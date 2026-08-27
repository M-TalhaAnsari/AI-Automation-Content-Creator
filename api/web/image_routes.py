"""
api/web/image_routes.py — FastAPI Router for Image Generation Subsystem.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import Response as RawBinaryResponse
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from api.web.auth import verify_identity, verify_jwt
from api.web.image_deps import (
    IMAGE_QUEUE_NAME,
    extract_user_id,
    get_image_queue,
    get_image_redis_conn,
    get_image_service,
)
from api.web.image_errors import (
    ImageJobNotFoundError,
    ImageNotFoundError,
    VisualProfileNotFoundError,
    to_http_exception,
)
from api.web.image_jobs import run_image_generation_job
from api.web.image_schemas import (
    BatchImageGenerateRequest,
    BatchImageJobResponse,
    ImageAssetMeta,
    ImageGenerateRequest,
    ImageJobResponse,
    ImageJobStatusResponse,
    VisualProfileCreateRequest,
    VisualProfileResponse,
)
from imaging.models import BrandVisualProfile, ColorPalette, LayoutType
from imaging.service import ImageService

logger = logging.getLogger("trendforge.api.image_routes")

router = APIRouter(prefix="/images", tags=["Images"])


@router.post("/generate", response_model=ImageJobResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_image(
    body: ImageGenerateRequest,
    queue: Queue = Depends(get_image_queue),
    client_name: str = Depends(verify_identity),
):
    """
    Enqueue an asynchronous image generation job for a post.
    Returns a job_id for polling.
    """
    job = queue.enqueue(
        run_image_generation_job,
        body.session_id,
        client_name,
        body.post_number,
        body.post_data,
        body.platform or "instagram",
        body.visual_profile_id,
        body.reference_image_id,
        body.custom_prompt,
        job_timeout=120,
        result_ttl=3600,
        meta={
            "client_name": client_name,
            "session_id": body.session_id,
            "post_number": body.post_number,
        },
    )

    logger.info("Enqueued image job %s for post %d", job.id, body.post_number)
    return ImageJobResponse(status="queued", job_id=job.id, post_number=body.post_number)


@router.post("/generate-batch", response_model=BatchImageJobResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_images_batch(
    body: BatchImageGenerateRequest,
    queue: Queue = Depends(get_image_queue),
    client_name: str = Depends(verify_identity),
):
    """
    Enqueue image generation jobs for multiple posts in batch.
    """
    jobs = []
    for item in body.posts:
        job = queue.enqueue(
            run_image_generation_job,
            body.session_id,
            client_name,
            item.post_number,
            item.post_data,
            body.platform or "instagram",
            body.visual_profile_id,
            item.reference_image_id,
            item.custom_prompt,
            job_timeout=120,
            result_ttl=3600,
            meta={
                "client_name": client_name,
                "session_id": body.session_id,
                "post_number": item.post_number,
            },
        )
        jobs.append(ImageJobResponse(status="queued", job_id=job.id, post_number=item.post_number))

    return BatchImageJobResponse(status="queued", jobs=jobs)


@router.get("/status/{job_id}", response_model=ImageJobStatusResponse)
def get_image_job_status(
    job_id: str,
    conn=Depends(get_image_redis_conn),
    client_name: str = Depends(verify_identity),
):
    """
    Poll status of an image generation job.
    """
    try:
        job = Job.fetch(job_id, connection=conn)
    except NoSuchJobError:
        raise to_http_exception(ImageJobNotFoundError(job_id))

    if job.meta.get("client_name") != client_name:
        raise to_http_exception(ImageJobNotFoundError(job_id))

    post_number = job.meta.get("post_number", 1)

    if job.is_finished:
        result = job.result or {}
        if result.get("status") == "completed":
            return ImageJobStatusResponse(
                status="completed",
                job_id=job_id,
                post_number=post_number,
                asset_id=result.get("asset_id"),
                image_url=result.get("image_url"),
                file_size_bytes=result.get("file_size_bytes"),
            )
        else:
            return ImageJobStatusResponse(
                status="failed",
                job_id=job_id,
                post_number=post_number,
                asset_id=result.get("asset_id"),
                detail=result.get("error", "Image generation failed"),
            )

    if job.is_failed:
        return ImageJobStatusResponse(
            status="failed",
            job_id=job_id,
            post_number=post_number,
            detail="Background image generation worker failed",
        )

    if job.is_started:
        return ImageJobStatusResponse(status="generating", job_id=job_id, post_number=post_number)

    return ImageJobStatusResponse(status="queued", job_id=job_id, post_number=post_number)


@router.post("/upload-reference", status_code=status.HTTP_201_CREATED)
async def upload_reference_image(
    file: UploadFile = File(...),
    client_name: str = Depends(verify_identity),
    service: ImageService = Depends(get_image_service),
):
    """
    Upload a user reference post image for style transfer.
    Returns the reference asset_id.
    """
    user_id = extract_user_id(client_name)
    ref_id = str(uuid.uuid4())
    content = await file.read()

    # Determine extension and content type
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        ext = "png"
    content_type = file.content_type or f"image/{ext}"

    key = service.storage.build_key(user_id=user_id, asset_id=ref_id, extension=ext)
    service.storage.save(key, content, content_type=content_type)

    logger.info("Uploaded user reference image %s (%d bytes)", ref_id, len(content))
    return {
        "reference_asset_id": ref_id,
        "image_url": f"/images/{ref_id}",
        "file_size_bytes": len(content),
    }


@router.get("/{asset_id}")
def serve_image_asset(
    asset_id: str,
    request: Request,
    service: ImageService = Depends(get_image_service),
):
    """
    Serve raw image bytes securely with correct content-type and cache headers.
    """
    result = service.get_asset_bytes(asset_id)
    if not result:
        raise to_http_exception(ImageNotFoundError(asset_id))

    data, content_type = result
    origin = request.headers.get("origin") or "*"
    headers = {
        "Cache-Control": "public, max-age=3600, must-revalidate",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Content-Disposition": f'inline; filename="{asset_id}.png"',
    }
    if origin != "*":
        headers["Access-Control-Allow-Credentials"] = "true"

    return RawBinaryResponse(
        content=data,
        media_type=content_type,
        headers=headers,
    )


@router.get("/{asset_id}/meta", response_model=ImageAssetMeta)
def get_image_asset_metadata(
    asset_id: str,
    service: ImageService = Depends(get_image_service),
):
    """
    Retrieve generation metadata for an image asset.
    """
    asset = service.get_asset(asset_id)
    if not asset:
        raise to_http_exception(ImageNotFoundError(asset_id))

    return ImageAssetMeta(
        id=asset.id,
        session_id=asset.session_id,
        post_number=asset.post_number,
        mode=asset.mode.value,
        prompt=asset.prompt,
        negative_prompt=asset.negative_prompt,
        visual_profile_id=asset.visual_profile_id,
        provider_name=asset.provider_name,
        model_name=asset.model_name,
        reference_asset_id=asset.reference_asset_id,
        source_post_version=asset.source_post_version,
        storage_backend=asset.storage_backend.value,
        storage_key=asset.storage_key,
        content_type=asset.content_type,
        file_size_bytes=asset.file_size_bytes,
        status=asset.status.value,
        error_message=asset.error_message,
        image_url=f"/images/{asset.id}",
        created_at=asset.created_at.isoformat() if asset.created_at else None,
        updated_at=asset.updated_at.isoformat() if asset.updated_at else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Visual Profiles Management Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/profiles/list", response_model=List[VisualProfileResponse])
def list_visual_profiles(
    client_name: str = Depends(verify_jwt),
    service: ImageService = Depends(get_image_service),
):
    """
    List brand visual profiles available to the user.
    """
    user_id = extract_user_id(client_name)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    domain_profiles = service.metadata_repo.list_profiles(user_id)
    return [
        VisualProfileResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            color_palette=p.color_palette.model_dump() if hasattr(p.color_palette, "model_dump") else p.color_palette,
            typography_style=p.typography_style,
            visual_mood=p.visual_mood,
            default_layout=p.default_layout.value if hasattr(p.default_layout, "value") else str(p.default_layout),
            platform_overrides={k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in p.platform_overrides.items()},
            is_default=p.is_default,
            created_at=p.created_at.isoformat() if hasattr(p.created_at, "isoformat") else str(p.created_at),
            updated_at=p.updated_at.isoformat() if hasattr(p.updated_at, "isoformat") else str(p.updated_at),
        )
        for p in domain_profiles
    ]


@router.post("/profiles/create", response_model=VisualProfileResponse, status_code=status.HTTP_201_CREATED)
def create_visual_profile(
    body: VisualProfileCreateRequest,
    client_name: str = Depends(verify_jwt),
    service: ImageService = Depends(get_image_service),
):
    """
    Create a new custom brand visual profile.
    """
    user_id = extract_user_id(client_name)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    palette = ColorPalette(**body.color_palette) if body.color_palette else ColorPalette()
    profile = BrandVisualProfile(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=body.name,
        description=body.description or "",
        color_palette=palette,
        typography_style=body.typography_style or "minimal-sans",
        visual_mood=body.visual_mood or "clean-informative",
        default_layout=LayoutType(body.default_layout or "minimal_clean"),
        platform_overrides=body.platform_overrides or {},
    )

    saved = service.metadata_repo.save_profile(profile)
    return VisualProfileResponse(
        id=saved.id,
        name=saved.name,
        description=saved.description,
        color_palette=saved.color_palette.model_dump(),
        typography_style=saved.typography_style,
        visual_mood=saved.visual_mood,
        default_layout=saved.default_layout.value,
        platform_overrides=saved.platform_overrides,
        is_default=saved.is_default,
        created_at=saved.created_at.isoformat() if saved.created_at else None,
        updated_at=saved.updated_at.isoformat() if saved.updated_at else None,
    )
