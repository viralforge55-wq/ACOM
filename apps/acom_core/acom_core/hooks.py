"""PROJECT ACOM — Frappe hooks manifest.

Per docs/FRAPPE_AGENT_RULES.md §6:
- hooks.py is a manifest only; no inline logic or multi-line function bodies.
- No wildcard doc_events ("*").
- Every hook target must exist and be importable.
"""

app_name = "acom_core"
app_title = "ACOM Core"
app_publisher = "PROJECT ACOM"
app_description = "Affiliate-first commerce domain app for PROJECT ACOM"
app_email = "founder@acom.local"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

before_install = "acom_core.setup.install.ensure_roles"
after_install = "acom_core.setup.install.after_install"
after_migrate = ["acom_core.setup.install.ensure_roles"]
