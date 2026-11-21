import type {
  AffiliateClickRequest,
  AffiliateClickResponse,
  RedirectResolution,
} from "@/types/catalog";
import { CURATED_KITCHEN_PRODUCTS } from "./catalog_repository";
import { callFrappeMethod, type FrappeCallResult } from "./frappe_client";
import { isSafeHttpUrl, isValidUuidV4 } from "./security";

export async function submitAffiliateClick(
  payload: AffiliateClickRequest,
  options: { userAgent?: string | null; correlationId?: string } = {},
): Promise<FrappeCallResult<AffiliateClickResponse>> {
  try {
    const upstream = await callFrappeMethod<AffiliateClickResponse>({
      method: "POST",
      endpoint: "acom_core.api.affiliate.record_affiliate_click",
      body: payload,
      userAgent: options.userAgent,
      correlationId: options.correlationId,
    });
    if (upstream.envelope.ok) {
      return upstream;
    }
  } catch {
    // Upstream unreachable; check curated catalog
  }

  const matched = CURATED_KITCHEN_PRODUCTS.find((p) => p.slug === payload.product_slug);
  if (matched && matched.view_deal_url) {
    return {
      status: 200,
      envelope: {
        ok: true,
        data: {
          click_id: crypto.randomUUID(),
          redirect_url: matched.view_deal_url,
        },
        meta: { correlation_id: options.correlationId || "curated-fallback" },
      },
    };
  }

  return {
    status: 502,
    envelope: {
      ok: false,
      error: {
        code: "UPSTREAM_UNAVAILABLE",
        message: "Catalog service is temporarily unavailable.",
        details: {},
      },
      meta: { correlation_id: options.correlationId || "upstream-unavailable" },
    },
  };
}

export async function resolveAffiliateRedirect(
  clickId: string,
  correlationId?: string,
): Promise<FrappeCallResult<RedirectResolution>> {
  const cleaned = clickId.trim();
  if (!isValidUuidV4(cleaned)) {
    return {
      status: 404,
      envelope: {
        ok: false,
        error: {
          code: "NOT_FOUND",
          message: "Affiliate link not found.",
          details: {},
        },
        meta: { correlation_id: correlationId || "invalid-click-id" },
      },
    };
  }

  const result = await callFrappeMethod<RedirectResolution>({
    method: "GET",
    endpoint: "acom_core.api.affiliate.resolve_affiliate_redirect",
    query: { click_id: cleaned },
    correlationId,
  });

  if (result.envelope.ok && !isSafeHttpUrl(result.envelope.data.destination_url)) {
    return {
      status: 502,
      envelope: {
        ok: false,
        error: {
          code: "INVALID_REDIRECT_TARGET",
          message: "Destination URL is not permitted.",
          details: {},
        },
        meta: result.envelope.meta,
      },
    };
  }

  return result;
}
