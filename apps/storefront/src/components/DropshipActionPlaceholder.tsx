import type { DropshipProductDetail } from "@/types/catalog";

type DropshipActionPlaceholderProps = {
  product: DropshipProductDetail;
};

/**
 * Isolated component for DROPSHIP sales type (ADR-0001).
 * Dropshipping cart & checkout are deferred to Phase 5; this component
 * intentionally contains zero cart, pricing, or payment logic.
 */
export function DropshipActionPlaceholder({ product }: DropshipActionPlaceholderProps) {
  return (
    <div
      className="space-y-2 rounded-md border border-line bg-paper p-4"
      data-sales-type="DROPSHIP"
    >
      <button
        type="button"
        disabled
        className="inline-flex w-full cursor-not-allowed items-center justify-center rounded-md border border-line bg-surface px-6 py-3 text-sm font-medium text-muted sm:w-auto"
      >
        {product.availability.in_stock ? "Direct Checkout — Coming Soon" : "Currently Out of Stock"}
      </button>
      <p className="text-xs text-muted">
        Direct ACOM fulfillment checkout is not enabled in this release.
      </p>
    </div>
  );
}
