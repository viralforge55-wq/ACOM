"""Idempotent Phase 5 synthetic Dropshipping demo seeder.

Creates via Frappe ORM (zero raw SQL):
- ERPNext Supplier (`ACOM Demo Direct Supplier`)
- ERPNext Item (`ACOM-DS-001`, Bamboo Travel Cutlery Set, HSN 847130)
- ERPNext Item Price (`Standard Selling`, INR 549.00)
- Published Dropshipping Product (`acom-demo-bamboo-cutlery-set`, stock 25)
- Demo test customer user (`demo_customer@acom.local`, role Customer) for storefront checkout testing
"""

from __future__ import annotations

import json
import os
import sys

import frappe
from frappe.utils import now_datetime
from frappe.utils.password import update_password

SITE = "acom.localhost"
SUPPLIER_NAME = "ACOM Demo Direct Supplier"
ITEM_CODE = "ACOM-DS-001"
DS_SLUG = "acom-demo-bamboo-cutlery-set"
DEMO_CUSTOMER_EMAIL = "demo_customer@acom.local"


def main() -> int:
    frappe.init(site=SITE, sites_path=".")
    frappe.connect()
    frappe.set_user("Administrator")

    if not frappe.db.exists("Supplier", SUPPLIER_NAME):
        sup_group = (
            frappe.db.get_value("Supplier Group", {"is_group": 0}, "name", order_by="name asc")
            or "Services"
        )
        frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": SUPPLIER_NAME,
                "supplier_group": sup_group,
                "country": "India",
            }
        ).insert(ignore_permissions=True)

    category = (
        frappe.db.get_value("Item Group", {"name": "Products"}, "name")
        or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    )

    if not frappe.db.exists("Item", ITEM_CODE):
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": ITEM_CODE,
                "item_name": "ACOM Demo Bamboo Travel Cutlery Set",
                "item_group": category,
                "stock_uom": "Nos",
                "standard_rate": 549.00,
                "gst_hsn_code": "847130",
                "is_stock_item": 1,
                "description": "Synthetic demo dropshipping item for Phase 5 verification.",
            }
        ).insert(ignore_permissions=True)

    existing_price = frappe.db.get_value(
        "Item Price",
        {"item_code": ITEM_CODE, "price_list": "Standard Selling", "selling": 1},
        "name",
    )
    if existing_price:
        frappe.db.set_value("Item Price", existing_price, "price_list_rate", 549.00)
    else:
        frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": ITEM_CODE,
                "price_list": "Standard Selling",
                "selling": 1,
                "currency": "INR",
                "price_list_rate": 549.00,
            }
        ).insert(ignore_permissions=True)

    if not frappe.db.exists("Dropshipping Product", {"slug": DS_SLUG}):
        frappe.get_doc(
            {
                "doctype": "Dropshipping Product",
                "product_name": "ACOM Demo Bamboo Travel Cutlery Set",
                "slug": DS_SLUG,
                "category": category,
                "erpnext_item": ITEM_CODE,
                "supplier": SUPPLIER_NAME,
                "supplier_sku": "SUP-ACOM-BAMBOO-01",
                "currency": "INR",
                "price_list": "Standard Selling",
                "selling_price": 549.00,
                "supplier_cost": 220.00,
                "shipping_cost": 60.00,
                "packaging_cost": 15.00,
                "payment_fee_percent": 2.0,
                "expected_return_rate": 5.0,
                "hsn_code": "847130",
                "gst_rate": 18.0,
                "supplier_stock": 25,
                "last_stock_sync": now_datetime(),
                "lead_time_days": 3,
                "status": "Published",
                "content_review_status": "Approved",
                "short_description": "Reusable bamboo travel cutlery kit with washable cloth pouch.",
                "return_policy_summary": "7-day replacement on damage",
            }
        ).insert(ignore_permissions=True)

    if not frappe.db.exists("User", DEMO_CUSTOMER_EMAIL):
        frappe.get_doc(
            {
                "doctype": "User",
                "email": DEMO_CUSTOMER_EMAIL,
                "first_name": "Demo",
                "last_name": "Customer",
                "enabled": 1,
                "send_welcome_email": 0,
                "roles": [{"role": "Customer"}],
            }
        ).insert(ignore_permissions=True)

    demo_pwd = os.environ.get("ACOM_DEMO_CUSTOMER_PASSWORD")
    if demo_pwd:
        update_password(DEMO_CUSTOMER_EMAIL, demo_pwd)

    frappe.db.commit()

    ds_doc = frappe.get_doc("Dropshipping Product", {"slug": DS_SLUG})
    print(
        json.dumps(
            {
                "dropshipping_product": ds_doc.name,
                "slug": ds_doc.slug,
                "status": ds_doc.status,
                "selling_price": ds_doc.selling_price,
                "contribution_profit": ds_doc.contribution_profit,
                "contribution_margin_pct": ds_doc.contribution_margin_pct,
                "demo_customer": DEMO_CUSTOMER_EMAIL,
            },
            indent=2,
        )
    )
    frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
