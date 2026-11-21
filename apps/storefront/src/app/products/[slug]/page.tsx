import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { DisclosureBanner } from "@/components/DisclosureBanner";
import { ProductActionRouter } from "@/components/ProductActionRouter";
import { ProductImageGallery } from "@/components/ProductImageGallery";
import { formatMoney } from "@/lib/format";
import { fetchProductBySlug } from "@/lib/server/catalog_repository";

export const dynamic = "force-dynamic";

type ProductPageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  const { slug } = await params;
  const res = await fetchProductBySlug(slug);
  if (!res.envelope.ok) {
    return { title: "Product Not Found" };
  }
  const product = res.envelope.data;
  if (product.sales_type === "AFFILIATE") {
    return {
      title: product.seo_title || product.title,
      description: product.seo_description || product.short_description,
    };
  }
  return {
    title: product.title,
    description: product.short_description,
  };
}

export default async function ProductDetailPage({ params }: ProductPageProps) {
  const { slug } = await params;
  const res = await fetchProductBySlug(slug);

  if (!res.envelope.ok) {
    if (res.status === 404 || res.envelope.error.code === "NOT_FOUND") {
      notFound();
    }
    return (
      <section className="mx-auto max-w-xl py-12">
        <div className="rounded-md border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">
          Unable to load this product right now. Please try again shortly.
        </div>
      </section>
    );
  }

  const product = res.envelope.data;
  const isAffiliate = product.sales_type === "AFFILIATE";

  return (
    <article className="space-y-8" data-sales-type={product.sales_type}>
      <nav aria-label="Breadcrumb" className="text-xs text-muted">
        <Link href="/" className="hover:text-ink">
          Discover
        </Link>{" "}
        <span aria-hidden="true">/</span>{" "}
        <Link href={`/categories/${product.category.slug}`} className="hover:text-ink">
          {product.category.name}
        </Link>{" "}
        <span aria-hidden="true">/</span> <span className="text-ink">{product.title}</span>
      </nav>

      {isAffiliate ? <DisclosureBanner text={product.affiliate_disclosure} /> : null}

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <ProductImageGallery
            title={product.title}
            mainImage={product.image_url}
            images={product.images}
            marketplace={isAffiliate ? product.marketplace : "ACOM"}
            salesType={product.sales_type}
          />
        </div>

        <div className="space-y-6 lg:col-span-7">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {isAffiliate ? (
                <span className="rounded border border-line bg-surface px-2.5 py-0.5 font-medium text-ink">
                  {product.marketplace}
                </span>
              ) : (
                <span className="rounded border border-line bg-surface px-2.5 py-0.5 font-medium text-ink">
                  ACOM Direct
                </span>
              )}
              <span className="text-muted">{product.category.name}</span>
              {isAffiliate ? (
                <span className="font-mono text-[11px] text-muted">SKU: {product.product_sku}</span>
              ) : null}
            </div>

            <h1 className="font-serif text-3xl font-medium tracking-tight text-ink">
              {product.title}
            </h1>
          </div>

          <div className="rounded-lg border border-line bg-surface p-5 space-y-4">
            {isAffiliate ? (
              product.display_price ? (
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-ink">
                    {formatMoney(product.display_price)}
                  </p>
                  <p className="mt-0.5 text-xs text-muted">
                    Indicative price — final price and stock are confirmed on {product.marketplace}.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted">
                  Check current price and availability on {product.marketplace}.
                </p>
              )
            ) : (
              <div>
                <p className="text-2xl font-semibold tabular-nums text-ink">
                  {formatMoney(product.price)}
                </p>
                <p className="mt-0.5 text-xs text-muted">Authoritative storefront price</p>
              </div>
            )}

            <ProductActionRouter product={product} />
          </div>

          {product.short_description ? (
            <section className="space-y-2">
              <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Summary
              </h2>
              <p className="text-sm leading-relaxed text-ink">{product.short_description}</p>
            </section>
          ) : null}

          {isAffiliate && (product.pros.length > 0 || product.cons.length > 0) ? (
            <section
              aria-label="Key considerations"
              className="grid grid-cols-1 gap-4 sm:grid-cols-2"
            >
              {product.pros.length > 0 ? (
                <div className="rounded-lg border border-line bg-surface p-4">
                  <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">
                    Pros
                  </h2>
                  <ul className="mt-3 space-y-2 text-sm text-ink">
                    {product.pros.map((pro, idx) => (
                      <li key={idx} className="flex gap-2">
                        <span aria-hidden="true" className="text-accent">
                          +
                        </span>
                        <span>{pro}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {product.cons.length > 0 ? (
                <div className="rounded-lg border border-line bg-surface p-4">
                  <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                    Cons
                  </h2>
                  <ul className="mt-3 space-y-2 text-sm text-ink">
                    {product.cons.map((con, idx) => (
                      <li key={idx} className="flex gap-2">
                        <span aria-hidden="true" className="text-muted">
                          −
                        </span>
                        <span>{con}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>
    </article>
  );
}
