export type Role = "user" | "assistant";

export type PostEdit = {
  id: string;
  instruction: string;
  atLabel: string;
};

export type GeneratedPost = {
  id: string;
  number?: number;
  platform: string;
  title: string;
  hook: string;
  summary?: string[];
  caption: string;
  hashtags: string[];
  sourceUrl: string;
  sourceLabel: string;
  imageUrl?: string;
  imageAssetId?: string;
  isGeneratingImage?: boolean;
  imageError?: string;
  edits?: PostEdit[];
  latencyMs?: number;
};

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  posts?: GeneratedPost[];
};

export type Session = {
  id: string;
  title: string;
  updatedLabel: string;
};

export const PLATFORMS = [
  { value: "auto", label: "Auto-detect" },
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "x", label: "X / Twitter" },
  { value: "youtube", label: "YouTube" },
  { value: "reddit", label: "Reddit" },
] as const;

export const POST_COUNTS = [1, 3, 5, 8, 10] as const;

export const SOURCES = [
  "GitHub",
  "Reddit",
  "Google Trends",
  "HackerNews",
  "YouTube",
  "Tavily",
  "PapersWithCode",
] as const;

export const SUGGESTED_PROMPTS = [
  {
    title: "5 Instagram posts about Docker deployment",
    hint: "pulls from GitHub + HackerNews",
  },
  {
    title: "3 LinkedIn posts on AI agent frameworks",
    hint: "pulls from PapersWithCode + Reddit",
  },
  {
    title: "What's trending in local-first apps this week?",
    hint: "pulls from Google Trends + Tavily",
  },
  {
    title: "5 X threads about Rust performance wins",
    hint: "pulls from GitHub + YouTube",
  },
];

export const DEMO_SESSIONS: Session[] = [
  { id: "s1", title: "Docker deployment carousel", updatedLabel: "2m ago" },
  { id: "s2", title: "AI agent frameworks roundup", updatedLabel: "Yesterday" },
  { id: "s3", title: "Local-first app trends", updatedLabel: "Tuesday" },
  { id: "s4", title: "Rust performance thread ideas", updatedLabel: "Last week" },
];

export const DEMO_MESSAGES: ChatMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "generate 5 instagram posts about docker deployment",
  },
  {
    id: "m2",
    role: "assistant",
    content:
      "I pulled **14 live items** from GitHub, HackerNews and Reddit and kept the 5 strongest angles. Each post is written for Instagram, hook first, with the source it came from.",
    posts: [
      {
        id: "p1",
        platform: "instagram",
        title: "Multi-stage builds cut our image 82%",
        hook: "Your Docker image is probably 4x bigger than it needs to be.",
        caption:
          "A multi-stage build ships only the final artifact — no compilers, no dev deps, no cache. One team took a 1.2GB Node image down to 210MB by moving the build into a throwaway stage.\n\nThe trick: build in one stage, COPY --from into a slim runtime stage, and never let your toolchain reach production.",
        hashtags: ["#docker", "#devops", "#containers"],
        sourceUrl: "https://github.com",
        sourceLabel: "GitHub",
      },
      {
        id: "p2",
        platform: "instagram",
        title: "Distroless is quietly winning",
        hook: "No shell. No package manager. Nothing to exploit.",
        caption:
          "Distroless images strip the OS down to your runtime. Smaller surface, faster pulls, fewer CVEs in the scan report on Monday morning.\n\nDebugging gets harder — that's the trade. Keep a debug variant around for the days you need a shell.",
        hashtags: ["#docker", "#security", "#platformengineering"],
        sourceUrl: "https://news.ycombinator.com",
        sourceLabel: "HackerNews",
        edits: [
          { id: "e1", instruction: "make the hook shorter", atLabel: "1m ago" },
        ],
      },
      {
        id: "p3",
        platform: "instagram",
        title: "Your layer cache order is backwards",
        hook: "COPY . . before installing deps? That's a rebuild every commit.",
        caption:
          "Copy your lockfile first, install, then copy source. Docker reuses the dependency layer until the lockfile actually changes — minutes back on every CI run.",
        hashtags: ["#docker", "#ci", "#devex"],
        sourceUrl: "https://reddit.com",
        sourceLabel: "Reddit",
      },
    ],
  },
];

