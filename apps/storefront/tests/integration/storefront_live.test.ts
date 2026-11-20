import { describe, it } from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { findBannedFields } from "../../src/lib/server/security";

const STOREFRONT_URL = (process.env.STOREFRONT_TEST_URL || "http://127.0.0.1:3000").replace(
  /\/+$/,
  "",
);

const PUBLISHED_SLUG = "acom-demo-steel-bottle-1l";
const DRAFT_SLUG = "acom-demo-draft-product";
const RAW_AFFILIATE_TAG = "tag=acomdemo-21";

describe("Phase 3 live storefront integration against ERPNext", () => {
  it("renders Home (/) HTTP 200 with live ERPNext product, hides draft, leaks zero raw URLs or banned fields", async () => {
    const res = await fetch(`${STOREFRONT_URL}/`);
    assert.equal(res.status, 200);
    const html = await res.text();

    assert.match(html, /ACOM Demo Stainless Steel Bottle 1L/);
    assert.match(html, /₹799\.00/);
    assert.match(html, /View Deal/);
    assert.doesNotMatch(html, /ACOM Demo Unpublished Draft Product/);
    assert.doesNotMatch(html, new RegExp(RAW_AFFILIATE_TAG));
    assert.doesNotMatch(html, /supplier_cost|commission_rate|affiliate_url/);
  });

  it("renders Category (/categories/products) HTTP 200 and returns 404 for unknown category", async () => {
    const okRes = await fetch(`${STOREFRONT_URL}/categories/products`);
    assert.equal(okRes.status, 200);
    const html = await okRes.text();
    assert.match(html, /ACOM Demo Stainless Steel Bottle 1L/);

    const missingRes = await fetch(`${STOREFRONT_URL}/categories/does-not-exist-xyz`);
    assert.equal(missingRes.status, 404);
  });

  it("renders Product Detail (/products/acom-demo-steel-bottle-1l) HTTP 200 with visible disclosure and zero raw affiliate URL", async () => {
    const res = await fetch(`${STOREFRONT_URL}/products/${PUBLISHED_SLUG}`);
    assert.equal(res.status, 200);
    const html = await res.text();

    assert.match(html, /ACOM Demo Stainless Steel Bottle 1L/);
    assert.match(html, /Amazon/);
    assert.match(html, /₹799\.00/);
    assert.match(html, /Double-wall insulation/);
    assert.match(html, /Hand wash recommended/);
    assert.match(html, /data-testid="affiliate-disclosure"/);
    assert.match(html, /affiliate partner/i);
    assert.match(html, /View Deal/);
    assert.doesNotMatch(html, new RegExp(RAW_AFFILIATE_TAG));
    assert.doesNotMatch(html, /supplier_cost|commission_rate|affiliate_url/);
  });

  it("returns HTTP 404 for unpublished draft slug and non-existent slug", async () => {
    const draftRes = await fetch(`${STOREFRONT_URL}/products/${DRAFT_SLUG}`);
    assert.equal(draftRes.status, 404);

    const missingRes = await fetch(`${STOREFRONT_URL}/products/non-existent-sku-999`);
    assert.equal(missingRes.status, 404);
  });

  it("serves all four static compliance pages with HTTP 200", async () => {
    for (const path of ["/affiliate-disclosure", "/privacy-policy", "/terms", "/about"]) {
      const res = await fetch(`${STOREFRONT_URL}${path}`);
      assert.equal(res.status, 200, `Expected 200 for ${path}`);
    }
  });

  it("proxies /api/catalog and /api/products/[slug] with zero banned fields and 404 on draft", async () => {
    const catRes = await fetch(`${STOREFRONT_URL}/api/catalog?page=1&page_size=20&sales_type=AFFILIATE`);
    assert.equal(catRes.status, 200);
    const catJson = await catRes.json();
    assert.equal(catJson.ok, true);
    assert.deepEqual(findBannedFields(catJson.data), []);
    assert.equal(JSON.stringify(catJson).includes(RAW_AFFILIATE_TAG), false);

    const prodRes = await fetch(`${STOREFRONT_URL}/api/products/${PUBLISHED_SLUG}`);
    assert.equal(prodRes.status, 200);
    const prodJson = await prodRes.json();
    assert.equal(prodJson.ok, true);
    assert.equal(prodJson.data.sales_type, "AFFILIATE");
    assert.deepEqual(findBannedFields(prodJson.data), []);
    assert.equal(JSON.stringify(prodJson).includes(RAW_AFFILIATE_TAG), false);

    const draftApiRes = await fetch(`${STOREFRONT_URL}/api/products/${DRAFT_SLUG}`);
    assert.equal(draftApiRes.status, 404);
  });

  it("rejects PII/price tampering (400) and draft SKU clicks (422) on POST /api/affiliate/click", async () => {
    const piiRes = await fetch(`${STOREFRONT_URL}/api/affiliate/click`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_slug: PUBLISHED_SLUG,
        session_id: "s_int_pii_0001",
        email: "user@example.com",
      }),
    });
    assert.equal(piiRes.status, 400);
    const piiJson = await piiRes.json();
    assert.equal(piiJson.ok, false);
    assert.equal(piiJson.error.code, "VALIDATION_ERROR");

    const draftClickRes = await fetch(`${STOREFRONT_URL}/api/affiliate/click`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_slug: DRAFT_SLUG,
        session_id: "s_int_draft_0001",
      }),
    });
    assert.equal(draftClickRes.status, 422);
    const draftClickJson = await draftClickRes.json();
    assert.equal(draftClickJson.ok, false);
    assert.equal(draftClickJson.error.code, "PRODUCT_UNAVAILABLE");
  });

  it("records click (201) and resolves GET /go/[click_id] -> HTTP 302 with subid and no-store headers", async () => {
    const sessionId = `s_e2e_${crypto.randomBytes(6).toString("hex")}`;
    const clickRes = await fetch(`${STOREFRONT_URL}/api/affiliate/click`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_slug: PUBLISHED_SLUG,
        session_id: sessionId,
        source: "google",
        medium: "organic",
        landing_path: `/products/${PUBLISHED_SLUG}`,
      }),
    });
    assert.equal(clickRes.status, 201);
    const clickJson = await clickRes.json();
    assert.equal(clickJson.ok, true);
    const { click_id: clickId, redirect_url: redirectUrl } = clickJson.data;
    assert.equal(redirectUrl, `/go/${clickId}`);

    const goRes = await fetch(`${STOREFRONT_URL}${redirectUrl}`, {
      redirect: "manual",
    });
    assert.equal(goRes.status, 302);
    const location = goRes.headers.get("location") || "";
    assert.match(location, /^https:\/\/www\.amazon\.in\/dp\/B0ACOMDEMO01/);
    assert.match(location, /tag=acomdemo-21/);
    assert.match(location, new RegExp(`subid=${clickId}`));
    assert.match(goRes.headers.get("cache-control") || "", /no-store/);
    assert.ok(goRes.headers.get("referrer-policy"));
  });

  it("returns HTTP 404 cleanly on /go/[click_id] for invalid or unknown click IDs", async () => {
    const badRes = await fetch(`${STOREFRONT_URL}/go/not-a-uuid`, { redirect: "manual" });
    assert.equal(badRes.status, 404);

    const missingRes = await fetch(
      `${STOREFRONT_URL}/go/00000000-0000-4000-8000-000000000000`,
      { redirect: "manual" },
    );
    assert.equal(missingRes.status, 404);
  });
});
