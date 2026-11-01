"""Small calculator helpers: expression evaluation and profit / loss.

Both are pure functions with no Tk or database imports, so they can be
unit-tested without a display. The expression evaluator walks the Python
AST and accepts only numeric literals and arithmetic operators — it never
calls ``eval()``, so a pasted string cannot reach names, attributes or
function calls.
"""

import ast
import operator
from dataclasses import dataclass
from math import isfinite

# Anything larger is almost certainly a mistyped power, not a real result.
_MAX_ABS_RESULT = 1e100

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_DIVISION = (operator.truediv, operator.floordiv, operator.mod)


def evaluate_expression(expression):
    """Evaluate a basic arithmetic expression and return a float.

    Supports ``+ - * / // % **``, unary signs and parentheses. Commas are
    ignored so a grouped number such as ``1,20,000`` can be pasted in.
    Anything else — names, calls, attribute access — raises ``ValueError``
    instead of being evaluated.
    """

    text = str(expression or "").strip().replace(",", "")
    if not text:
        raise ValueError("Enter an expression")

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise ValueError("Invalid expression") from None

    result = _evaluate(tree.body)
    if not isfinite(result) or abs(result) > _MAX_ABS_RESULT:
        raise ValueError("Result is too large")
    return result


def _evaluate(node):
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Only numbers and arithmetic are supported")
        number = float(value)
        if not isfinite(number):
            raise ValueError("Only finite numbers are supported")
        return number

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        operation = _BINARY_OPERATORS[type(node.op)]
        if operation in _DIVISION and right == 0:
            raise ValueError("Cannot divide by zero")
        try:
            result = operation(left, right)
        except OverflowError:
            raise ValueError("Result is too large") from None
        except (ArithmeticError, ValueError):
            raise ValueError("Invalid arithmetic") from None
        if not isfinite(result):
            raise ValueError("Result is too large")
        return result

    raise ValueError("Only numbers and arithmetic are supported")


@dataclass(frozen=True)
class ProfitLoss:
    """The money result of one buy → sell round trip."""

    quantity: float
    buy_price: float
    sell_price: float
    buy_charges: float
    sell_charges: float
    cost: float
    proceeds: float
    profit_loss: float
    percent: float | None
    breakeven_price: float | None


def profit_loss(buy_price, sell_price, quantity=1, buy_charges=0, sell_charges=0):
    """Return the profit or loss of buying and selling ``quantity`` units.

    ``cost`` is the buy value plus buy charges; ``proceeds`` is the sell
    value minus sell charges. ``percent`` is the return on cost (``None``
    when cost is zero), and ``breakeven_price`` is the per-unit sell price
    that would make the result exactly zero.
    """

    quantity = _positive(quantity, "Quantity")
    buy_price = _amount(buy_price, "Buy price")
    sell_price = _amount(sell_price, "Sell price")
    buy_charges = _amount(buy_charges, "Buy charges")
    sell_charges = _amount(sell_charges, "Sell charges")

    cost = buy_price * quantity + buy_charges
    proceeds = sell_price * quantity - sell_charges
    result = proceeds - cost

    return ProfitLoss(
        quantity=quantity,
        buy_price=buy_price,
        sell_price=sell_price,
        buy_charges=buy_charges,
        sell_charges=sell_charges,
        cost=cost,
        proceeds=proceeds,
        profit_loss=result,
        percent=(result / cost * 100) if cost > 0 else None,
        breakeven_price=(cost + sell_charges) / quantity,
    )


def _amount(value, field):
    number = _number(value, field)
    if number < 0:
        raise ValueError(f"{field} cannot be negative")
    return number


def _positive(value, field):
    number = _number(value, field)
    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number


def _number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number") from None
    if not isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number
