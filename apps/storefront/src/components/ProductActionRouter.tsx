import type { ProductDetail } from "@/types/catalog";
import { AffiliateActionCta } from "./AffiliateActionCta";
import { DropshipActionPlaceholder } from "./DropshipActionPlaceholder";

type ProductActionRouterProps = {
  product: ProductDetail;
};

/**
 * Enforces strict separation between AFFILIATE and DROPSHIP flows
 * (ARCHITECTURE_RULES.md §1.2, MASTER_BLUEPRINT.md §8).
 */
export function ProductActionRouter({ product }: ProductActionRouterProps) {
  if (product.sales_type === "AFFILIATE") {
    return (
      <AffiliateActionCta
        slug={product.slug}
        marketplace={product.marketplace}
        ctaLabel={product.cta_label}
      />
    );
  }

  return <DropshipActionPlaceholder product={product} />;
}
