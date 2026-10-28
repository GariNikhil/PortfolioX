"""
PortfolioX Theme
Central place for colors, fonts and UI constants.
"""

import customtkinter as ctk

# ------------------------
# Appearance
# ------------------------

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ------------------------
# Colors
# ------------------------

BACKGROUND = "#1E1E1E"
SIDEBAR = "#252526"
CARD = "#2D2D30"

ACCENT = "#00C853"

TEXT = "#FFFFFF"
TEXT_SECONDARY = "#B0B0B0"

SUCCESS = "#00C853"
WARNING = "#FFB300"
ERROR = "#E53935"

BORDER = "#3A3A3A"

# ------------------------
# Fonts
# ------------------------

FONT_FAMILY = "Segoe UI"

TITLE_FONT = (FONT_FAMILY, 30, "bold")
HEADING_FONT = (FONT_FAMILY, 22, "bold")
BODY_FONT = (FONT_FAMILY, 15)
SMALL_FONT = (FONT_FAMILY, 13)

# ------------------------
# Sizes
# ------------------------

SIDEBAR_WIDTH = 240

CARD_WIDTH = 250
CARD_HEIGHT = 120

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 850

PADDING = 20