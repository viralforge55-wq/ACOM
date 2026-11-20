import Link from "next/link";

export default function NotFound() {
  return (
    <section className="mx-auto max-w-lg py-16 text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">404</p>
      <h1 className="mt-2 font-serif text-3xl font-medium text-ink">Page not found</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        The product or page you requested does not exist or is no longer published.
      </p>
      <div className="mt-8">
        <Link
          href="/"
          className="inline-flex rounded-md bg-ink px-5 py-2.5 text-sm font-medium text-white hover:bg-ink/85"
        >
          Back to Catalog
        </Link>
      </div>
    </section>
  );
}
