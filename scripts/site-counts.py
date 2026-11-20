"""Emit Phase 1 document counts as machine-readable JSON.

Used by scripts/phase1-verify.ps1 before and after a stack restart so the
harness can prove the dummy documents actually survived, rather than just
asserting that they exist.

Run inside the backend container with cwd = the sites directory (Frappe's
file logger resolves "../logs" relative to cwd):

    cd /home/frappe/frappe-bench/sites
    /home/frappe/frappe-bench/env/bin/python /tmp/site-counts.py
"""

from __future__ import annotations

import json
import sys

import frappe

SITE = "acom.localhost"

COUNTED = (
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

SUBMITTED = ("Sales Order", "Purchase Order")


def main() -> int:
    frappe.init(site=SITE, sites_path=".")
    frappe.connect()

    payload: dict = {"site": SITE, "counts": {}, "submitted": {}, "names": {}}

    for dt in COUNTED:
        payload["counts"][dt] = frappe.db.count(dt)

    for dt in SUBMITTED:
        payload["submitted"][dt] = frappe.db.count(dt, {"docstatus": 1})
        payload["names"][dt] = frappe.get_all(
            dt, filters={"docstatus": 1}, pluck="name", order_by="creation asc"
        )

    payload["setup_complete"] = bool(frappe.is_setup_complete())

    print("<<<COUNTS>>>")
    print(json.dumps(payload, indent=2, default=str))
    print("<<<END>>>")

    frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
