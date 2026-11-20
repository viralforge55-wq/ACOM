import type { AffiliateClickRequest } from "@/types/catalog";

/**
 * Authoritative union of DATA_DICTIONARY.md §13 + API_CONTRACTS.md §1
 * fields that must NEVER reach the browser on any public catalog or product route.
 */
export const BANNED_PUBLIC_FIELDS: ReadonlySet<string> = new Set([
  "supplier_cost",
  "supplier",
  "supplier_sku",
  "supplier_stock",
  "shipping_cost",
  "packaging_cost",
  "erpnext_item",
  "price_list",
  "contribution_profit",
  "contribution_margin_pct",
  "payment_fee_percent",
  "expected_return_rate",
  "commission_rate",
  "commission_type",
  "commission_flat_amount",
  "commission_amount",
  "commission_status",
  "network_conversion_id",
  "affiliate_url",
  "affiliate_network",
  "payload",
  "error_details",
  "owner",
  "modified_by",
  "creation",
  "modified",
  "docstatus",
  "idx",
  "ai_task",
  "approval_status",
  "approved_by",
  "decision_note",
  "rationale",
  "recommendation",
  "risk_level",
  "verification_method",
  "last_verified_date",
  "content_review_status",
]);

const SLUG_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const UUID_V4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SESSION_ID_REGEX = /^[A-Za-z0-9_-]{8,128}$/;
const MEDIUM_REGEX = /^[A-Za-z0-9_-]{1,64}$/;

const ALLOWED_UTM_SOURCES: ReadonlySet<string> = new Set([
  "direct",
  "google",
  "bing",
  "duckduckgo",
  "youtube",
  "instagram",
  "facebook",
  "twitter",
  "x",
  "reddit",
  "whatsapp",
  "telegram",
  "email",
  "newsletter",
  "referral",
  "organic",
  "internal",
  "other",
]);

const ALLOWED_CLICK_KEYS: ReadonlySet<string> = new Set([
  "product_slug",
  "session_id",
  "source",
  "medium",
  "referrer",
  "landing_path",
  "clicked_at",
]);

export function findBannedFields(value: unknown, path = "$"): string[] {
  const hits: string[] = [];
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      hits.push(...findBannedFields(item, `${path}[${index}]`));
    });
    return hits;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
      if (BANNED_PUBLIC_FIELDS.has(key)) {
        hits.push(`${path}.${key}`);
      }
      hits.push(...findBannedFields(nested, `${path}.${key}`));
    }
  }
  return hits;
}

export function assertNoBannedFields(value: unknown): void {
  const hits = findBannedFields(value);
  if (hits.length > 0) {
    throw new Error(`Security guard blocked banned public fields: ${hits.join(", ")}`);
  }
}

export function isValidSlug(value: string): boolean {
  return SLUG_REGEX.test(value.trim().toLowerCase());
}

export function isValidUuidV4(value: string): boolean {
  return UUID_V4_REGEX.test(value.trim());
}

export function isSafeHttpUrl(rawUrl: string): boolean {
  try {
    const parsed = new URL(rawUrl);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}

export type ClickValidationResult =
  | { ok: true; value: AffiliateClickRequest }
  | { ok: false; code: "VALIDATION_ERROR"; message: string; fields: string[] };

/**
 * Strictly validate an inbound click request body before forwarding to ERPNext.
 * Rejects any unknown or PII fields (email, phone, ip_address, price, etc.).
 */
export function validateClickPayload(raw: unknown): ClickValidationResult {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return {
      ok: false,
      code: "VALIDATION_ERROR",
      message: "Request body must be a JSON object.",
      fields: [],
    };
  }

  const obj = raw as Record<string, unknown>;
  const unknownFields = Object.keys(obj)
    .filter((k) => !ALLOWED_CLICK_KEYS.has(k))
    .sort();
  if (unknownFields.length > 0) {
    return {
      ok: false,
      code: "VALIDATION_ERROR",
      message: "Unknown or prohibited fields in request payload.",
      fields: unknownFields,
    };
  }

  const productSlug =
    typeof obj.product_slug === "string" ? obj.product_slug.trim().toLowerCase() : "";
  if (!productSlug || !isValidSlug(productSlug)) {
    return {
      ok: false,
      code: "VALIDATION_ERROR",
      message: "product_slug is required and must be a valid slug.",
      fields: ["product_slug"],
    };
  }

  const sessionId = typeof obj.session_id === "string" ? obj.session_id.trim() : "";
  if (!sessionId || !SESSION_ID_REGEX.test(sessionId)) {
    return {
      ok: false,
      code: "VALIDATION_ERROR",
      message: "session_id is required and must be 8-128 safe characters.",
      fields: ["session_id"],
    };
  }

  const result: AffiliateClickRequest = {
    product_slug: productSlug,
    session_id: sessionId,
  };

  if (obj.source !== undefined && obj.source !== null && obj.source !== "") {
    if (typeof obj.source !== "string") {
      return {
        ok: false,
        code: "VALIDATION_ERROR",
        message: "source must be a string.",
        fields: ["source"],
      };
    }
    const normalizedSource = obj.source.trim().toLowerCase();
    if (!ALLOWED_UTM_SOURCES.has(normalizedSource)) {
      return {
        ok: false,
        code: "VALIDATION_ERROR",
        message: "source is not in the allowed UTM source list.",
        fields: ["source"],
      };
    }
    result.source = normalizedSource;
  }

  if (obj.medium !== undefined && obj.medium !== null && obj.medium !== "") {
    if (typeof obj.medium !== "string" || !MEDIUM_REGEX.test(obj.medium.trim())) {
      return {
        ok: false,
        code: "VALIDATION_ERROR",
        message: "medium must be 1-64 safe characters.",
        fields: ["medium"],
      };
    }
    result.medium = obj.medium.trim().toLowerCase();
  }

  if (obj.landing_path !== undefined && obj.landing_path !== null && obj.landing_path !== "") {
    if (typeof obj.landing_path !== "string") {
      return {
        ok: false,
        code: "VALIDATION_ERROR",
        message: "landing_path must be a string.",
        fields: ["landing_path"],
      };
    }
    const lp = obj.landing_path.trim();
    if (!lp.startsWith("/") || lp.length > 512) {
      return {
        ok: false,
        code: "VALIDATION_ERROR",
        message: "landing_path must be a relative path starting with '/'.",
        fields: ["landing_path"],
      };
    }
    result.landing_path = lp;
  }

  if (obj.referrer !== undefined && obj.referrer !== null && obj.referrer !== "") {
    if (typeof obj.referrer !== "string" || !isSafeHttpUrl(obj.referrer.trim())) {
      return {
        ok: false,
        code: "VALIDATION_ERROR",
        message: "referrer must be a valid http(s) URL.",
        fields: ["referrer"],
      };
    }
    result.referrer = obj.referrer.trim();
  }

  return { ok: true, value: result };
}
