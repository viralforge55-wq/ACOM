import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Affiliate Disclosure",
  description: "How ACOM earns affiliate commissions and keeps product listings transparent.",
};

export default function AffiliateDisclosurePage() {
  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2 border-b border-line pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Compliance</p>
        <h1 className="font-serif text-3xl font-medium text-ink">Affiliate Disclosure</h1>
      </header>

      <div className="space-y-4 text-sm leading-relaxed text-ink">
        <p>
          ACOM participates in affiliate marketing programs with external marketplaces and merchant
          networks. When you click a &ldquo;View Deal&rdquo; link on ACOM and complete a qualifying
          purchase on the merchant&rsquo;s website, ACOM may earn an affiliate commission at no
          additional cost to you.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">
          How outbound links work
        </h2>
        <p className="text-muted">
          Clicking &ldquo;View Deal&rdquo; records an anonymous click event (with no personal
          contact information) and redirects your browser through our same-origin redirector
          (<code className="font-mono text-xs">/go/…</code>) to the merchant&rsquo;s product page
          with the partner tracking parameter attached.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">
          Pricing and availability
        </h2>
        <p className="text-muted">
          Display prices shown on ACOM affiliate pages are indicative only. Final selling prices,
          taxes, shipping charges, warranty terms, and returns are determined exclusively by the
          external merchant at checkout.
        </p>
      </div>
    </article>
  );
}
