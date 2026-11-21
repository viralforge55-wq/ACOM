export type SalesType = "AFFILIATE" | "DROPSHIP";

export type CatalogSort = "newest" | "popular" | "price_asc" | "price_desc";

export type Money = {
  amount: string;
  currency: string;
};

export type CategoryRef = {
  slug: string;
  name: string;
};

export type CategorySummary = {
  slug: string;
  name: string;
  product_count: number;
  parent: string | null;
};

export type CatalogProductCard = {
  id: string;
  slug: string;
  title: string;
  sales_type: SalesType;
  category: CategoryRef;
  image_url?: string;
  images?: string[];
  display_price?: Money;
  marketplace: string;
  badge?: string;
  cta_label: string;
};

export type AffiliateProductDetail = {
  id: string;
  slug: string;
  title: string;
  product_sku: string;
  sales_type: "AFFILIATE";
  category: CategoryRef;
  marketplace: string;
  cta_label: "View Deal";
  disclosure_required: boolean;
  affiliate_disclosure: string;
  view_deal_url: string;
  pros: string[];
  cons: string[];
  image_url?: string;
  images?: string[];
  display_price?: Money;
  short_description?: string;
  long_description?: string;
  seo_title?: string;
  seo_description?: string;
};

export type DropshipAvailability = {
  in_stock: boolean;
  quantity_band: string;
  ships_in_days: number;
};

export type DropshipProductDetail = {
  id: string;
  slug: string;
  title: string;
  sales_type: "DROPSHIP";
  category: CategoryRef;
  price: Money;
  availability: DropshipAvailability;
  hsn_category?: string;
  return_policy_summary?: string;
  image_url?: string;
  images?: string[];
  short_description?: string;
  cta_label: "Add to Cart";
};

export type ProductDetail = AffiliateProductDetail | DropshipProductDetail;

export type CatalogPaginationMeta = {
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  correlation_id: string;
};

export type ApiMeta = {
  correlation_id: string;
  [key: string]: unknown;
};

export type ApiSuccessEnvelope<T, M extends ApiMeta = ApiMeta> = {
  ok: true;
  data: T;
  meta: M;
};

export type ApiErrorEnvelope = {
  ok: false;
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
  meta: ApiMeta;
};

export type ApiEnvelope<T, M extends ApiMeta = ApiMeta> =
  | ApiSuccessEnvelope<T, M>
  | ApiErrorEnvelope;

export type AffiliateClickRequest = {
  product_slug: string;
  session_id: string;
  source?: string;
  medium?: string;
  referrer?: string;
  landing_path?: string;
};

export type AffiliateClickResponse = {
  click_id: string;
  redirect_url: string;
};

export type RedirectResolution = {
  click_id: string;
  destination_url: string;
  rel: string;
};
