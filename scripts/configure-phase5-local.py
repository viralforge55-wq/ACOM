"""Provision independent random local-only signing keys without printing secrets.

Run in bench/sites with the bench Python. Values persist in the named sites volume.
Existing keys are retained. This explicitly enables the local payment simulator.
"""
import secrets
import frappe
from frappe.installer import update_site_config

frappe.init(site="acom.localhost", sites_path=".")
for key in ("acom_payment_webhook_secret", "acom_cart_signing_secret"):
    if not frappe.conf.get(key):
        update_site_config(key, secrets.token_hex(32))
update_site_config("acom_payment_mode", "test")
update_site_config("acom_enable_payment_simulator", 1)
print("Independent signing keys configured; test gateway simulator enabled. No secrets printed.")
frappe.destroy()
