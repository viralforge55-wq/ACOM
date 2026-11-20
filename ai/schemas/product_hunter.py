"""Pydantic Schema for Product Hunter Agent."""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ProductHunterInput(BaseModel):
    """Input payload provided to the Product Hunter agent."""
    raw_text: str = Field(..., description="Raw scraped or provided supplier product description")
    supplier_name: str = Field(..., description="Identified supplier name")
    supplier_sku: str = Field(..., description="Supplier SKU or product identifier")
    category: str = Field(..., description="Target category")
    supplier_cost: float = Field(..., gt=0, description="Supplier cost in INR")
    source_url: Optional[str] = Field(None, description="Source catalog or reference URL")


class ProductHunterOutput(BaseModel):
    """Strict output schema required from the Product Hunter agent."""
    product_name: str = Field(..., min_length=2, max_length=150)
    category: str = Field(..., min_length=2, max_length=80)
    supplier_name: str = Field(..., min_length=2, max_length=100)
    supplier_sku: str = Field(..., min_length=2, max_length=100)
    supplier_price: str = Field(..., pattern=r"^\d+(\.\d{2})?$")
    competitor_price: str = Field(..., pattern=r"^\d+(\.\d{2})?$")
    proposed_selling_price: str = Field(..., pattern=r"^\d+(\.\d{2})?$")
    estimated_shipping_cost: str = Field(..., pattern=r"^\d+(\.\d{2})?$")
    estimated_return_rate: float = Field(..., ge=0.0, le=1.0)
    target_customer: str = Field(..., min_length=3)
    key_features: List[str] = Field(..., min_length=1)
    verdict: Literal["RECOMMENDED", "REJECTED", "NEEDS_REVIEW"]
    reasoning: str = Field(..., min_length=10)
    margin_pct: Optional[float] = None
    product_score: Optional[float] = None

    @field_validator("verdict", mode="before")
    @classmethod
    def normalize_verdict(cls, v: str) -> str:
        return str(v).upper()
