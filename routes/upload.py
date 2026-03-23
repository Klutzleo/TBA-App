"""
File upload endpoint — stores files in Cloudflare R2.
Supports character portraits and campaign chat images/maps.
"""
import os
import uuid
import boto3
from botocore.config import Config
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from backend.auth.jwt import get_current_user
from backend.models import User, Message
from backend.database import get_db

router = APIRouter(prefix="/api/upload", tags=["Upload"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def get_r2_client():
    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all([account_id, access_key, secret_key]):
        raise HTTPException(status_code=500, detail="R2 storage not configured")

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_to_r2(contents: bytes, key: str, content_type: str) -> str:
    bucket = os.environ.get("R2_BUCKET_NAME", "tba-assets")
    public_url_base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    client = get_r2_client()
    client.put_object(Bucket=bucket, Key=key, Body=contents, ContentType=content_type)
    return f"{public_url_base}/{key}"


@router.post("/portrait")
async def upload_portrait(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a character portrait image to R2. Returns the public URL."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, and WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large — max 10MB")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    key = f"portraits/{current_user.id}/{uuid.uuid4()}.{ext}"

    try:
        url = upload_to_r2(contents, key, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    return {"url": url, "key": key}


@router.post("/image")
async def upload_campaign_image(
    file: UploadFile = File(...),
    campaign_id: str = Form(...),
    sender_name: str = Form(...),
    chat_mode: str = Form("ic"),  # ic or ooc
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload an image for use in campaign chat (Story or OOC tab).
    Saves the message to DB and returns the public URL + message record
    so the caller can broadcast via WS.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, and WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large — max 10MB")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    key = f"campaigns/{campaign_id}/images/{uuid.uuid4()}.{ext}"

    try:
        url = upload_to_r2(contents, key, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Persist as a message so it appears in history and the images tab
    msg = Message(
        campaign_id=campaign_id,
        sender_id=str(current_user.id),
        sender_name=sender_name,
        message_type="image_upload",
        mode=chat_mode,
        content=f"[image] {file.filename or 'image'}",
        extra_data={"url": url, "filename": file.filename or "image", "key": key}
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {
        "url": url,
        "key": key,
        "message_id": str(msg.id),
        "sender_name": sender_name,
        "chat_mode": chat_mode,
        "filename": file.filename or "image"
    }
