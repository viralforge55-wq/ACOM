"""Core automation workflows (ADR-0002)."""
from acom_core.integration_management.workflows.product_research import run_product_research_flow
from acom_core.integration_management.workflows.content_generation import run_content_generation_flow
from acom_core.integration_management.workflows.supplier_monitor import run_supplier_monitor_flow
from acom_core.integration_management.workflows.order_monitor import run_order_monitor_flow
from acom_core.integration_management.workflows.reconciliation_monitor import run_reconciliation_monitor_flow

__all__ = [
    "run_product_research_flow",
    "run_content_generation_flow",
    "run_supplier_monitor_flow",
    "run_order_monitor_flow",
    "run_reconciliation_monitor_flow",
]
