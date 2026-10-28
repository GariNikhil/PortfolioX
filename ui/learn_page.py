"""Learn page: short beginner lessons on the stock market.

Static content — the lessons are curated text, not fetched from the
internet (PortfolioX stays offline by default).
"""

import customtkinter as ctk

from ui.theme import *

LESSONS = (
    (
        "What is the stock market?",
        "A stock market is a place where shares of companies are bought "
        "and sold. In India the two main exchanges are NSE and BSE. When "
        "you buy a share you own a small piece of that company, and its "
        "price moves with the company's fortunes and market mood.",
    ),
    (
        "Shares, lots and demat accounts",
        "Shares you buy sit in a demat account (like a bank account for "
        "securities) held through a broker. Equity shares trade in "
        "quantities of 1; F&O contracts trade in fixed lot sizes, e.g. 15 "
        "or 25 per lot for index options.",
    ),
    (
        "Reading a contract note",
        "Every trading day your broker sends a contract note: order no, "
        "trade no, time, security, exchange, B/S flag, quantity, rate and "
        "net total. The net total is what actually left (buys) or arrived "
        "(sells) in your account after charges.",
    ),
    (
        "Order types",
        "A market order executes immediately at the best price; a limit "
        "order executes only at your price or better; a stop-loss turns "
        "into a market order once a trigger price is hit. Choose based on "
        "whether speed or price matters more.",
    ),
    (
        "Futures & options basics",
        "A futures contract is an agreement to buy/sell at a fixed price "
        "on a fixed date. An option gives the right, not the obligation: "
        "a CE (call) profits when prices rise, a PE (put) when they fall. "
        "Options are leveraged — small moves make big percentage swings, "
        "and most contracts expire worthless for buyers.",
    ),
    (
        "Mutual funds vs direct stocks",
        "A mutual fund pools money from many investors and a manager "
        "buys securities with it. SIPs automate monthly investing. Funds "
        "diversify instantly but charge an expense ratio; direct stocks "
        "need your own research but carry no management fee.",
    ),
    (
        "IPOs and bonds",
        "An IPO is a company's first public share sale — apply through "
        "your broker's UPI flow, and allotment is lottery-based for "
        "oversubscribed issues. Bonds are loans you give to a company or "
        "government; they pay interest and return principal at maturity.",
    ),
    (
        "US stocks from India",
        "You can invest in US stocks through LRS (Liberalised Remittance "
        "Scheme) using international brokers. Watch the TCS on "
        "remittances, wire charges, and the fact that gains are taxed in "
        "India as capital gains in USD terms.",
    ),
    (
        "Dividends and taxes",
        "Dividends are paid from company profits and are taxed at your "
        "income-tax slab rate in India. Equity capital gains: short-term "
        "(under 1 year) at 20%, long-term above the annual exempt limit "
        "at 12.5%. F&O profits are taxed as business income.",
    ),
    (
        "Why track XIRR?",
        "XIRR is the single annual rate that makes all your dated "
        "investments and withdrawals equal to your current value. Unlike "
        "absolute profit it accounts for timing, so it is the honest way "
        "to compare a SIP, a lump sum and a trade portfolio.",
    ),
)


class LearnPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="📚 Learn",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Stock-market basics, one short lesson at a time.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        body.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

        for heading, text in LESSONS:
            card = ctk.CTkFrame(body, fg_color=CARD, corner_radius=8)
            card.pack(fill="x", pady=6)

            ctk.CTkLabel(
                card,
                text=heading,
                font=HEADING_FONT,
                text_color=TEXT,
                anchor="w",
            ).pack(fill="x", padx=16, pady=(12, 4))

            ctk.CTkLabel(
                card,
                text=text,
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
                wraplength=900,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 14))
