"use client";

import { useState } from "react";

type ProductImageGalleryProps = {
  title: string;
  mainImage?: string;
  images?: string[];
  marketplace?: string;
  salesType?: "AFFILIATE" | "DROPSHIP";
};

export function ProductImageGallery({
  title,
  mainImage,
  images = [],
  marketplace = "Amazon",
  salesType = "AFFILIATE",
}: ProductImageGalleryProps) {
  // Aggregate unique image URLs in order
  const allImages = Array.from(
    new Set([mainImage, ...images].filter((img): img is string => Boolean(img && img.trim())))
  );

  const [activeIndex, setActiveIndex] = useState(0);
  const activeImage = allImages[activeIndex] || mainImage;

  if (allImages.length === 0) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-lg border border-dashed border-line bg-surface text-xs uppercase tracking-widest text-muted">
        {salesType === "AFFILIATE" ? `${marketplace} Product` : "ACOM Direct Product"}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Main Image Display */}
      <div className="relative overflow-hidden rounded-lg border border-line bg-white shadow-sm">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={activeImage}
          alt={`${title} - view ${activeIndex + 1}`}
          className="aspect-[4/3] w-full object-contain p-2 transition-all duration-200"
          loading="eager"
        />
        {allImages.length > 1 ? (
          <div className="absolute bottom-2 right-2 rounded bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-xs">
            {activeIndex + 1} / {allImages.length}
          </div>
        ) : null}
      </div>

      {/* Thumbnails Strip */}
      {allImages.length > 1 ? (
        <div
          role="tablist"
          aria-label="Product thumbnails"
          className="flex gap-2 overflow-x-auto pb-1"
        >
          {allImages.map((img, idx) => {
            const isSelected = idx === activeIndex;
            return (
              <button
                key={idx}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-label={`Select product image ${idx + 1}`}
                onClick={() => setActiveIndex(idx)}
                className={`relative h-16 w-16 shrink-0 overflow-hidden rounded-md border-2 bg-white transition-all ${
                  isSelected
                    ? "border-accent ring-2 ring-accent/20"
                    : "border-line opacity-70 hover:border-muted hover:opacity-100"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img}
                  alt={`Thumbnail ${idx + 1}`}
                  className="h-full w-full object-contain p-1"
                  loading="lazy"
                />
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
