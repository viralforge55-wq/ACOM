"""PROJECT ACOM - Phase 1 dummy data seeder.

Idempotent. Uses the Frappe ORM and ERPNext's own setup-wizard entry point;
contains no raw SQL and touches no ERPNext/Frappe core files.

Why the setup wizard: `bench new-site --install-app erpnext` installs the
schema and runs `after_install`, but the Company, chart of accounts, UOMs,
Item Groups and default Warehouse are created by the *setup wizard*. Calling
`setup_complete` is the same code path the Desk UI uses, so the resulting
site is a normal, fully-initialised ERPNext site rather than a hand-patched one.

Run inside the backend container (cwd must be the sites dir - Frappe's file
logger resolves "../logs" relative to cwd):

    cd /home/frappe/frappe-bench/sites
    ACOM_SEED_PASSWORD=... /home/frappe/frappe-bench/env/bin/python /tmp/seed.py
"""

from __future__ import annotations

import json
import os
import sys

import frappe
from frappe.utils import add_days, nowdate

SITE = "acom.localhost"

COMPANY_NAME = "ACOM Demo Company"
COMPANY_ABBR = "ACOMD"
COUNTRY = "India"
CURRENCY = "INR"
TIMEZONE = "Asia/Kolkata"
DOMAIN = "Distribution"
CHART_OF_ACCOUNTS = "Standard"

CUSTOMER = "ACOM Demo Customer"
SUPPLIER = "ACOM Demo Supplier"

ITEMS = [
    {
        "item_code": "ACOM-DEMO-001",
        "item_name": "ACOM Demo Widget",
        "item_group": "Products",
        "stock_uom": "Nos",
        "standard_rate": 1500.0,
        "gst_hsn_code": "847130",
        "description": "Phase 1 dummy item - widget",
    },
    {
        "item_code": "ACOM-DEMO-002",
        "item_name": "ACOM Demo Gadget",
        "item_group": "Products",
        "stock_uom": "Nos",
        "standard_rate": 2750.0,
        "gst_hsn_code": "847130",
        "description": "Phase 1 dummy item - gadget",
    },
]

SO_MARKER = "ACOM-PHASE1-SO"
PO_MARKER = "ACOM-PHASE1-PO"


def log(msg: str) -> None:
    print(f"[seed] {msg}", flush=True)


def run_setup_wizard() -> None:
    """Initialise the site exactly as the Desk setup wizard would."""
    if frappe.is_setup_complete():
        log("setup wizard already complete - skipping")
        return

    password = os.environ.get("ACOM_SEED_PASSWORD")
    if not password:
        raise RuntimeError("ACOM_SEED_PASSWORD is required to initialise the site")

    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

    log("running setup wizard (country=%s, company=%s)" % (COUNTRY, COMPANY_NAME))
    result = setup_complete(
        {
            "language": "English",
            "country": COUNTRY,
            "timezone": TIMEZONE,
            "currency": CURRENCY,
            "enable_telemetry": 0,
            "full_name": "ACOM Founder",
            "email": os.environ.get("ACOM_SEED_EMAIL", "founder@acom.local"),
            "password": password,
            "company_name": COMPANY_NAME,
            "company_abbr": COMPANY_ABBR,
            "company_tagline": "AI-driven commerce, one founder and agents",
            "domain": DOMAIN,
            "chart_of_accounts": CHART_OF_ACCOUNTS,
            "fy_start_date": "2026-04-01",
            "fy_end_date": "2027-03-31",
        }
    )
    log(f"setup wizard result: {result}")
    frappe.db.commit()
    frappe.clear_cache()


def ensure_company() -> str:
    name = frappe.db.get_value("Company", {"company_name": COMPANY_NAME}, "name")
    if not name:
        # Only reached if the wizard was skipped on an older site.
        doc = frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": COMPANY_NAME,
                "abbr": COMPANY_ABBR,
                "country": COUNTRY,
                "default_currency": CURRENCY,
                "create_chart_of_accounts_based_on": "Standard Template",
                "chart_of_accounts": CHART_OF_ACCOUNTS,
                "domain": DOMAIN,
            }
        )
        doc.insert(ignore_permissions=True)
        name = doc.name
        log(f"created company {name}")
    else:
        log(f"company exists: {name}")
    return name


def ensure_item(item: dict) -> str:
    if frappe.db.exists("Item", item["item_code"]):
        log(f"item exists: {item['item_code']}")
        return item["item_code"]

    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "stock_uom": item["stock_uom"],
            "standard_rate": item["standard_rate"],
            "gst_hsn_code": item["gst_hsn_code"],
            "description": item["description"],
            "is_stock_item": 1,
            "include_item_in_manufacturing": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    log(f"created item {doc.name}")
    return doc.name


