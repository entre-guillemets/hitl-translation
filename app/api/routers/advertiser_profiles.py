"""Advertiser Profile CRUD endpoints.

Each AdvertiserProfile captures the brand identity parameters that govern
how ad copy should be transcreated and evaluated for a specific advertiser.

GET    /api/advertiser-profiles            List all active profiles
POST   /api/advertiser-profiles            Create a new profile
GET    /api/advertiser-profiles/{id}       Get a single profile
PUT    /api/advertiser-profiles/{id}       Update a profile
DELETE /api/advertiser-profiles/{id}       Soft-delete (sets isActive=False)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.base import prisma

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/advertiser-profiles", tags=["Advertiser Profiles"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AdvertiserProfileCreate(BaseModel):
    brandName: str
    brandTone: str          # BrandTone enum value
    adRegister: str         # AdRegister enum value
    targetMarkets: list[str] = []
    keyTerms: list[str] = []
    tabooTerms: list[str] = []
    policyNotes: Optional[str] = None


class AdvertiserProfileUpdate(BaseModel):
    brandName: Optional[str] = None
    brandTone: Optional[str] = None
    adRegister: Optional[str] = None
    targetMarkets: Optional[list[str]] = None
    keyTerms: Optional[list[str]] = None
    tabooTerms: Optional[list[str]] = None
    policyNotes: Optional[str] = None
    isActive: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(profile) -> dict:
    return {
        "id": profile.id,
        "brandName": profile.brandName,
        "brandTone": str(profile.brandTone),
        "register": str(profile.adRegister),
        "targetMarkets": profile.targetMarkets,
        "keyTerms": profile.keyTerms,
        "tabooTerms": profile.tabooTerms,
        "policyNotes": profile.policyNotes,
        "isActive": profile.isActive,
        "createdAt": profile.createdAt.isoformat(),
        "updatedAt": profile.updatedAt.isoformat(),
    }


async def _ensure_connected():
    if not prisma.is_connected():
        await prisma.connect()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_profiles(include_inactive: bool = False):
    """List advertiser profiles. Active only by default."""
    await _ensure_connected()
    where = {} if include_inactive else {"isActive": True}
    profiles = await prisma.advertiserprofile.find_many(
        where=where,
        order={"brandName": "asc"},
    )
    return {"profiles": [_serialize(p) for p in profiles], "count": len(profiles)}


@router.post("", status_code=201)
async def create_profile(body: AdvertiserProfileCreate):
    """Create a new advertiser profile."""
    await _ensure_connected()
    from prisma.enums import BrandTone, AdRegister
    try:
        tone = BrandTone[body.brandTone]
        reg = AdRegister[body.adRegister]
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Invalid enum value: {e}")

    profile = await prisma.advertiserprofile.create(
        data={
            "brandName": body.brandName,
            "brandTone": tone,
            "adRegister": reg,
            "targetMarkets": body.targetMarkets,
            "keyTerms": body.keyTerms,
            "tabooTerms": body.tabooTerms,
            "policyNotes": body.policyNotes,
        }
    )
    logger.info(f"Created AdvertiserProfile '{profile.brandName}' ({profile.id})")
    return _serialize(profile)


@router.get("/{profile_id}")
async def get_profile(profile_id: str):
    """Get a single advertiser profile by ID."""
    await _ensure_connected()
    profile = await prisma.advertiserprofile.find_unique(where={"id": profile_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Advertiser profile not found.")
    return _serialize(profile)


@router.put("/{profile_id}")
async def update_profile(profile_id: str, body: AdvertiserProfileUpdate):
    """Update an advertiser profile."""
    await _ensure_connected()
    existing = await prisma.advertiserprofile.find_unique(where={"id": profile_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Advertiser profile not found.")

    data: dict = {}
    if body.brandName is not None:
        data["brandName"] = body.brandName
    if body.brandTone is not None:
        from prisma.enums import BrandTone
        try:
            data["brandTone"] = BrandTone[body.brandTone]
        except KeyError:
            raise HTTPException(status_code=422, detail=f"Invalid BrandTone: {body.brandTone}")
    if body.adRegister is not None:
        from prisma.enums import AdRegister
        try:
            data["adRegister"] = AdRegister[body.adRegister]
        except KeyError:
            raise HTTPException(status_code=422, detail=f"Invalid AdRegister: {body.adRegister}")
    if body.targetMarkets is not None:
        data["targetMarkets"] = body.targetMarkets
    if body.keyTerms is not None:
        data["keyTerms"] = body.keyTerms
    if body.tabooTerms is not None:
        data["tabooTerms"] = body.tabooTerms
    if body.policyNotes is not None:
        data["policyNotes"] = body.policyNotes
    if body.isActive is not None:
        data["isActive"] = body.isActive

    updated = await prisma.advertiserprofile.update(where={"id": profile_id}, data=data)
    return _serialize(updated)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str):
    """Soft-delete an advertiser profile (sets isActive=False)."""
    await _ensure_connected()
    existing = await prisma.advertiserprofile.find_unique(where={"id": profile_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Advertiser profile not found.")
    await prisma.advertiserprofile.update(
        where={"id": profile_id},
        data={"isActive": False},
    )
    logger.info(f"Soft-deleted AdvertiserProfile {profile_id}")
