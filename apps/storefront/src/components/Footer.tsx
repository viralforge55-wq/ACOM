import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-20 border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-md space-y-2">
            <p className="font-serif text-base font-semibold text-ink">ACOM</p>
            <p className="text-xs leading-relaxed text-muted">
              Independent product discovery catalog. Affiliate links redirect to external
              merchants where prices and availability are set by the seller.
            </p>
          </div>

          <nav aria-label="Legal and company" className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted">
            <Link href="/affiliate-disclosure" className="hover:text-ink">
              Affiliate Disclosure
            </Link>
            <Link href="/privacy-policy" className="hover:text-ink">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-ink">
              Terms
            </Link>
            <Link href="/about" className="hover:text-ink">
              About
            </Link>
          </nav>
        </div>

        <p className="mt-8 border-t border-line pt-6 text-xs text-muted">
          © {new Date().getFullYear()} PROJECT ACOM. Prices shown are indicative and may change on
          the merchant website.
        </p>
      </div>
    </footer>
  );
}