def pick_leaf_group(doctype: str, fallback: str) -> str:
    """Return a non-group record: ERPNext rejects group nodes on party/item docs."""
    name = frappe.db.get_value(doctype, {"is_group": 0}, "name", order_by="name asc")
    return name or fallback


def ensure_customer() -> str:
    if frappe.db.exists("Customer", CUSTOMER):
        log(f"customer exists: {CUSTOMER}")
        return CUSTOMER
    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": CUSTOMER,
            "customer_type": "Company",
            "customer_group": pick_leaf_group("Customer Group", "Commercial"),
            "territory": "India",
        }
    )
    doc.insert(ignore_permissions=True)
    log(f"created customer {doc.name}")
    return doc.name


def ensure_supplier() -> str:
    if frappe.db.exists("Supplier", SUPPLIER):
        log(f"supplier exists: {SUPPLIER}")
        return SUPPLIER
    doc = frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": SUPPLIER,
            "supplier_group": pick_leaf_group("Supplier Group", "Services"),
            "country": COUNTRY,
        }
    )
    doc.insert(ignore_permissions=True)
    log(f"created supplier {doc.name}")
    return doc.name


def default_warehouse(company: str) -> str:
    warehouse = frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0}, "name", order_by="creation asc"
    )
    if not warehouse:
        raise RuntimeError(f"no warehouse found for company {company}")
    return warehouse


def ensure_sales_order(company: str, customer: str, warehouse: str) -> str:
    existing = frappe.db.get_value(
        "Sales Order", {"customer": customer, "docstatus": 1}, "name", order_by="creation asc"
    )
    if existing:
        log(f"submitted sales order exists: {existing}")
        return existing

    so = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "customer": customer,
            "company": company,
            "transaction_date": nowdate(),
            "delivery_date": add_days(nowdate(), 7),
            "po_no": SO_MARKER,
            "order_type": "Sales",
            "currency": CURRENCY,
            "selling_price_list": "Standard Selling",
            "items": [
                {
                    "item_code": ITEMS[0]["item_code"],
                    "qty": 2,
                    "rate": ITEMS[0]["standard_rate"],
                    "warehouse": warehouse,
                    "delivery_date": add_days(nowdate(), 7),
                }
            ],
        }
    )
    so.insert(ignore_permissions=True)
    so.submit()
    log(f"created + submitted sales order {so.name}")
    return so.name


def ensure_purchase_order(company: str, supplier: str, warehouse: str) -> str:
    existing = frappe.db.get_value(
        "Purchase Order", {"supplier": supplier, "docstatus": 1}, "name", order_by="creation asc"
    )
    if existing:
        log(f"submitted purchase order exists: {existing}")
        return existing

    po = frappe.get_doc(
        {
            "doctype": "Purchase Order",
            "supplier": supplier,
            "company": company,
            "transaction_date": nowdate(),
            "schedule_date": add_days(nowdate(), 7),
            "order_confirmation_no": PO_MARKER,
            "currency": CURRENCY,
            "buying_price_list": "Standard Buying",
            "items": [
                {
                    "item_code": ITEMS[1]["item_code"],
                    "qty": 5,
                    "rate": ITEMS[1]["standard_rate"] * 0.6,
                    "warehouse": warehouse,
                    "schedule_date": add_days(nowdate(), 7),
                }
            ],
        }
    )
    po.insert(ignore_permissions=True)
    po.submit()
    log(f"created + submitted purchase order {po.name}")
    return po.name


def main() -> int:
    # cwd must be the sites dir: Frappe's RotatingFileHandler opens
    # "../logs/<module>.log" relative to the process cwd.
    frappe.init(site=SITE, sites_path=".")
    frappe.connect()
    frappe.set_user("Administrator")

    summary: dict = {"site": SITE}

    run_setup_wizard()

    company = ensure_company()
    summary["company"] = company

    for item in ITEMS:
        ensure_item(item)
    summary["items"] = [i["item_code"] for i in ITEMS]

    customer = ensure_customer()
    supplier = ensure_supplier()
    warehouse = default_warehouse(company)
    summary.update({"customer": customer, "supplier": supplier, "warehouse": warehouse})

    summary["sales_order"] = ensure_sales_order(company, customer, warehouse)
    summary["purchase_order"] = ensure_purchase_order(company, supplier, warehouse)

    frappe.db.commit()

    summary["counts"] = {
        dt: frappe.db.count(dt)
        for dt in (
            "Company",
            "Item",
            "Item Group",
            "UOM",
            "Warehouse",
            "Customer",
            "Supplier",
            "Sales Order",
            "Purchase Order",
        )
    }
    summary["setup_complete"] = frappe.is_setup_complete()

    print("<<<SEED>>>")
    print(json.dumps(summary, indent=2, default=str))
    print("<<<END>>>")

    frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
