"""ACOM Analytics Module.

Provides read-only aggregations, business intelligence, executive summaries,
and drill-through reporting for the CEO and management team.
Strict one-way dependency: analytics may read from all acom_core modules;
no other module may import from analytics (ARCHITECTURE_RULES §3).
"""

from __future__ import annotations
