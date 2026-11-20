import Link from "next/link";
import { CatalogFilters } from "@/components/CatalogFilters";
import { ProductCard } from "@/components/ProductCard";
import { fetchCatalog, fetchCategories } from "@/lib/server/catalog_repository";
import type { CatalogSort } from "@/types/catalog";

export const dynamic = "force-dynamic";

const ALLOWED_SORTS = new Set<CatalogSort>(["newest", "popular", "price_asc", "price_desc"]);

type HomePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function firstParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export default async function HomePage({ searchParams }: HomePageProps) {
  const sp = await searchParams;
  const pageParsed = Number.parseInt(firstParam(sp.page) || "1", 10);
  const page = Number.isFinite(pageParsed) && pageParsed >= 1 ? pageParsed : 1;
  const q = firstParam(sp.q).trim().slice(0, 120);
  const category = firstParam(sp.category).trim().toLowerCase() || undefined;
  const sortRaw = (firstParam(sp.sort).trim().toLowerCase() || "newest") as CatalogSort;
  const sort: CatalogSort = ALLOWED_SORTS.has(sortRaw) ? sortRaw : "newest";

  const [catalogRes, categoriesRes] = await Promise.all([
    fetchCatalog({
      page,
      page_size: 12,
      category,
      sales_type: "AFFILIATE",
      sort,
      q: q || undefined,
    }),
    fetchCategories(),
  ]);

  const categories = categoriesRes.envelope.ok ? categoriesRes.envelope.data.categories : [];
  const items = catalogRes.envelope.ok ? catalogRes.envelope.data.items : [];
  const meta = catalogRes.envelope.ok ? catalogRes.envelope.meta : null;

  function pageHref(targetPage: number): string {
    const qs = new URLSearchParams();
    qs.set("page", String(targetPage));
    if (q) qs.set("q", q);
    if (sort !== "newest") qs.set("sort", sort);
    if (category) qs.set("category", category);
    return `/?${qs.toString()}`;
  }

  return (
    <div className="space-y-10">
      <section className="max-w-2xl space-y-3 border-b border-line pb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
          Verified Affiliate Catalog
        </p>
        <h1 className="font-serif text-3xl font-medium tracking-tight text-ink sm:text-4xl">
          Products selected for utility, priced transparently at the merchant.
        </h1>
        <p className="text-sm leading-relaxed text-muted">
          Every listing is reviewed before publication and links out to its marketplace via a
          disclosed affiliate redirect. Prices shown are indicative.
        </p>
      </section>

      <CatalogFilters
        categories={categories}
        activeCategory={category}
        query={q}
        sort={sort}
        basePath="/"
      />

      {!catalogRes.envelope.ok ? (
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          Unable to load the live catalog right now. Please refresh in a moment.
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface px-6 py-12 text-center">
          <p className="font-serif text-lg text-ink">No matching published products</p>
          <p className="mt-1 text-sm text-muted">
            {q
              ? `No published listings matched "${q}".`
              : "There are currently no published listings in this view."}
          </p>
          {q || category ? (
            <Link
              href="/"
              className="mt-4 inline-block text-xs font-medium text-accent underline underline-offset-2"
            >
              Clear filters
            </Link>
          ) : null}
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between text-xs text-muted">
            <p>
              Showing <span className="font-medium text-ink">{items.length}</span> of{" "}
              <span className="font-medium text-ink">{meta?.total ?? items.length}</span> published{" "}
              {(meta?.total ?? items.length) === 1 ? "product" : "products"}
            </p>
            <p>Page {meta?.page ?? page}</p>
          </div>

          <section
            aria-label="Published products"
            className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {items.map((item) => (
              <ProductCard key={item.id} item={item} />
            ))}
          </section>

          {meta && (meta.page > 1 || meta.has_next) ? (
            <nav
              aria-label="Pagination"
              className="flex items-center justify-between border-t border-line pt-6 text-sm"
            >
              {meta.page > 1 ? (
                <Link
                  href={pageHref(meta.page - 1)}
                  className="rounded-md border border-line bg-surface px-4 py-2 text-ink hover:border-ink/40"
                >
                  ← Previous
                </Link>
              ) : (
                <span />
              )}

              {meta.has_next ? (
                <Link
                  href={pageHref(meta.page + 1)}
                  className="rounded-md border border-line bg-surface px-4 py-2 text-ink hover:border-ink/40"
                >
                  Next →
                </Link>
              ) : null}
            </nav>
          ) : null}
        </>
      )}
    </div>
  );
}
