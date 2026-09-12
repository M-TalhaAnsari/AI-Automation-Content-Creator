"""
api/web/image_routes.py — FastAPI Router for Image Generation Subsystem.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import Response as RawBinaryResponse
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from api.web import db
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
    UserAssetResponse,
    UserAssetListResponse,
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


@router.post("/upload-asset", response_model=UserAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_user_asset(
    file: UploadFile = File(...),
    asset_role: str = Form("avatar"),
    default_scope: str = Form("all"),
    client_name: str = Depends(verify_identity),
    service: ImageService = Depends(get_image_service),
):
    """
    Upload a custom branded image asset (creator avatar, brand logo, product screenshot, sticker).
    Returns metadata and URL for selective post injection.
    """
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum allowed limit of 10MB",
        )

    # Determine extension and validate MIME
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "webp", "svg"):
        ext = "png"

    allowed_mimes = ("image/png", "image/jpeg", "image/webp", "image/svg+xml")
    content_type = file.content_type or f"image/{ext}"
    if content_type not in allowed_mimes and not any(ext in m for m in allowed_mimes):
        content_type = f"image/{ext}"

    # Validate asset_role
    valid_roles = ("avatar", "logo", "hero_inset", "custom_sticker")
    normalized_role = asset_role if asset_role in valid_roles else "avatar"

    # Validate default_scope
    valid_scopes = ("all", "first_only", "last_only", "custom", "none")
    normalized_scope = default_scope if default_scope in valid_scopes else "all"

    user_id = extract_user_id(client_name)
    asset_id = f"ast_{uuid.uuid4().hex[:12]}"
    key = service.storage.build_key(user_id=user_id, asset_id=asset_id, extension=ext)
    service.storage.save(key, content, content_type=content_type)

    record = db.create_user_uploaded_asset(
        asset_id=asset_id,
        user_id=user_id,
        filename=file.filename or f"asset.{ext}",
        mime_type=content_type,
        file_size_bytes=len(content),
        asset_role=normalized_role,
        default_scope=normalized_scope,
        storage_key=key,
    )

    logger.info("Uploaded user asset %s (%s, %d bytes) for user %s", asset_id, normalized_role, len(content), user_id)
    return UserAssetResponse(
        id=record["id"],
        filename=record["filename"],
        mime_type=record["mime_type"],
        file_size_bytes=record["file_size_bytes"],
        asset_role=record["asset_role"],
        default_scope=record["default_scope"],
        url=f"/images/{asset_id}",
        created_at=record["created_at"],
    )


@router.get("/user-assets", response_model=UserAssetListResponse)
def list_user_assets(
    client_name: str = Depends(verify_identity),
):
    """List all custom image assets uploaded by the current user."""
    user_id = extract_user_id(client_name)
    if user_id <= 0:
        return UserAssetListResponse(assets=[])

    records = db.list_user_uploaded_assets(user_id)
    return UserAssetListResponse(
        assets=[
            UserAssetResponse(
                id=r["id"],
                filename=r["filename"],
                mime_type=r["mime_type"],
                file_size_bytes=r["file_size_bytes"],
                asset_role=r["asset_role"],
                default_scope=r["default_scope"],
                url=f"/images/{r['id']}",
                created_at=r["created_at"],
            )
            for r in records
        ]
    )


@router.delete("/user-assets/{asset_id}")
def delete_user_asset(
    asset_id: str,
    client_name: str = Depends(verify_identity),
    service: ImageService = Depends(get_image_service),
):
    """Delete an uploaded image asset and free its storage."""
    user_id = extract_user_id(client_name)
    record = db.get_user_uploaded_asset(asset_id)
    if not record or record.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found or access denied")

    try:
        service.storage.delete(record["storage_key"])
    except Exception as e:
        logger.warning("Could not delete file from storage for asset %s: %s", asset_id, e)

    db.delete_user_uploaded_asset(asset_id, user_id)
    return {"ok": True, "deleted_id": asset_id}


@router.get("/{asset_id}")
def serve_image_asset(
    asset_id: str,
    request: Request,
    service: ImageService = Depends(get_image_service),
):
    """
    Serve raw image bytes securely with correct content-type and cache headers.
    Supports both generated AI assets and user-uploaded branded assets.
    """
    result = service.get_asset_bytes(asset_id)
    if not result:
        # Check user_uploaded_assets table
        record = db.get_user_uploaded_asset(asset_id)
        if record and record.get("storage_key"):
            data = service.storage.get(record["storage_key"])
            if data:
                result = (data, record.get("mime_type", "image/png"))

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
