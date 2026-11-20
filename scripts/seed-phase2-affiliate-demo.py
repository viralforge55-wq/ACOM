"""Idempotent Phase 2 synthetic demo data seeder for live HTTP verification.

Creates via Frappe ORM (zero raw SQL):
- 1 Active Affiliate Network (`ACOM Demo Amazon India`, tracking_param=`tag`)
- 1 Published Affiliate Product (`acom-demo-steel-bottle-1l`)
- 1 Draft Affiliate Product (`acom-demo-draft-product`) for negative API tests
"""

from __future__ import annotations

import json
import sys

import frappe
from frappe.utils import nowdate

SITE = "acom.localhost"
NETWORK_NAME = "ACOM Demo Amazon India"
PUBLISHED_SLUG = "acom-demo-steel-bottle-1l"
DRAFT_SLUG = "acom-demo-draft-product"


def main() -> int:
    frappe.init(site=SITE, sites_path=".")
    frappe.connect()
    frappe.set_user("Administrator")

    if not frappe.db.exists("Affiliate Network", NETWORK_NAME):
        frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": NETWORK_NAME,
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": "tag",
                "payout_cycle": "Monthly",
                "cookie_window_days": 1,
                "status": "Active",
            }
        ).insert()

    category = (
        frappe.db.get_value("Item Group", {"name": "Products"}, "name")
        or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    )

    if not frappe.db.exists("Affiliate Product", {"slug": PUBLISHED_SLUG}):
        frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "ACOM Demo Stainless Steel Bottle 1L",
                "slug": PUBLISHED_SLUG,
                "product_sku": "B0ACOMDEMO01",
                "marketplace": "Amazon",
                "affiliate_network": NETWORK_NAME,
                "affiliate_url": "https://www.amazon.in/dp/B0ACOMDEMO01?tag=acomdemo-21",
                "canonical_url": "https://www.amazon.in/dp/B0ACOMDEMO01",
                "category": category,
                "commission_type": "Percentage",
                "commission_rate": 9.0,
                "currency": "INR",
                "display_price": 799.00,
                "short_description": "Synthetic demo vacuum-insulated bottle for Phase 2 API verification.",
                "pros": [{"text": "Double-wall insulation", "sort_order": 1}],
                "cons": [{"text": "Hand wash recommended", "sort_order": 1}],
                "status": "Published",
                "last_verified_date": nowdate(),
                "verification_method": "Manual",
                "content_review_status": "Approved",
                "disclosure_required": 1,
            }
        ).insert()

    if not frappe.db.exists("Affiliate Product", {"slug": DRAFT_SLUG}):
        frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "ACOM Demo Unpublished Draft Product",
                "slug": DRAFT_SLUG,
                "product_sku": "B0ACOMDRFT01",
                "marketplace": "Amazon",
                "affiliate_network": NETWORK_NAME,
                "affiliate_url": "https://www.amazon.in/dp/B0ACOMDRFT01?tag=acomdemo-21",
                "category": category,
                "commission_type": "Percentage",
                "commission_rate": 12.0,
                "currency": "INR",
                "display_price": 1499.00,
                "status": "Draft",
                "disclosure_required": 1,
            }
        ).insert()

    frappe.db.commit()

    out = {
        "affiliate_networks": frappe.db.count("Affiliate Network"),
        "affiliate_products": frappe.db.count("Affiliate Product"),
        "published_slug": PUBLISHED_SLUG,
        "draft_slug": DRAFT_SLUG,
    }
    print(json.dumps(out, indent=2))
    frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
