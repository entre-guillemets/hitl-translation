import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from prisma import Prisma

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/style-guides", tags=["style-guides"])

db = Prisma()


async def _get_db() -> Prisma:
    if not db.is_connected():
        await db.connect()
    return db


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------

class StyleGuideTermIn(BaseModel):
    term: str
    targetTerm: Optional[str] = None
    type: str          # "REQUIRED" | "FORBIDDEN"
    glossaryTermId: Optional[str] = None


class StyleGuideIn(BaseModel):
    name: str
    description: Optional[str] = None
    styleRegister: str   # Register enum value
    tone: Optional[str] = None
    languagePairs: list[str] = []
    rules: list[str] = []
    terms: list[StyleGuideTermIn] = []


class StyleGuideUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    styleRegister: Optional[str] = None
    tone: Optional[str] = None
    languagePairs: Optional[list[str]] = None
    rules: Optional[list[str]] = None
    isActive: Optional[bool] = None


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.get("")
async def list_style_guides(active_only: bool = True):
    prisma = await _get_db()
    where = {"isActive": True} if active_only else {}
    guides = await prisma.styleguide.find_many(
        where=where,
        include={"terms": True},
        order_by={"createdAt": "desc"},
    )
    return guides


@router.post("", status_code=201)
async def create_style_guide(body: StyleGuideIn):
    prisma = await _get_db()
    guide = await prisma.styleguide.create(
        data={
            "name": body.name,
            "description": body.description,
            "styleRegister": body.styleRegister,
            "tone": body.tone,
            "languagePairs": body.languagePairs,
            "rules": body.rules,
            "terms": {
                "create": [
                    {
                        "term": t.term,
                        "targetTerm": t.targetTerm,
                        "type": t.type,
                        "glossaryTermId": t.glossaryTermId,
                    }
                    for t in body.terms
                ]
            },
        },
        include={"terms": True},
    )
    return guide


@router.get("/{guide_id}")
async def get_style_guide(guide_id: str):
    prisma = await _get_db()
    guide = await prisma.styleguide.find_unique(
        where={"id": guide_id},
        include={"terms": True},
    )
    if not guide:
        raise HTTPException(status_code=404, detail="Style guide not found")
    return guide


@router.patch("/{guide_id}")
async def update_style_guide(guide_id: str, body: StyleGuideUpdate):
    prisma = await _get_db()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    guide = await prisma.styleguide.update(
        where={"id": guide_id},
        data=data,
        include={"terms": True},
    )
    return guide


@router.delete("/{guide_id}", status_code=204)
async def delete_style_guide(guide_id: str):
    prisma = await _get_db()
    await prisma.styleguide.delete(where={"id": guide_id})


@router.post("/{guide_id}/terms", status_code=201)
async def add_term(guide_id: str, body: StyleGuideTermIn):
    prisma = await _get_db()
    term = await prisma.styleguideterm.create(
        data={
            "term": body.term,
            "targetTerm": body.targetTerm,
            "type": body.type,
            "styleGuideId": guide_id,
            "glossaryTermId": body.glossaryTermId,
        }
    )
    return term


@router.delete("/{guide_id}/terms/{term_id}", status_code=204)
async def delete_term(guide_id: str, term_id: str):
    prisma = await _get_db()
    await prisma.styleguideterm.delete(where={"id": term_id})
