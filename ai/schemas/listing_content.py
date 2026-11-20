"""Pydantic Schema for Listing & Content Agent."""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field, field_validator

BANNED_SUPERLATIVES = (
    "world's best",
    "best in the world",
    "miracle cure",
    "guaranteed 100%",
    "100% guaranteed",
    "100% risk free",
    "#1 on the planet",
    "magic solution",
)


class ListingContentInput(BaseModel):
    """Input payload for content generation."""
    product_name: str
    category: str
    key_features: List[str]
    target_customer: str
    supplier_notes: str = ""


class ListingContentOutput(BaseModel):
    """Strict schema for generated product listing content."""
    title: str = Field(..., min_length=5, max_length=150)
    short_description: str = Field(..., min_length=10, max_length=1000)
    highlights: List[str] = Field(..., min_length=2, max_length=10)
    pros: List[str] = Field(..., min_length=1, max_length=8)
    cons: List[str] = Field(..., min_length=1, max_length=8)
    seo_meta_title: str = Field(..., min_length=5, max_length=70)
    seo_meta_description: str = Field(..., min_length=10, max_length=160)

    @field_validator("seo_meta_title", mode="before")
    @classmethod
    def trim_seo_meta_title(cls, v: str) -> str:
        if isinstance(v, str) and len(v) > 70:
            v = v[:67].rsplit(" ", 1)[0] + "..." if " " in v[:67] else v[:70]
        return v

    @field_validator("seo_meta_description", mode="before")
    @classmethod
    def trim_seo_meta_description(cls, v: str) -> str:
        if isinstance(v, str) and len(v) > 160:
            v = v[:157].rsplit(" ", 1)[0] + "..." if " " in v[:157] else v[:160]
        return v

    @field_validator("title", "short_description", "seo_meta_title", "seo_meta_description")
    @classmethod
    def check_superlatives(cls, v: str) -> str:
        lower = v.lower()
        for banned in BANNED_SUPERLATIVES:
            if banned in lower:
                raise ValueError(f"Content contains banned superlative: '{banned}'")
        return v
