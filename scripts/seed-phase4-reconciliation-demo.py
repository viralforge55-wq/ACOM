"""Idempotent Phase 4 demo conversion import & reconciliation runner.

Reads the synthetic CSV fixture (tests/fixtures/affiliate_demo_conversions.csv)
and runs it through the real acom_core conversion_service and reconciliation_service
inside the backend container.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import frappe

from acom_core.affiliate_commerce.services.conversion_service import (
    import_affiliate_conversions,
)
from acom_core.affiliate_commerce.services.reconciliation_service import (
    get_reconciliation_summary,
)

SITE = "acom.localhost"
NETWORK = "ACOM Demo Amazon India"
REPORT_DATE = "2026-11-20"


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/affiliate_demo_conversions.csv")
    csv_text = csv_path.read_text(encoding="utf-8")

    frappe.init(site=SITE, sites_path=".")
    frappe.connect()
    frappe.set_user("Administrator")

    first = import_affiliate_conversions(
        network=NETWORK,
        report_date=REPORT_DATE,
        csv_content=csv_text,
        file_name=csv_path.name,
    )
    second = import_affiliate_conversions(
        network=NETWORK,
        report_date=REPORT_DATE,
        csv_content=csv_text,
        file_name=csv_path.name,
    )
    summary = get_reconciliation_summary(affiliate_network=NETWORK)
    frappe.db.commit()

    print(
        json.dumps(
            {
                "first_import": first,
                "duplicate_reimport": second,
                "reconciliation": {
                    "clicks": summary["clicks"],
                    "conversions": summary["conversions"],
                    "commissions": summary["commissions"],
                    "manual_review_queue_count": len(summary["manual_review_queue"]),
                },
            },
            indent=2,
        )
    )
    frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
