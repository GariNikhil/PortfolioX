"""Docked calculator: a basic expression pad plus a profit / loss form.

The panel is a plain frame, so `ui/main_window.py` can place it in a grid
column beside the page host and hide it without losing its state — an open
calculation survives switching pages.

Keys are only bound on the panel's own inputs (the expression entry and the
P&L fields), so typing anywhere else in the app is never intercepted.
Arithmetic lives in `calculations/calculator.py`; this module only deals
with input and display.
"""

import tkinter as tk
from math import isfinite

import customtkinter as ctk

from calculations.calculator import evaluate_expression, profit_loss
from ui.formatting import format_rupees
from ui.theme import *

PANEL_WIDTH = 330

# Keypad layout. "back" is the backspace key; the rest are inserted as-is.
_KEY_ROWS = (
    ("C", "back", "(", ")"),
    ("7", "8", "9", "/"),
    ("4", "5", "6", "*"),
    ("1", "2", "3", "-"),
    ("0", ".", "%", "+"),
)

_KEY_LABELS = {"/": "÷", "*": "×", "-": "−", "back": "⌫"}

_OPERATORS = {"/", "*", "-", "+", "%", "(", ")"}

_TITLE_FONT = (FONT_FAMILY, 18, "bold")
_KEY_FONT = (FONT_FAMILY, 16, "bold")


