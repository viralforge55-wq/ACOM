"use client";

import { useRouter } from "next/navigation";
import type { DropshipProductDetail } from "@/types/catalog";

export function DropshipAction({ product }: { product: DropshipProductDetail }) {
  const router = useRouter();
  function add() {
    const stored = JSON.parse(localStorage.getItem("acom-cart") || "[]") as { product_slug: string; quantity: number }[];
    const items = Array.isArray(stored) ? stored : [];
    const existing = items.find((item) => item.product_slug === product.slug);
    if (existing) existing.quantity = Math.min(25, existing.quantity + 1);
    else items.push({ product_slug: product.slug, quantity: 1 });
    localStorage.setItem("acom-cart", JSON.stringify(items));
    router.push("/cart");
  }
  return <div className="space-y-3">
    <button disabled={!product.availability.in_stock} onClick={add} className="rounded-md bg-accent px-6 py-3 text-white disabled:opacity-40">Add to Cart</button>
    <p className="text-sm text-muted">Test-mode checkout · dispatch estimate {product.availability.ships_in_days} days</p>
  </div>;
}
