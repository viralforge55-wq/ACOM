import type {
  ApiEnvelope,
  CatalogPaginationMeta,
  CatalogProductCard,
  CatalogSort,
  CategorySummary,
  ProductDetail,
} from "@/types/catalog";
import { callFrappeMethod, type FrappeCallResult } from "./frappe_client";
import { assertNoBannedFields, isValidSlug } from "./security";

export type CatalogQuery = {
  page?: number;
  page_size?: number;
  category?: string;
  sales_type?: "AFFILIATE" | "DROPSHIP";
  sort?: CatalogSort;
  q?: string;
};

export async function fetchCatalog(
  query: CatalogQuery = {},
  correlationId?: string,
): Promise<FrappeCallResult<{ items: CatalogProductCard[] }, CatalogPaginationMeta>> {
  const result = await callFrappeMethod<{ items: CatalogProductCard[] }, CatalogPaginationMeta>({
    method: "GET",
    endpoint: "acom_core.api.catalog.get_catalog",
    query: {
      page: query.page ?? 1,
      page_size: query.page_size ?? 20,
      category: query.category,
      sales_type: query.sales_type,
      sort: query.sort ?? "newest",
      q: query.q,
    },
    correlationId,
  });

  if (result.envelope.ok) {
    assertNoBannedFields(result.envelope.data);
  }
  return result;
}

export async function fetchProductBySlug(
  slug: string,
  correlationId?: string,
): Promise<FrappeCallResult<ProductDetail>> {
  const cleaned = slug.trim().toLowerCase();
  if (!cleaned || !isValidSlug(cleaned)) {
    return {
      status: 404,
      envelope: {
        ok: false,
        error: {
          code: "NOT_FOUND",
          message: "Product not found.",
          details: {},
        },
        meta: { correlation_id: correlationId || "invalid-slug" },
      },
    };
  }

  const result = await callFrappeMethod<ProductDetail>({
    method: "GET",
    endpoint: "acom_core.api.catalog.get_product",
    query: { slug: cleaned },
    correlationId,
  });

  if (result.envelope.ok) {
    assertNoBannedFields(result.envelope.data);
  }
  return result;
}

export async function fetchCategories(
  correlationId?: string,
): Promise<FrappeCallResult<{ categories: CategorySummary[] }>> {
  const result = await callFrappeMethod<{ categories: CategorySummary[] }>({
    method: "GET",
    endpoint: "acom_core.api.catalog.get_categories",
    correlationId,
  });

  if (result.envelope.ok) {
    assertNoBannedFields(result.envelope.data);
  }
  return result;
}

export function extractCatalogItems(
  envelope: ApiEnvelope<{ items: CatalogProductCard[] }, CatalogPaginationMeta>,
): CatalogProductCard[] {
  return envelope.ok ? envelope.data.items : [];
}
