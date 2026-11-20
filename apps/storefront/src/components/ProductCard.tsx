import Link from "next/link";
import { formatMoney } from "@/lib/format";
import type { CatalogProductCard } from "@/types/catalog";

type ProductCardProps = {
  item: CatalogProductCard;
};

export function ProductCard({ item }: ProductCardProps) {
  const isAffiliate = item.sales_type === "AFFILIATE";

  return (
    <article
      data-sales-type={item.sales_type}
      className="group flex flex-col justify-between rounded-lg border border-line bg-surface p-5 transition-colors hover:border-ink/40"
    >
      <div>
        <div className="mb-3 flex items-center justify-between gap-2 text-[11px] uppercase tracking-wider text-muted">
          <Link
            href={`/categories/${item.category.slug}`}
            className="hover:text-ink"
          >
            {item.category.name}
          </Link>
          <span className="rounded border border-line bg-paper px-2 py-0.5 font-medium text-ink">
            {item.marketplace}
          </span>
        </div>

        {item.image_url ? (
          <Link href={`/products/${item.slug}`} className="mb-4 block overflow-hidden rounded bg-paper">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={item.image_url}
              alt={item.title}
              className="aspect-[4/3] w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
            />
          </Link>
        ) : (
          <Link
            href={`/products/${item.slug}`}
            aria-label={item.title}
            className="mb-4 flex aspect-[4/3] items-center justify-center rounded border border-dashed border-line bg-paper text-xs tracking-wide text-muted"
          >
            {item.marketplace} Listing
          </Link>
        )}

        <h2 className="font-serif text-lg font-medium leading-snug text-ink">
          <Link href={`/products/${item.slug}`} className="hover:text-accent">
            {item.title}
          </Link>
        </h2>
      </div>

      <div className="mt-5 flex items-end justify-between border-t border-line pt-4">
        <div>
          {item.display_price ? (
            <>
              <p className="text-base font-semibold tabular-nums text-ink">
                {formatMoney(item.display_price)}
              </p>
              <p className="text-[11px] text-muted">Indicative price</p>
            </>
          ) : (
            <p className="text-xs text-muted">Check merchant for price</p>
          )}
        </div>

        <Link
          href={`/products/${item.slug}`}
          className={
            isAffiliate
              ? "rounded-md bg-accent px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
              : "rounded-md border border-line bg-paper px-3.5 py-2 text-xs font-medium text-muted"
          }
        >
          {item.cta_label}
        </Link>
      </div>
    </article>
  );
}
