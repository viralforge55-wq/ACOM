import Link from "next/link";

type DisclosureBannerProps = {
  text: string;
};

export function DisclosureBanner({ text }: DisclosureBannerProps) {
  return (
    <aside
      aria-label="Affiliate disclosure"
      data-testid="affiliate-disclosure"
      className="rounded-md border border-line border-l-4 border-l-accent bg-callout px-4 py-3 text-xs leading-relaxed text-ink"
    >
      <span className="font-semibold uppercase tracking-wide text-accent">
        Affiliate Disclosure:{" "}
      </span>
      <span>{text}</span>{" "}
      <Link
        href="/affiliate-disclosure"
        className="font-medium text-accent underline underline-offset-2 hover:text-accent-hover"
      >
        Learn more
      </Link>
    </aside>
  );
}