class CalculatorPanel(ctk.CTkFrame):
    """Calculator docked beside the current page."""

    def __init__(self, parent, on_close=None):
        super().__init__(
            parent, width=PANEL_WIDTH, corner_radius=0, fg_color=CARD
        )
        self._on_close = on_close

        # ---------------- Header ---------------- #

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 0))

        ctk.CTkLabel(
            header,
            text="Calculator",
            font=_TITLE_FONT,
            text_color=TEXT,
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="✕",
            width=28,
            height=28,
            font=SMALL_FONT,
            corner_radius=6,
            fg_color="transparent",
            text_color=TEXT_SECONDARY,
            hover_color=BORDER,
            command=self._close,
        ).pack(side="right")

        # ---------------- Body ---------------- #

        # Scrollable: the keypad plus the P&L form can exceed the height of
        # a short window, and a scrollbar is better than clipped fields.
        body = ctk.CTkScrollableFrame(
            self,
            width=PANEL_WIDTH - 20,
            fg_color=CARD,
            corner_radius=0,
        )
        body.pack(fill="both", expand=True, padx=(10, 4), pady=(6, 10))

        # ---------------- Expression pad ---------------- #

        self._display_var = tk.StringVar()

        self.display = ctk.CTkEntry(
            body,
            textvariable=self._display_var,
            height=46,
            font=(FONT_FAMILY, 20, "bold"),
            justify="right",
            fg_color=SIDEBAR,
            border_color=BORDER,
            text_color=TEXT,
        )
        self.display.pack(fill="x", pady=(2, 4))
        self.display.bind("<Return>", self._on_return)
        self.display.bind("<KP_Enter>", self._on_return)
        self.display.bind("<Escape>", lambda event: self._clear())

        self.result_label = ctk.CTkLabel(
            body,
            text="",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="e",
        )
        self.result_label.pack(fill="x", padx=2)

        keypad = ctk.CTkFrame(body, fg_color="transparent")
        keypad.pack(fill="x", pady=(8, 4))
        for column in range(4):
            keypad.grid_columnconfigure(column, weight=1)

        for row, keys in enumerate(_KEY_ROWS):
            for column, key in enumerate(keys):
                self._keypad_button(keypad, key, row, column)

        self._keypad_button(
            keypad, "=", len(_KEY_ROWS), 0, columnspan=4, accent=True
        )

        # ---------------- Profit / Loss ---------------- #

        ctk.CTkFrame(body, height=1, fg_color=BORDER).pack(
            fill="x", pady=(10, 12)
        )

        ctk.CTkLabel(
            body,
            text="Profit / Loss",
            font=(FONT_FAMILY, 16, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(fill="x")

        fields = ctk.CTkFrame(body, fg_color="transparent")
        fields.pack(fill="x", pady=(8, 4))
        fields.grid_columnconfigure(1, weight=1)

        self.buy_price = self._field(fields, 0, "Buy price", "0")
        self.sell_price = self._field(fields, 1, "Sell price", "0")
        self.quantity = self._field(fields, 2, "Quantity", "1")
        self.buy_charges = self._field(fields, 3, "Buy charges", "0")
        self.sell_charges = self._field(fields, 4, "Sell charges", "0")

        ctk.CTkButton(
            body,
            text="Calculate P&L",
            height=36,
            corner_radius=8,
            font=SMALL_FONT,
            fg_color=ACCENT,
            text_color=SIDEBAR,
            hover_color=SUCCESS,
            command=self._calculate,
        ).pack(fill="x", pady=(10, 8))

        self.pnl_amount = ctk.CTkLabel(
            body,
            text="—",
            font=(FONT_FAMILY, 20, "bold"),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.pnl_amount.pack(fill="x")

        self.pnl_detail = ctk.CTkLabel(
            body,
            text="Enter a buy and sell price.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
            wraplength=PANEL_WIDTH - 60,
        )
        self.pnl_detail.pack(fill="x", pady=(2, 12))

    # ---------------- Expression pad ----------------

    def _keypad_button(self, parent, key, row, column, columnspan=1,
                       accent=False):
        if key == "C":
            colors = (ERROR, TEXT, "#C62828")
        elif accent:
            colors = (ACCENT, SIDEBAR, SUCCESS)
        elif key in _OPERATORS:
            colors = (BORDER, TEXT, "#4A4A4A")
        else:
            colors = (SIDEBAR, TEXT, BORDER)

        button = ctk.CTkButton(
            parent,
            text=_KEY_LABELS.get(key, key),
            height=40,
            corner_radius=8,
            font=_KEY_FONT,
            fg_color=colors[0],
            text_color=colors[1],
            hover_color=colors[2],
            command=lambda value=key: self._press(value),
        )
        button.grid(
            row=row, column=column, columnspan=columnspan,
            sticky="ew", padx=3, pady=3,
        )

    def _press(self, key):
        if key == "C":
            self._clear()
        elif key == "back":
            self._display_var.set(self._display_var.get()[:-1])
            self._focus_display()
        elif key == "=":
            self._evaluate()
        else:
            self._display_var.set(self._display_var.get() + key)
            self._focus_display()

    def _on_return(self, event=None):
        self._evaluate()
        return "break"

    def _evaluate(self):
        try:
            value = evaluate_expression(self._display_var.get())
        except ValueError as error:
            self.result_label.configure(text=str(error), text_color=ERROR)
            return

        text = _format_number(value)
        self._display_var.set(text)
        self.result_label.configure(text=f"= {text}", text_color=TEXT_SECONDARY)
        self._focus_display()

    def _clear(self):
        self._display_var.set("")
        self.result_label.configure(text="", text_color=TEXT_SECONDARY)
        self._focus_display()

    def _focus_display(self):
        self.display.focus_set()
        self.display.icursor("end")

    # ---------------- Profit / Loss ----------------

    def _field(self, parent, row, label, default):
        ctk.CTkLabel(
            parent,
            text=label,
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=row, column=0, sticky="w", pady=3)

        entry = ctk.CTkEntry(
            parent,
            height=30,
            font=SMALL_FONT,
            justify="right",
            fg_color=SIDEBAR,
            border_color=BORDER,
        )
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=3)
        entry.bind("<Return>", lambda event: self._calculate())
        entry.bind("<KP_Enter>", lambda event: self._calculate())
        return entry

    def _calculate(self):
        try:
            result = profit_loss(
                _number(self.buy_price.get(), "Buy price"),
                _number(self.sell_price.get(), "Sell price"),
                _number(self.quantity.get(), "Quantity"),
                _number(self.buy_charges.get() or "0", "Buy charges"),
                _number(self.sell_charges.get() or "0", "Sell charges"),
            )
        except ValueError as error:
            self.pnl_amount.configure(text="—", text_color=TEXT_SECONDARY)
            self.pnl_detail.configure(text=str(error), text_color=ERROR)
            return

        colour = SUCCESS if result.profit_loss >= 0 else ERROR
        percent = (
            "—" if result.percent is None else f"{result.percent:+.2f}%"
        )
        self.pnl_amount.configure(
            text=format_rupees(result.profit_loss), text_color=colour
        )
        self.pnl_detail.configure(
            text=(
                f"Invested {format_rupees(result.cost)}  ·  "
                f"Proceeds {format_rupees(result.proceeds)}\n"
                f"Return {percent}  ·  Breakeven "
                f"{format_rupees(result.breakeven_price)} per unit"
            ),
            text_color=TEXT_SECONDARY,
        )

    # ---------------- Close ----------------

    def _close(self):
        if self._on_close is not None:
            self._on_close()


class CalculatorIconButton(ctk.CTkFrame):
    """Small canvas-drawn calculator icon that toggles the panel.

    A canvas is used instead of an emoji glyph because emoji rendering in
    Tk is inconsistent across Windows builds. ``set_active`` highlights
    the outline while the panel is open.
    """

    def __init__(self, parent, command=None, size=30):
        super().__init__(
            parent, width=size + 4, height=size + 2,
            fg_color="transparent",
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        self._command = command
        self._size = size
        self._hover = False
        self._active = False

        self._canvas = tk.Canvas(
            self,
            width=size,
            height=size,
            bg=BACKGROUND,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._canvas.pack(expand=True)

        for widget in (self, self._canvas):
            widget.bind("<Button-1>", self._clicked)
            widget.bind("<Enter>", self._entered)
            widget.bind("<Leave>", self._left)

        self._draw_icon()

    def set_active(self, active):
        self._active = bool(active)
        self._draw_icon()

    def _draw_icon(self):
        size = self._size
        self._canvas.delete("all")

        if self._active:
            outline = ACCENT
        elif self._hover:
            outline = TEXT
        else:
            outline = TEXT_SECONDARY

        # Body and screen.
        self._canvas.create_rectangle(
            4, 2, size - 4, size - 2, outline=outline, width=1.5
        )
        self._canvas.create_rectangle(
            8, size - 25, size - 8, size - 20, fill=ACCENT, outline=""
        )

        # 3 x 3 keypad below the screen.
        for row in range(3):
            for column in range(3):
                x = 8 + column * 6
                y = size - 17 + row * 5
                self._canvas.create_rectangle(
                    x, y, x + 4, y + 3, fill=TEXT_SECONDARY, outline=""
                )

    def _entered(self, event=None):
        self._hover = True
        self._draw_icon()

    def _left(self, event=None):
        self._hover = False
        self._draw_icon()

    def _clicked(self, event=None):
        if self._command is not None:
            self._command()


def _format_number(value):
    """Trim float noise: 0.30000000000000004 -> '0.3'."""

    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.12g}"


def _number(text, field):
    text = str(text or "").strip().replace(",", "")
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{field} must be a number") from None
    if not isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return value
