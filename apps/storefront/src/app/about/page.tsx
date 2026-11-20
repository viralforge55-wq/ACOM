import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About ACOM",
  description: "How ACOM curates and verifies affiliate product listings.",
};

export default function AboutPage() {
  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2 border-b border-line pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">About</p>
        <h1 className="font-serif text-3xl font-medium text-ink">About PROJECT ACOM</h1>
      </header>

      <div className="space-y-4 text-sm leading-relaxed text-ink">
        <p>
          ACOM is a lean, verification-first product discovery catalog built on top of a structured
          ERP catalog backend. Listings are published only after link verification, content review,
          and explicit affiliate disclosure checks pass.
        </p>

        <p className="text-muted">
          Every product card distinguishes clearly between external affiliate offers and direct
          storefront products. In the current release, ACOM operates exclusively as an affiliate
          catalog, linking readers directly to external merchants.
        </p>

        <p className="pt-2 text-xs text-muted">
          Read our{" "}
          <Link href="/affiliate-disclosure" className="text-accent underline underline-offset-2">
            Affiliate Disclosure
          </Link>{" "}
          and{" "}
          <Link href="/privacy-policy" className="text-accent underline underline-offset-2">
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </article>
  );
}
