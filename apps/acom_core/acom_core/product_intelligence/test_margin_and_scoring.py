"""Unit tests for Product Intelligence margin & scoring (TEST_PLAN.md M1–M7)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from frappe.tests import UnitTestCase

from acom_core.product_intelligence.margin import calculate_contribution_profit
from acom_core.product_intelligence.scoring import (
    calculate_product_score,
    calculate_supplier_reliability,
)


class TestMarginAndScoring(UnitTestCase):
    def test_M1_standard_product_matches_hand_calculation_to_paisa(self) -> None:
        # selling_price = 1000.00
        # supplier_cost = 450.00
        # shipping_cost = 80.00
        # packaging_cost = 20.00
        # payment_fee = 1000 * 2.5% = 25.00
        # return_cost = 1000 * 5% * 1.0 = 50.00
        # profit = 1000 - 450 - 80 - 20 - 25 - 50 = 375.00 (37.50%)
        res = calculate_contribution_profit(
            selling_price="1000.00",
            supplier_cost="450.00",
            shipping_cost="80.00",
            packaging_cost="20.00",
            payment_fee_percent="2.5",
            expected_return_rate="5",
            return_cost_factor="1.0",
        )
        self.assertEqual(res.payment_fee_amount, Decimal("25.00"))
        self.assertEqual(res.expected_return_cost, Decimal("50.00"))
        self.assertEqual(res.contribution_profit, Decimal("375.00"))
        self.assertEqual(res.contribution_margin_pct, Decimal("37.50"))
        self.assertTrue(res.can_publish)

    def test_M2_zero_selling_price_raises_validation_error_no_div_zero(self) -> None:
        with self.assertRaises(ValueError):
            calculate_contribution_profit(
                selling_price="0",
                supplier_cost="100",
                shipping_cost="50",
            )
        with self.assertRaises(ValueError):
            calculate_contribution_profit(
                selling_price="-10",
                supplier_cost="100",
                shipping_cost="50",
            )

    def test_M3_negative_contribution_blocks_publish(self) -> None:
        res = calculate_contribution_profit(
            selling_price="500.00",
            supplier_cost="450.00",
            shipping_cost="80.00",
            packaging_cost="20.00",
            payment_fee_percent="2.0",
            expected_return_rate="5.0",
        )
        self.assertLess(res.contribution_profit, Decimal("0.00"))
        self.assertEqual(res.contribution_profit, Decimal("-85.00"))
        self.assertFalse(res.can_publish)

    def test_M4_gst_excluded_from_contribution_profit(self) -> None:
        base = calculate_contribution_profit(
            selling_price="1299.00",
            supplier_cost="600.00",
            shipping_cost="75.00",
            packaging_cost="15.00",
            payment_fee_percent="2.0",
            expected_return_rate="4.0",
            gst_rate="0",
        )
        with_gst = calculate_contribution_profit(
            selling_price="1299.00",
            supplier_cost="600.00",
            shipping_cost="75.00",
            packaging_cost="15.00",
            payment_fee_percent="2.0",
            expected_return_rate="4.0",
            gst_rate="18",
        )
        self.assertEqual(base.contribution_profit, with_gst.contribution_profit)
        self.assertEqual(base.contribution_margin_pct, with_gst.contribution_margin_pct)

    def test_M5_return_rate_zero_vs_20_percent_differs_by_exact_return_cost(self) -> None:
        r0 = calculate_contribution_profit(
            selling_price="1000.00",
            supplier_cost="400.00",
            shipping_cost="50.00",
            expected_return_rate="0",
            return_cost_factor="1.0",
        )
        r20 = calculate_contribution_profit(
            selling_price="1000.00",
            supplier_cost="400.00",
            shipping_cost="50.00",
            expected_return_rate="20",
            return_cost_factor="1.0",
        )
        self.assertEqual(r0.contribution_profit - r20.contribution_profit, Decimal("200.00"))
        self.assertEqual(r20.expected_return_cost, Decimal("200.00"))

    def test_M6_score_bounds_weights_and_clamping_0_to_100(self) -> None:
        # Supplier reliability upper/lower bounds
        perfect = calculate_supplier_reliability(
            orders_received=100,
            orders_fulfilled=100,
            orders_cancelled=0,
            orders_returned=0,
            avg_dispatch_hours=24,
            quality_issues=0,
        )
        self.assertEqual(perfect.reliability_score, Decimal("100.00"))
        self.assertEqual(perfect.dispatch_penalty, Decimal("0"))

        terrible = calculate_supplier_reliability(
            orders_received=100,
            orders_fulfilled=50,
            orders_cancelled=50,
            orders_returned=30,
            avg_dispatch_hours=200,
            quality_issues=25,
        )
        self.assertEqual(terrible.reliability_score, Decimal("0.00"))
        self.assertEqual(terrible.dispatch_penalty, Decimal("15.00"))

        # Product score clamping & exact weights
        high = calculate_product_score(
            margin_score=150,
            demand_score=120,
            competition_score=110,
            supplier_reliability=130,
        )
        self.assertEqual(high.score, Decimal("100.00"))
        self.assertFalse(high.is_incomplete)

        low = calculate_product_score(
            margin_score=-20,
            demand_score=-10,
            competition_score=0,
            supplier_reliability=0,
        )
        self.assertEqual(low.score, Decimal("0.00"))

        exact = calculate_product_score(
            margin_score=80,        # 0.35 -> 28
            demand_score=60,        # 0.30 -> 18
            competition_score=40,   # 0.15 -> 6
            supplier_reliability=90,  # 0.20 -> 18  => total 70.00
        )
        self.assertEqual(exact.score, Decimal("70.00"))
        self.assertFalse(exact.is_incomplete)

    def test_M7_missing_supplier_reliability_computes_and_flags_incomplete(self) -> None:
        res = calculate_product_score(
            margin_score=80,       # weight 0.35 / 0.80 = 0.4375 -> 35.0
            demand_score=60,       # weight 0.30 / 0.80 = 0.3750 -> 22.5
            competition_score=40,  # weight 0.15 / 0.80 = 0.1875 -> 7.5  => 65.00
            supplier_reliability=None,
        )
        self.assertEqual(res.score, Decimal("65.00"))
        self.assertTrue(res.is_incomplete)
        self.assertEqual(res.missing_factors, ("supplier_reliability",))
