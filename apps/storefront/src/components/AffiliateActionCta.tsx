"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useAnonymousSession } from "@/hooks/useAnonymousSession";
import type { AffiliateClickResponse, ApiEnvelope } from "@/types/catalog";

type AffiliateActionCtaProps = {
  slug: string;
  marketplace: string;
  ctaLabel: string;
};

/**
 * Affiliate-only outbound action component.
 * Records an anonymous click via POST /api/affiliate/click (no PII)
 * and navigates to the returned server-side /go/{click_id} redirector.
 * Never interacts with cart or checkout state.
 */
export function AffiliateActionCta({ slug, marketplace, ctaLabel }: AffiliateActionCtaProps) {
  const pathname = usePathname();
  const { getSessionId } = useAnonymousSession();
  const [pending, setPending] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function handleViewDeal() {
    if (pending) return;
    setPending(true);
    setErrorMsg(null);

    try {
      const sessionId = getSessionId();
      const response = await fetch("/api/affiliate/click", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_slug: slug,
          session_id: sessionId,
          source: "internal",
          medium: "storefront",
          landing_path: pathname || `/products/${slug}`,
        }),
      });

      const payload = (await response.json()) as ApiEnvelope<AffiliateClickResponse>;
      if (!response.ok || !payload.ok) {
        setErrorMsg(
          !payload.ok && payload.error?.message
            ? payload.error.message
            : "This deal is currently unavailable.",
        );
        setPending(false);
        return;
      }

      window.location.assign(payload.data.redirect_url);
    } catch {
      setErrorMsg("Unable to open merchant link right now. Please try again.");
      setPending(false);
    }
  }

  return (
    <div className="space-y-2" data-sales-type="AFFILIATE">
      <button
        type="button"
        onClick={handleViewDeal}
        disabled={pending}
        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
      >
        <span>{pending ? "Opening merchant..." : `${ctaLabel} on ${marketplace}`}</span>
        <span aria-hidden="true">↗</span>
      </button>

      <p className="text-xs text-muted">
        Opens external {marketplace} product page via tracked redirect (
        <span className="font-mono">rel=&quot;sponsored nofollow&quot;</span>).
      </p>

      {errorMsg ? (
        <p role="alert" className="text-xs font-medium text-red-700">
          {errorMsg}
        </p>
      ) : null}
    </div>
  );
}
