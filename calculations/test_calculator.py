"""Tests for the calculator's expression evaluator and P&L helper."""

import unittest

from calculations.calculator import evaluate_expression, profit_loss


class ExpressionTests(unittest.TestCase):
    def test_basic_arithmetic_and_precedence(self):
        self.assertEqual(evaluate_expression("2+3*4"), 14)
        self.assertEqual(evaluate_expression("(1+2)*3"), 9)
        self.assertEqual(evaluate_expression("10/4"), 2.5)
        self.assertEqual(evaluate_expression("7//2"), 3)
        self.assertEqual(evaluate_expression("7%2"), 1)
        self.assertEqual(evaluate_expression("2**10"), 1024)

    def test_unary_signs(self):
        self.assertEqual(evaluate_expression("-5+2"), -3)
        self.assertEqual(evaluate_expression("-(2+3)"), -5)
        self.assertEqual(evaluate_expression("+4"), 4)

    def test_decimals_and_grouping_commas(self):
        self.assertEqual(evaluate_expression("0.1 + 0.2"), 0.1 + 0.2)
        self.assertEqual(evaluate_expression("1,20,000 / 2"), 60000)

    def test_whitespace_is_ignored(self):
        self.assertEqual(evaluate_expression("  6 * 7  "), 42)

    def test_empty_expression_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Enter an expression"):
            evaluate_expression("   ")

    def test_invalid_syntax_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid expression"):
            evaluate_expression("1 +")

    def test_division_by_zero_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "divide by zero"):
            evaluate_expression("1/0")

    def test_names_and_calls_are_rejected(self):
        for expression in ("abc", "abs(-1)", "__import__('os')"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    evaluate_expression(expression)

    def test_boolean_literals_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Only numbers"):
            evaluate_expression("True")

    def test_runaway_power_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Result is too large"):
            evaluate_expression("10**400")


class ProfitLossTests(unittest.TestCase):
    def test_profit_on_a_single_share(self):
        result = profit_loss(100, 120)

        self.assertEqual(result.quantity, 1)
        self.assertEqual(result.cost, 100)
        self.assertEqual(result.proceeds, 120)
        self.assertEqual(result.profit_loss, 20)
        self.assertAlmostEqual(result.percent, 20)
        self.assertAlmostEqual(result.breakeven_price, 100)

    def test_loss_reports_a_negative_amount(self):
        result = profit_loss(200, 150, quantity=10)

        self.assertEqual(result.cost, 2000)
        self.assertEqual(result.proceeds, 1500)
        self.assertEqual(result.profit_loss, -500)
        self.assertAlmostEqual(result.percent, -25)

    def test_charges_are_added_to_cost_and_deducted_from_proceeds(self):
        result = profit_loss(
            100, 110, quantity=10, buy_charges=25, sell_charges=15
        )

        self.assertEqual(result.cost, 1025)
        self.assertEqual(result.proceeds, 1085)
        self.assertEqual(result.profit_loss, 60)
        self.assertAlmostEqual(result.percent, 60 / 1025 * 100)

    def test_breakeven_covers_both_sides_of_charges(self):
        result = profit_loss(100, 110, quantity=10, buy_charges=25,
                             sell_charges=15)

        # Selling at breakeven must produce exactly zero.
        zero = profit_loss(100, result.breakeven_price, quantity=10,
                           buy_charges=25, sell_charges=15)
        self.assertAlmostEqual(zero.profit_loss, 0)
        self.assertAlmostEqual(result.breakeven_price, 104)

    def test_zero_cost_has_no_percentage(self):
        result = profit_loss(0, 5, quantity=10)

        self.assertIsNone(result.percent)
        self.assertEqual(result.profit_loss, 50)

    def test_validation(self):
        with self.assertRaisesRegex(ValueError, "Quantity must be greater"):
            profit_loss(100, 120, quantity=0)
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            profit_loss(-1, 120)
        with self.assertRaisesRegex(ValueError, "must be a number"):
            profit_loss("abc", 120)
        with self.assertRaisesRegex(ValueError, "must be a finite"):
            profit_loss(float("nan"), 120)


if __name__ == "__main__":
    unittest.main()
