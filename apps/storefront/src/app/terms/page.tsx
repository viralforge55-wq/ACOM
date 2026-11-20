import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms and Conditions",
  description: "Terms governing use of the ACOM product discovery catalog.",
};

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2 border-b border-line pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Compliance</p>
        <h1 className="font-serif text-3xl font-medium text-ink">Terms and Conditions</h1>
      </header>

      <div className="space-y-4 text-sm leading-relaxed text-ink">
        <p>
          ACOM operates as an informational product catalog and affiliate publisher. By using this
          website, you agree to the terms below.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">
          Third-party transactions
        </h2>
        <p className="text-muted">
          For affiliate listings, ACOM is not the seller of record. Purchases, order fulfillment,
          invoices, cancellations, warranties, and refunds are handled solely by the external
          marketplace where you complete your order.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">Accuracy of information</h2>
        <p className="text-muted">
          We review product details and links periodically before publication, but product
          specifications, stock levels, and prices may change without notice on external
          marketplaces. Always verify details on the merchant page before purchasing.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">Acceptable use</h2>
        <p className="text-muted">
          Automated abuse, scraping beyond normal browsing, or attempting to manipulate affiliate
          click telemetry is prohibited and subject to rate limiting.
        </p>
      </div>
    </article>
  );
}
