import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatMoney } from "../../src/lib/format";
import {
  assertNoBannedFields,
  findBannedFields,
  isSafeHttpUrl,
  isValidSlug,
  isValidUuidV4,
  validateClickPayload,
} from "../../src/lib/server/security";

describe("formatMoney", () => {
  it("formats INR string decimals with Indian grouping and exact paisa", () => {
    assert.equal(formatMoney({ amount: "799.00", currency: "INR" }), "₹799.00");
    assert.equal(formatMoney({ amount: "12499.50", currency: "INR" }), "₹12,499.50");
    assert.equal(formatMoney({ amount: "1234567.89", currency: "INR" }), "₹12,34,567.89");
  });

  it("formats USD with standard grouping", () => {
    assert.equal(formatMoney({ amount: "1499.00", currency: "USD" }), "$1,499.00");
  });
});

describe("security banned-field guard", () => {
  it("allows clean public catalog payloads", () => {
    const clean = {
      items: [
        {
          id: "APROD-00001",
          slug: "steel-bottle",
          title: "Steel Bottle",
          sales_type: "AFFILIATE",
          category: { slug: "products", name: "Products" },
          display_price: { amount: "799.00", currency: "INR" },
          marketplace: "Amazon",
          cta_label: "View Deal",
        },
      ],
    };
    assert.deepEqual(findBannedFields(clean), []);
    assert.doesNotThrow(() => assertNoBannedFields(clean));
  });

  it("catches banned fields from DATA_DICTIONARY §13 at any nesting depth", () => {
    const leaky = {
      items: [
        {
          id: "APROD-00001",
          supplier_cost: "400.00",
          nested: {
            commission_rate: 12.5,
            affiliate_url: "https://amazon.in/dp/X?tag=secret",
            owner: "Administrator",
          },
        },
      ],
    };
    const hits = findBannedFields(leaky);
    assert.equal(hits.length, 4);
    assert.throws(() => assertNoBannedFields(leaky), /Security guard blocked banned public fields/);
  });
});

describe("validateClickPayload", () => {
  it("accepts valid anonymous click payloads", () => {
    const res = validateClickPayload({
      product_slug: "acom-demo-steel-bottle-1l",
      session_id: "s_anon_12345678",
      source: "google",
      medium: "organic",
      landing_path: "/products/acom-demo-steel-bottle-1l",
    });
    assert.equal(res.ok, true);
    if (res.ok) {
      assert.equal(res.value.product_slug, "acom-demo-steel-bottle-1l");
      assert.equal(res.value.source, "google");
    }
  });

  it("rejects PII and unknown fields (email, ip_address, price, discount)", () => {
    for (const bad of [
      { product_slug: "valid-slug", session_id: "s_12345678", email: "a@b.com" },
      { product_slug: "valid-slug", session_id: "s_12345678", ip_address: "1.2.3.4" },
      { product_slug: "valid-slug", session_id: "s_12345678", price: "1.00" },
      { product_slug: "valid-slug", session_id: "s_12345678", discount: "99" },
    ]) {
      const res = validateClickPayload(bad);
      assert.equal(res.ok, false);
      if (!res.ok) {
        assert.equal(res.code, "VALIDATION_ERROR");
      }
    }
  });

  it("validates slugs, UUIDv4, and safe redirect URLs", () => {
    assert.equal(isValidSlug("acom-demo-steel-bottle-1l"), true);
    assert.equal(isValidSlug("../etc/passwd"), false);
    assert.equal(isValidUuidV4("3d37ac02-81b3-4e95-aa67-79a34694d75e"), true);
    assert.equal(isValidUuidV4("not-a-uuid"), false);
    assert.equal(isSafeHttpUrl("https://www.amazon.in/dp/B0ACOMDEMO01?tag=acomdemo-21"), true);
    assert.equal(isSafeHttpUrl("javascript:alert(1)"), false);
    assert.equal(isSafeHttpUrl("data:text/html,hi"), false);
  });
});
