"""
fetchers/youtube_fetcher.py — YouTube Data API v3 Fetcher

Uses the OFFICIAL YouTube Data API (not scraping libraries like pytube/
yt_dlp, which break frequently as YouTube changes internals). Fetches
videos matching core_topic, plus description and transcript — no comments,
since comments add noise without value for content-generation purposes.
"""

from typing import List, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .base import logger, normalize_item

# Transcript fetching is optional — the fetcher still works without it,
# just returns items without a "transcript" field if the library isn't installed.
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _TRANSCRIPT_AVAILABLE = True
except ImportError:
    _TRANSCRIPT_AVAILABLE = False


def _fetch_transcript_safe(video_id: str, language: str = "en") -> str:
    """
    Best-effort transcript fetch. Returns empty string on any failure —
    never raises, since a missing transcript should not fail the whole fetch.
    """
    if not _TRANSCRIPT_AVAILABLE:
        return ""
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=[language])
        return " ".join(snippet.text for snippet in transcript.snippets())[:2000]
    except Exception:
        return ""


def fetch_youtube(state, config) -> List[Dict[str, Any]]:
    """
    Fetch YouTube videos matching core_topic (or trending if no topic given).
    Each item includes title, description, and (if available) transcript.
    Deliberately excludes comments — not useful signal for content generation.
    """
    topic = getattr(state, "fetch_summary", None) or getattr(state, "core_topic", "")
    items: List[Dict[str, Any]] = []

    if not config.YOUTUBE_API_KEY:
        logger.error("YouTube API key missing; skipping YouTube.")
        return items

    try:
        youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
    except Exception as e:
        logger.error(f"Failed to build YouTube client: {e}")
        return items

    try:
        if topic:
            request = youtube.search().list(
                part="snippet",
                q=topic,
                type="video",
                maxResults=10,
                order="viewCount",
            )
        else:
            request = youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode="US",
                maxResults=10,
            )
        response = request.execute()

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        return items
    except Exception as e:
        logger.error(f"YouTube fetch failed: {e}")
        return items

    for video in response.get("items", []):
        snippet = video.get("snippet", {})
        video_id = video.get("id", {}).get("videoId", "") if isinstance(video.get("id"), dict) else video.get("id", "")
        title = snippet.get("title", "No title")
        link = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        description = snippet.get("description", "") or "YouTube video."

        transcript = _fetch_transcript_safe(video_id) if video_id else ""

        items.append(normalize_item(
            title=title,
            link=link,
            summary=description[:500],
            source="youtube",
            channel=snippet.get("channelTitle", ""),
            published_at=snippet.get("publishedAt", ""),
            transcript=transcript,   # empty string if unavailable — never None, never missing key
        ))

    logger.info(f"YouTube returned {len(items)} items (transcripts included where available).")
    return items