import Link from "next/link";

export function Header() {
  return (
    <header className="border-b border-line bg-surface/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link
          href="/"
          className="flex items-baseline gap-2 text-ink no-underline focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <span className="font-serif text-xl font-semibold tracking-tight">ACOM</span>
          <span className="hidden text-xs uppercase tracking-[0.14em] text-muted sm:inline">
            Product Index
          </span>
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-6 text-sm text-muted">
          <Link href="/cart" className="hover:text-ink">Cart</Link>
          <Link href="/" className="transition-colors hover:text-ink">
            Discover
          </Link>
          <Link href="/about" className="transition-colors hover:text-ink">
            About
          </Link>
          <Link href="/affiliate-disclosure" className="transition-colors hover:text-ink">
            Disclosure
          </Link>
        </nav>
      </div>
    </header>
  );
}