export function deriveSourceLabel(url: string, sourceHint?: string): string {
  if (sourceHint) {
    const hint = sourceHint.toLowerCase();
    if (hint.includes("github")) return "GitHub";
    if (hint.includes("hackernews") || hint.includes("hacker_news") || hint.includes("hn")) return "HackerNews";
    if (hint.includes("reddit")) return "Reddit";
    if (hint.includes("youtube")) return "YouTube";
    if (hint.includes("trend")) return "Google Trends";
    if (hint.includes("tavily")) return "Tavily";
    if (hint.includes("paper")) return "PapersWithCode";
  }

  if (!url) return "Web";
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    if (hostname.includes("github.com")) return "GitHub";
    if (hostname.includes("ycombinator.com")) return "HackerNews";
    if (hostname.includes("reddit.com")) return "Reddit";
    if (hostname.includes("youtube.com") || hostname.includes("youtu.be")) return "YouTube";
    if (hostname.includes("google.com")) return "Google Trends";
    if (hostname.includes("arxiv.org") || hostname.includes("paperswithcode.com")) return "PapersWithCode";
    return hostname.replace(/^www\./, "");
  } catch {
    return "Source";
  }
}

export function cleanHumanCopy(text: string): string {
  if (!text) return "";
  return text
    .replace(/^#+\s+/gm, "")          // strip markdown headings #, ##, ###
    .replace(/\*\*(.*?)\*\*/g, "$1")  // strip markdown bold stars
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")      // strip code backticks
    .trim();
}

export function rawPostToGeneratedPost(
  raw: Record<string, any>,
  fallbackPlatform = "instagram",
  index = 1
): GeneratedPost {
  const url = raw.link || raw.url || raw.source_url || "";
  const sourceLabel = deriveSourceLabel(url, raw._source || raw.source);
  const postNum = raw.number ?? index;

  // Clean title & hook from any AI markdown headers (# Title)
  const rawTitle = raw.title || raw.name || `Post ${index}`;
  const cleanTitle = cleanHumanCopy(String(rawTitle));

  const rawHook = raw.hook || (Array.isArray(raw.summary) ? raw.summary[0] : raw.summary) || "";
  const cleanHook = cleanHumanCopy(String(rawHook));

  let summaryArray: string[] | undefined;
  if (Array.isArray(raw.summary)) {
    summaryArray = raw.summary.map((s: any) => cleanHumanCopy(String(s))).filter(Boolean);
  } else if (typeof raw.summary === "string" && raw.summary.trim()) {
    summaryArray = raw.summary
      .split("\n")
      .map((s: string) => cleanHumanCopy(s))
      .filter(Boolean);
  }

  const rawCaption = raw.caption || (Array.isArray(raw.summary) ? raw.summary.join("\n\n") : raw.summary) || "";
  const cleanCaption = cleanHumanCopy(String(rawCaption));

  return {
    id: raw.id || `post-${postNum}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    number: postNum,
    platform: raw.platform || (fallbackPlatform !== "auto" ? fallbackPlatform : "instagram"),
    title: cleanTitle,
    hook: cleanHook,
    summary: summaryArray,
    caption: cleanCaption,
    hashtags: Array.isArray(raw.hashtags) ? raw.hashtags : [],
    sourceUrl: url,
    sourceLabel,
    imageUrl: raw.image_url || raw.imageUrl || undefined,
    imageAssetId: raw.image_asset_id || raw.imageAssetId || undefined,
    edits: Array.isArray(raw.edits) ? raw.edits : [],
  };
}

export function formatTimeAgo(isoDateString?: string | null): string {
  if (!isoDateString) return "just now";
  try {
    const date = new Date(isoDateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "recently";
  }
}

export function normalizeHistoryEntry(
  entry: Record<string, any>,
  posts?: GeneratedPost[]
): ChatMessage | null {
  if (!entry || typeof entry !== "object") return null;
  if (entry.role === "tool") return null; // internal dispatch bookkeeping
  if (!entry.content && !posts?.length) return null;

  return {
    id: entry.id || `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    role: entry.role === "user" ? "user" : "assistant",
    content: entry.content || "",
    posts,
  };
}

