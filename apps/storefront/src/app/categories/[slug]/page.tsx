import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { CatalogFilters } from "@/components/CatalogFilters";
import { ProductCard } from "@/components/ProductCard";
import { fetchCatalog, fetchCategories } from "@/lib/server/catalog_repository";
import type { CatalogSort } from "@/types/catalog";

export const dynamic = "force-dynamic";

const ALLOWED_SORTS = new Set<CatalogSort>(["newest", "popular", "price_asc", "price_desc"]);

type CategoryPageProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function firstParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export async function generateMetadata({ params }: CategoryPageProps): Promise<Metadata> {
  const { slug } = await params;
  const categoriesRes = await fetchCategories();
  const categories = categoriesRes.envelope.ok ? categoriesRes.envelope.data.categories : [];
  const matched = categories.find((c) => c.slug === slug.toLowerCase());
  return {
    title: matched ? matched.name : "Category",
  };
}

export default async function CategoryPage({ params, searchParams }: CategoryPageProps) {
  const { slug } = await params;
  const normalizedSlug = slug.trim().toLowerCase();
  const sp = await searchParams;

  const pageParsed = Number.parseInt(firstParam(sp.page) || "1", 10);
  const page = Number.isFinite(pageParsed) && pageParsed >= 1 ? pageParsed : 1;
  const q = firstParam(sp.q).trim().slice(0, 120);
  const sortRaw = (firstParam(sp.sort).trim().toLowerCase() || "newest") as CatalogSort;
  const sort: CatalogSort = ALLOWED_SORTS.has(sortRaw) ? sortRaw : "newest";

  const [categoriesRes, catalogRes] = await Promise.all([
    fetchCategories(),
    fetchCatalog({
      page,
      page_size: 12,
      category: normalizedSlug,
      sales_type: "AFFILIATE",
      sort,
      q: q || undefined,
    }),
  ]);

  const categories = categoriesRes.envelope.ok ? categoriesRes.envelope.data.categories : [];
  const currentCategory = categories.find((c) => c.slug === normalizedSlug);
  if (!currentCategory) {
    notFound();
  }

  const items = catalogRes.envelope.ok ? catalogRes.envelope.data.items : [];
  const meta = catalogRes.envelope.ok ? catalogRes.envelope.meta : null;

  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb" className="text-xs text-muted">
        <Link href="/" className="hover:text-ink">
          Discover
        </Link>{" "}
        <span aria-hidden="true">/</span> <span className="text-ink">{currentCategory.name}</span>
      </nav>

      <header className="space-y-2 border-b border-line pb-6">
        <h1 className="font-serif text-3xl font-medium text-ink">{currentCategory.name}</h1>
        <p className="text-sm text-muted">
          {currentCategory.product_count} published{" "}
          {currentCategory.product_count === 1 ? "product" : "products"} in this category.
        </p>
      </header>

      <CatalogFilters
        categories={categories}
        activeCategory={currentCategory.slug}
        query={q}
        sort={sort}
        basePath={`/categories/${currentCategory.slug}`}
      />

      {items.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface px-6 py-12 text-center">
          <p className="font-serif text-lg text-ink">No matching products in {currentCategory.name}</p>
          <Link
            href={`/categories/${currentCategory.slug}`}
            className="mt-3 inline-block text-xs font-medium text-accent underline underline-offset-2"
          >
            Clear search
          </Link>
        </div>
      ) : (
        <section
          aria-label={`${currentCategory.name} products`}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {items.map((item) => (
            <ProductCard key={item.id} item={item} />
          ))}
        </section>
      )}

      {meta && (meta.page > 1 || meta.has_next) ? (
        <nav
          aria-label="Pagination"
          className="flex items-center justify-between border-t border-line pt-6 text-sm"
        >
          {meta.page > 1 ? (
            <Link
              href={`/categories/${currentCategory.slug}?page=${meta.page - 1}`}
              className="rounded-md border border-line bg-surface px-4 py-2 text-ink hover:border-ink/40"
            >
              ← Previous
            </Link>
          ) : (
            <span />
          )}
          {meta.has_next ? (
            <Link
              href={`/categories/${currentCategory.slug}?page=${meta.page + 1}`}
              className="rounded-md border border-line bg-surface px-4 py-2 text-ink hover:border-ink/40"
            >
              Next →
            </Link>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}
