import Link from "next/link";
import type { CatalogSort, CategorySummary } from "@/types/catalog";

type CatalogFiltersProps = {
  categories: CategorySummary[];
  activeCategory?: string;
  query: string;
  sort: CatalogSort;
  basePath: string;
};

export function CatalogFilters({
  categories,
  activeCategory,
  query,
  sort,
  basePath,
}: CatalogFiltersProps) {
  return (
    <section aria-label="Catalog filters" className="space-y-4">
      <form
        method="GET"
        action={basePath}
        className="flex flex-col gap-3 sm:flex-row sm:items-center"
      >
        <label className="sr-only" htmlFor="catalog-search">
          Search products
        </label>
        <input
          id="catalog-search"
          type="search"
          name="q"
          defaultValue={query}
          placeholder="Search published products..."
          maxLength={120}
          className="w-full rounded-md border border-line bg-surface px-3.5 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none sm:flex-1"
        />

        <label className="sr-only" htmlFor="catalog-sort">
          Sort products
        </label>
        <select
          id="catalog-sort"
          name="sort"
          defaultValue={sort}
          className="rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
        >
          <option value="newest">Newest</option>
          <option value="popular">Popular</option>
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
        </select>

        <button
          type="submit"
          className="rounded-md border border-ink bg-ink px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ink/85"
        >
          Apply
        </button>

        {query || sort !== "newest" ? (
          <Link
            href={basePath}
            className="text-center text-xs font-medium text-muted underline underline-offset-2 hover:text-ink"
          >
            Reset
          </Link>
        ) : null}
      </form>

      <div className="flex flex-wrap items-center gap-2">
        <Link
          href="/"
          className={
            !activeCategory
              ? "rounded-full bg-ink px-3 py-1 text-xs font-medium text-white"
              : "rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted hover:border-ink/40 hover:text-ink"
          }
        >
          All Categories
        </Link>

        {categories.map((cat) => {
          const isActive = activeCategory === cat.slug;
          return (
            <Link
              key={cat.slug}
              href={`/categories/${cat.slug}`}
              className={
                isActive
                  ? "rounded-full bg-ink px-3 py-1 text-xs font-medium text-white"
                  : "rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted hover:border-ink/40 hover:text-ink"
              }
            >
              {cat.name}{" "}
              <span className={isActive ? "text-white/75" : "text-muted/80"}>
                ({cat.product_count})
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
