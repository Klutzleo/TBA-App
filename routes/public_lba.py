"""
routes/public_lba.py
LBA teaser tier — no login required ("window shopping"). Only ever returns
title/tagline/format/party-size/rating/genres/tags/adoption-count — never
story_text, world_text, NPCs, items, side quests, or attachments. Those live
behind routes/lba.py's login-required /packages/{id}/full, with an explicit
spoiler click-through in the UI.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import LbaPackage

public_lba_router = APIRouter(prefix="/api/public/lba", tags=["LBA"])


def _teaser_dict(p: LbaPackage) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "tagline": p.tagline,
        "format": p.format,
        "suggested_party_size": p.suggested_party_size,
        "content_rating": p.content_rating,
        "genres": p.genres or [],
        "tags": p.tags or [],
        "adoption_count": p.adoption_count or 0,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@public_lba_router.get("/entries")
async def list_public_entries(
    tag: Optional[str] = Query(None),
    format: List[str] = Query([]),
    party_size: List[str] = Query([]),
    rating: List[str] = Query([]),
    genre: List[str] = Query([]),
    db: Session = Depends(get_db),
):
    """Window-shopping list — teaser fields only, no login required.

    Each of format/party_size/rating/genre accepts multiple values
    (?format=one_shot&format=short_arc) — checking several boxes means
    "any of these", not "all of these". genre/tag are filtered in Python
    (JSONB array membership — same portability reasoning as elsewhere:
    avoid Postgres-only operators that would break under SQLite tests)."""
    q = db.query(LbaPackage).filter(LbaPackage.is_public == True)  # noqa: E712
    if format:
        q = q.filter(LbaPackage.format.in_(format))
    if party_size:
        q = q.filter(LbaPackage.suggested_party_size.in_(party_size))
    if rating:
        q = q.filter(LbaPackage.content_rating.in_(rating))
    entries = q.order_by(LbaPackage.adoption_count.desc(), LbaPackage.created_at.desc()).limit(200).all()

    if genre:
        wanted = set(genre)
        entries = [e for e in entries if wanted & set(e.genres or [])]

    if tag:
        tag = tag.strip().lower()
        entries = [e for e in entries if tag in (e.tags or [])]

    return [_teaser_dict(e) for e in entries]


@public_lba_router.get("/entries/{entry_id}")
async def get_public_entry_teaser(entry_id: UUID, db: Session = Depends(get_db)):
    """Teaser-only detail. Increments view_count — this is the "opened the
    page" action; revealing the full tier (routes/lba.py, login required)
    is a separate, deeper action and doesn't double-count here."""
    entry = db.query(LbaPackage).filter(
        LbaPackage.id == entry_id, LbaPackage.is_public == True  # noqa: E712
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    entry.view_count = (entry.view_count or 0) + 1
    db.commit()
    db.refresh(entry)

    return _teaser_dict(entry)
