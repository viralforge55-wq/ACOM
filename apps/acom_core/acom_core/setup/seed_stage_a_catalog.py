"""Seeds the Stage A curated Amazon India kitchen products into ERPNext.

Run via bench:
    bench --site acom.localhost execute acom_core.setup.seed_stage_a_catalog.seed_catalog
"""

from __future__ import annotations

import frappe
from frappe.utils import nowdate


STAGE_A_PRODUCTS = [
  {
    "slug": "automatic-electric-water-dispenser-pump",
    "product_name": "Automatic Wireless Water Dispenser Pump for 20 Litre Bottle (USB Rechargeable)",
    "product_sku": "B0HL4P1CW1",
    "category": "Kitchen Appliances",
    "display_price": 229.00,
    "commission_rate": 9.0,
    "affiliate_url": "https://www.amazon.in/dp/B0HL4P1CW1?tag=acom0a7-21",
    "short_description": "Wireless automatic drinking water pump with one-touch button for hassle-free dispensing from 20-liter water cans.",
    "long_description": "No more heavy lifting, spilling, or manual pumping from heavy 20-liter water jars. Features food-grade silicone tubing and durable battery life.",
  },
  {
    "slug": "12-in-1-vegetable-chopper-slicer",
    "product_name": "Ganesh 14-in-1 Multipurpose Vegetable & Fruit Chopper with Stainless Steel Blades",
    "product_sku": "B01BVDS1BE",
    "category": "Kitchen Tools",
    "display_price": 679.00,
    "commission_rate": 9.0,
    "affiliate_url": "https://www.amazon.in/dp/B01BVDS1BE?tag=acom0a7-21",
    "short_description": "The ultimate Indian kitchen prep station for quick dicing, slicing, and chopping of onions, tomatoes, and vegetables.",
    "long_description": "Save up to 70% of meal prep time with this multipurpose vegetable chopper. Features 14 stainless steel blades and catch container.",
  },
  {
    "slug": "2-in-1-spray-pour-oil-dispenser-bottle",
    "product_name": "2-in-1 Dual-Mode Glass Oil Dispenser & Sprayer for Kitchen (500ml)",
    "product_sku": "B0HKMZRTKG",
    "category": "Kitchenware",
    "display_price": 189.00,
    "commission_rate": 9.0,
    "affiliate_url": "https://www.amazon.in/dp/B0HKMZRTKG?tag=acom0a7-21",
    "short_description": "Dual-function leakproof glass oil container with precision spray nozzle for air frying, tawa cooking, and salads.",
    "long_description": "Upgrade to healthier cooking with this 2-in-1 glass oil dispenser. Seamlessly switch between fine mist and stream pour.",
  },
  {
    "slug": "pigeon-amaze-plus-electric-kettle-1-5l",
    "product_name": "Pigeon by Stovekraft Amaze Plus 1.5L Stainless Steel Electric Kettle",
    "product_sku": "B07WMS7TWB",
    "category": "Kitchen Appliances",
    "display_price": 489.00,
    "commission_rate": 9.0,
    "affiliate_url": "https://www.amazon.in/dp/B07WMS7TWB?tag=acom0a7-21",
    "short_description": "Classic stainless steel electric kettle with automatic shut-off and rapid 1500W boiling for tea, coffee, and noodles.",
    "long_description": "India's best-selling electric kettle. 1500W rapid boiling, 360-degree swivel cordless base, and dry boil safety protection.",
  },
  {
    "slug": "pigeon-handy-compact-vegetable-chopper",
    "product_name": "Pigeon Handy and Compact 3-Blade Manual Vegetable Chopper (400ml)",
    "product_sku": "B01LWYDEQ7",
    "category": "Kitchen Tools",
    "display_price": 262.00,
    "commission_rate": 9.0,
    "affiliate_url": "https://www.amazon.in/dp/B01LWYDEQ7?tag=acom0a7-21",
    "short_description": "India's best-selling pull-cord mini vegetable chopper for instantaneous dicing of onions, garlic, and chillies without tears.",
    "long_description": "Over 200,000+ ratings on Amazon India. Effortless 3-blade pull-cord chopper requires zero electricity and washes in seconds.",
  },
]


def ensure_affiliate_network() -> str:
    network_name = "Amazon India"
    if not frappe.db.exists("Affiliate Network", network_name):
        doc = frappe.get_doc({
            "doctype": "Affiliate Network",
            "network_name": network_name,
            "slug": "amazon-in",
            "program_type": "Marketplace",
            "status": "Active",
            "tracking_param": "tag",
            "cookie_window_days": 1,
            "payout_cycle": "Monthly",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    else:
        doc = frappe.get_doc("Affiliate Network", network_name)
        if doc.status != "Active" or doc.tracking_param != "tag":
            doc.status = "Active"
            doc.tracking_param = "tag"
            doc.save(ignore_permissions=True)
            frappe.db.commit()
    return network_name


def ensure_item_group(name: str) -> str:
    if frappe.db.exists("Item Group", name):
        return name
    parent = "All Item Groups"
    if not frappe.db.exists("Item Group", parent):
        parent = frappe.db.get_value("Item Group", {"is_group": 1}, "name") or ""
    ig = frappe.get_doc({
        "doctype": "Item Group",
        "item_group_name": name,
        "parent_item_group": parent,
        "is_group": 0,
    })
    ig.insert(ignore_permissions=True)
    frappe.db.commit()
    return name


def seed_catalog() -> list[str]:
    network = ensure_affiliate_network()
    today = nowdate()
    seeded = []

    for item in STAGE_A_PRODUCTS:
        ensure_item_group(item["category"])

        existing_name = frappe.db.get_value("Affiliate Product", {"slug": item["slug"]}, "name")
        if existing_name:
            doc = frappe.get_doc("Affiliate Product", existing_name)
            doc.product_name = item["product_name"]
            doc.product_sku = item["product_sku"]
            doc.category = item["category"]
            doc.display_price = item["display_price"]
            doc.commission_rate = item["commission_rate"]
            doc.commission_type = "Percentage"
            doc.affiliate_url = item["affiliate_url"]
            doc.short_description = item["short_description"]
            doc.long_description = item["long_description"]
            doc.disclosure_required = 1
            doc.content_review_status = "Approved"
            doc.last_verified_date = today
            doc.status = "Published"
            doc.save(ignore_permissions=True)
            seeded.append(f"Updated {doc.name} ({item['slug']})")
        else:
            doc = frappe.get_doc({
                "doctype": "Affiliate Product",
                "product_name": item["product_name"],
                "slug": item["slug"],
                "product_sku": item["product_sku"],
                "category": item["category"],
                "affiliate_network": network,
                "display_price": item["display_price"],
                "currency": "INR",
                "commission_rate": item["commission_rate"],
                "commission_type": "Percentage",
                "affiliate_url": item["affiliate_url"],
                "short_description": item["short_description"],
                "long_description": item["long_description"],
                "disclosure_required": 1,
                "content_review_status": "Approved",
                "last_verified_date": today,
                "status": "Published",
            })
            doc.insert(ignore_permissions=True)
            seeded.append(f"Created {doc.name} ({item['slug']})")

    frappe.db.commit()
    return seeded
