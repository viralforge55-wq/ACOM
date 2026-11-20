import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Data minimization and anonymous click telemetry practices on ACOM.",
};

export default function PrivacyPolicyPage() {
  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2 border-b border-line pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Compliance</p>
        <h1 className="font-serif text-3xl font-medium text-ink">Privacy Policy</h1>
      </header>

      <div className="space-y-4 text-sm leading-relaxed text-ink">
        <p>
          ACOM follows a strict data-minimization policy. Browsing the affiliate catalog does not
          require an account, name, email address, or phone number.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">
          What we record on affiliate clicks
        </h2>
        <ul className="list-disc space-y-1.5 pl-5 text-muted">
          <li>A random anonymous session identifier rotated every 30 days (not a device fingerprint).</li>
          <li>The product clicked, server timestamp, coarse browser family (e.g. Chrome, Safari), and allowlisted referral source.</li>
          <li>We do not store IP addresses, email addresses, phone numbers, or full User-Agent strings in our click ledger.</li>
        </ul>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">Retention</h2>
        <p className="text-muted">
          Raw anonymous affiliate click logs are retained for 180 days for attribution reconciliation
          and rate-limit protection, after which they are aggregated and purged.
        </p>

        <h2 className="pt-2 font-serif text-xl font-medium text-ink">External merchants</h2>
        <p className="text-muted">
          Once you are redirected to an external marketplace, that merchant&rsquo;s own privacy
          policy and terms govern your session and purchase.
        </p>
      </div>
    </article>
  );
}
