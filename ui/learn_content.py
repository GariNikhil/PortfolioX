"""Offline Learn library, distilled from the books in ``referance/books``.

The PDFs and Markdown conversions stay local (``referance/`` is
gitignored). Everything in this module is an original summary written for
PortfolioX: no book text is copied, and nothing is fetched from the
internet. The Learn page reads these constants to build its Lessons,
Book Library, Strategy Playbook and Planning tabs.
"""

from dataclasses import dataclass

LEVELS = ("Beginner", "Intermediate", "Advanced")


@dataclass(frozen=True)
class Track:
    """A reading track that groups books by the question they answer."""

    key: str
    title: str
    blurb: str


TRACKS = (
    Track(
        "foundation",
        "Money foundation",
        "Saving, spending and the money habits that come before picking "
        "investments.",
    ),
    Track(
        "investing",
        "Long-term investing",
        "Index funds, business quality and valuation for money you will "
        "not touch for years.",
    ),
    Track(
        "technical",
        "Chart reading",
        "Trends, patterns and indicators for timing entries and exits.",
    ),
    Track(
        "options",
        "Options & derivatives",
        "Payoffs, Greeks and defined-risk strategies for F&O.",
    ),
    Track(
        "psychology",
        "Decision psychology",
        "Biases, luck and trading behaviour — the part that decides "
        "whether a plan survives a drawdown.",
    ),
)

TRACK_BY_KEY = {track.key: track for track in TRACKS}


@dataclass(frozen=True)
class Book:
    """One book on the shelf, reduced to notes that fit a screen."""

    key: str
    title: str
    short_title: str
    author: str
    year: str
    track: str
    level: str
    file_name: str
    thesis: str
    ideas: tuple[str, ...]
    tricks: tuple[str, ...]
    planning: tuple[str, ...]


BOOKS = (
    Book(
        key="rich-dad",
        title="Rich Dad Poor Dad",
        short_title="Rich Dad Poor Dad",
        author="Robert T. Kiyosaki",
        year="1997",
        track="foundation",
        level="Beginner",
        file_name="Rich Dad Poor Dad eBook.pdf",
        thesis=(
            "The poor and middle class work for money; the rich build "
            "assets that earn money for them. Financial education, not the "
            "salary, decides who gets ahead."
        ),
        ideas=(
            "An asset puts money in your pocket. A liability takes money "
            "out — and a home loan is usually a liability first.",
            "Watch cash flow, not job title: what arrives from assets "
            "versus what leaves for expenses and debt.",
            "Mind your own business: build an investment portfolio "
            "outside your day job.",
            "The four quadrants — employee, self-employed, business owner, "
            "investor — describe how income is earned, not how much.",
        ),
        tricks=(
            "Before a large purchase, ask whether it pays you or you pay "
            "for it every month.",
            "Pay yourself first: move money into assets before lifestyle "
            "spending.",
            "Keep lifestyle costs below income so the asset column can "
            "grow.",
        ),
        planning=(
            "Use the net-worth view to separate income-producing assets "
            "from consumption.",
            "Set a monthly target for money moved into investments, "
            "independent of raises.",
        ),
    ),
    Book(
        key="richest-man",
        title="The Richest Man in Babylon",
        short_title="The Richest Man in Babylon",
        author="George S. Clason",
        year="1926",
        track="foundation",
        level="Beginner",
        file_name="The-Richest-Man-in-Babylon.pdf",
        thesis=(
            "Seven plain laws — save first, control spending, invest, "
            "protect capital, own a home, insure the future, keep learning "
            "— explain most wealth building."
        ),
        ideas=(
            "Start the purse to fattening: keep at least a tenth of "
            "everything you earn.",
            "Control expenditure: decide what each rupee must do before "
            "spending it.",
            "Make gold multiply by investing where principal is reasonably "
            "safe and the return is fair.",
            "Guard treasure from loss: test advice against the experience "
            "of people who have actually done it.",
            "Increase the ability to earn — skills raise the ceiling on "
            "every other rule.",
        ),
        tricks=(
            "Automate a 10%+ savings transfer on the day income arrives.",
            "Budget the remaining 90% deliberately instead of spending "
            "whatever is left.",
            "Take financial advice only from someone qualified and "
            "experienced in that exact field.",
            "Insure against the events that would wipe out years of "
            "saving.",
        ),
        planning=(
            "Set a savings rate and an emergency fund before picking "
            "investments.",
            "Review insurance cover once a year.",
        ),
    ),
    Book(
        key="think-grow-rich",
        title="Think and Grow Rich",
        short_title="Think and Grow Rich",
        author="Napoleon Hill",
        year="1937",
        track="foundation",
        level="Intermediate",
        file_name="ThinkandGrowRich.pdf",
        thesis=(
            "A definite goal, backed by desire, faith, specialised "
            "knowledge and persistence, is the common thread in "
            "achievement."
        ),
        ideas=(
            "A definite chief aim: a specific amount, a deadline, and what "
            "you will give in return.",
            "Autosuggestion and faith turn a written goal into daily "
            "attention.",
            "Specialised knowledge and imagination are worth more than "
            "general information.",
            "Organised planning converts desire into a sequence of "
            "actions.",
            "Persistence and a mastermind group carry a plan through "
            "temporary defeat.",
        ),
        tricks=(
            "Write the goal with amount and date; read it aloud twice a "
            "day.",
            "Decide quickly and change a decision slowly.",
            "Meet an accountability group on a fixed cadence.",
            "Treat a setback as information, not a verdict.",
        ),
        planning=(
            "Write a one-page goal statement with a date and a monthly "
            "action.",
            "Attach one accountability partner or group to each 90-day "
            "plan.",
        ),
    ),
    Book(
        key="psychology-money",
        title="The Psychology of Money",
        short_title="The Psychology of Money",
        author="Morgan Housel",
        year="2020",
        track="foundation",
        level="Beginner",
        file_name="the-psychology-of-money-by-morgan-housel.pdf",
        thesis=(
            "Financial outcomes are driven more by behaviour than "
            "intelligence. Survival, patience and room for error let "
            "compounding do the work."
        ),
        ideas=(
            "No one is crazy: money choices reflect different "
            "generations, incomes and scars.",
            "Luck and risk are siblings; a single outcome is weak evidence "
            "of skill.",
            "Define 'enough' or the scoreboard never stops moving.",
            "Compounding rewards time, not brilliance; getting wealthy and "
            "staying wealthy need different skills.",
            "A few tail events drive most returns, so a portfolio must "
            "survive the ordinary bad years.",
            "Wealth is what you do not see — income spent is not wealth.",
        ),
        tricks=(
            "Write down your 'enough' number and stop moving it after a "
            "win.",
            "Hold a cash buffer so you never have to sell at the bottom.",
            "Expect volatility; it is the price of admission, not a "
            "malfunction.",
            "Choose 'reasonable and repeatable' over 'optimal and "
            "abandoned'.",
        ),
        planning=(
            "Define the enough number and a cash buffer before increasing "
            "risk.",
            "Add a behaviour rule to the plan: what you will not do in a "
            "drawdown.",
        ),
    ),
    Book(
        key="random-walk",
        title="A Random Walk Down Wall Street",
        short_title="A Random Walk Down Wall Street",
        author="Burton G. Malkiel",
        year="2007 ed.",
        track="investing",
        level="Intermediate",
        file_name="A random walk down Wall Street. Burton G Malkiel_text.pdf",
        thesis=(
            "Prices already reflect most information, so most stock "
            "pickers and market timers lose to a broad, low-cost index "
            "fund held through a disciplined plan."
        ),
        ideas=(
            "The random walk: short-term price changes are close to "
            "unpredictable.",
            "Diversification lowers company-specific risk; market risk "
            "remains and must be paid for.",
            "Analyst recommendations, fund managers and market timing "
            "mostly fail to beat the index after costs.",
            "Five allocation principles: risk and reward are linked, time "
            "horizon changes risk, dollar-cost averaging helps, "
            "rebalancing controls risk, and risk attitude is not risk "
            "capacity.",
            "A life-cycle guide allocates by years until the money is "
            "needed.",
        ),
        tricks=(
            "Make a broad, low-cost index fund the core of the portfolio.",
            "Invest on a schedule and rebalance on a calendar, not on "
            "headlines.",
            "Separate willingness to take risk from ability to survive a "
            "loss.",
            "Audit fees and turnover: costs are the most reliable drag on "
            "returns.",
        ),
        planning=(
            "Set a core allocation by goal horizon, then a small satellite "
            "sleeve.",
            "Put an annual rebalance date in the calendar.",
        ),
    ),
    Book(
        key="buffett-way",
        title="The Warren Buffett Way",
        short_title="The Warren Buffett Way",
        author="Robert G. Hagstrom",
        year="1994",
        track="investing",
        level="Intermediate",
        file_name="the-warren-buffett-way.pdf",
        thesis=(
            "Buy a few understandable businesses with durable economics "
            "at a discount to intrinsic value, then hold while the "
            "business compounds."
        ),
        ideas=(
            "Business tenets: simple and understandable, consistent "
            "history, favourable long-term prospects.",
            "Management tenets: rational capital allocation, candour, "
            "resistance to the institutional imperative.",
            "Financial tenets: return on equity, owner earnings, profit "
            "margins, and one dollar of market value per dollar retained.",
            "Value tenets: intrinsic value, margin of safety, and Mr "
            "Market as a servant rather than a guide.",
            "Stay inside the circle of competence; concentration in the "
            "best ideas beats wide diversification.",
        ),
        tricks=(
            "Run the 12-tenet checklist before buying, not after.",
            "Require a margin of safety between price and a conservative "
            "intrinsic value.",
            "Read the capital-allocation record, not just the growth "
            "story.",
            "Do not sell a compounding business for a small premium.",
        ),
        planning=(
            "Keep a one-page stock scorecard for every holding.",
            "Review the thesis annually and size positions by conviction.",
        ),
    ),
    Book(
        key="reminiscences",
        title="Reminiscences of a Stock Operator",
        short_title="Reminiscences of a Stock Operator",
        author="Edwin Lefèvre",
        year="1923",
        track="psychology",
        level="Intermediate",
        file_name="Reminiscences Of A Stock Operator.pdf",
        thesis=(
            "Markets are made of people and repeat their behaviour. A "
            "trader wins by reading the market, waiting for confirmation, "
            "sitting tight in winners and cutting losses fast."
        ),
        ideas=(
            "Price action is the primary evidence; the tape tells you what "
            "participants are doing.",
            "Tips are poison: a position you cannot explain is a position "
            "you cannot hold.",
            "The market is never wrong; opinions are.",
            "Big money is made by sitting, not by trading every wiggle.",
            "Never average a loss, and study your own mistakes more than "
            "your wins.",
        ),
        tricks=(
            "Define the loss before entry and never add to a losing "
            "position.",
            "Trade with the trend and wait for confirmation instead of "
            "predicting.",
            "Keep a mistake journal and review it monthly.",
            "After a large win, cut size and reset before the next trade.",
        ),
        planning=(
            "Keep a trade journal with thesis, stop, size and outcome.",
            "Review mistakes monthly, not just profit and loss.",
        ),
    ),
    Book(
        key="fooled-by-randomness",
        title="Fooled by Randomness",
        short_title="Fooled by Randomness",
        author="Nassim Nicholas Taleb",
        year="2004 ed.",
        track="psychology",
        level="Advanced",
        file_name=(
            "Nassim Nicholas Taleb - Fooled by Randomness_ The Hidden "
            "Role of Chance in Life and in the Markets, Second "
            "Edition-Texere (2004)_text.pdf"
        ),
        thesis=(
            "Short runs of success mostly measure luck. Judging process, "
            "alternative histories and asymmetry matters more than any "
            "single outcome."
        ),
        ideas=(
            "Noise is not signal; a good month says little about a "
            "strategy.",
            "Alternative histories: many outcomes could have happened "
            "from the same process.",
            "Survivorship bias hides the failures that never got to tell "
            "their story.",
            "Skewness matters: many small gains can hide one catastrophic "
            "loss.",
            "Rare events dominate long-run results, and induction from a "
            "short sample is fragile.",
        ),
        tricks=(
            "Judge a strategy over many trades and at least one full "
            "cycle.",
            "Ask what else could have happened before calling an outcome "
            "skill.",
            "Prefer positive skew with capped downside over a "
            "smooth-looking record.",
            "Keep enough capital to survive the worst plausible "
            "sequence.",
        ),
        planning=(
            "Evaluate strategies on 30+ trades and report the sample size.",
            "Run a risk-of-ruin check before scaling a strategy.",
        ),
    ),
    Book(
        key="thinking-fast-slow",
        title="Thinking, Fast and Slow",
        short_title="Thinking, Fast and Slow",
        author="Daniel Kahneman",
        year="2011",
        track="psychology",
        level="Advanced",
        file_name="Thinking, Fast and Slow by Daniel Kahneman.pdf",
        thesis=(
            "Two systems — fast intuition and slow reasoning — produce "
            "predictable biases that quietly damage financial decisions."
        ),
        ideas=(
            "System 1 is fast and associative; System 2 is slow, "
            "effortful and easily depleted.",
            "Anchoring, availability and representativeness distort "
            "estimates.",
            "Loss aversion makes losses hurt more than equivalent gains "
            "please.",
            "Overconfidence and the planning fallacy make projects and "
            "returns look better than they are.",
            "Regression to the mean is mistaken for skill or failure.",
            "What you see is all there is: the mind builds a coherent "
            "story from incomplete evidence.",
        ),
        tricks=(
            "Pre-commit rules before emotion arrives.",
            "Use base rates and the outside view for forecasts.",
            "Write down the reason for a decision, then judge the decision "
            "separately from the outcome.",
            "Check the portfolio less often; frequent checking amplifies "
            "loss aversion.",
            "Run a pre-mortem before any large commitment.",
        ),
        planning=(
            "Keep a decision journal with the facts, the forecast and the "
            "reasoning.",
            "Add a pre-mortem and a base-rate check to every major "
            "allocation decision.",
        ),
    ),
    Book(
        key="murphy",
        title="Technical Analysis of the Financial Markets",
        short_title="Technical Analysis of the Financial Markets",
        author="John J. Murphy",
        year="1999",
        track="technical",
        level="Advanced",
        file_name="John J Murphy - Technical Analysis Of The Financial Markets_text.pdf",
        thesis=(
            "Price action discounts everything and trends persist. "
            "Charts, volume and open interest, plus strict money "
            "management, form a complete trading method."
        ),
        ideas=(
            "Dow theory: trends have three phases and persist until "
            "evidence reverses.",
            "Support, resistance and trendlines frame where risk is "
            "defined.",
            "Reversal patterns (head and shoulders, double tops) and "
            "continuation patterns (triangles, flags) describe supply and "
            "demand.",
            "Moving averages smooth trend; oscillators such as RSI, "
            "stochastics and MACD work best in ranges.",
            "Volume and open interest confirm or warn about a move.",
            "Three elements of a trade: price forecast, timing and money "
            "management.",
        ),
        tricks=(
            "Risk at most 5% of capital per trade; keep 10–15% in one "
            "market and 20–25% in one group.",
            "Stay at most 50% invested while trading, so cash is a "
            "position too.",
            "Demand at least 3:1 reward-to-risk before entering.",
            "Use oscillators in ranges and trend tools in trends — do not "
            "mix them up.",
            "Let the chart, not the news, set the stop.",
        ),
        planning=(
            "Put a position-size and reward/risk check in front of every "
            "trade.",
            "Review charts weekly and keep a written trade plan.",
        ),
    ),
    Book(
        key="candlestick-guide",
        title="Introduction to Candlestick Patterns",
        short_title="Candlestick Patterns Guide",
        author="ThinkMarkets",
        year="n.d.",
        track="technical",
        level="Beginner",
        file_name="Candlestick_Patterns_Trading_Guide.pdf",
        thesis=(
            "Candlesticks show the fight between buyers and sellers inside "
            "each session. A handful of patterns, read at the right "
            "location and confirmed, sharpen timing."
        ),
        ideas=(
            "The body shows open-to-close; the wicks show rejection of "
            "higher or lower prices.",
            "Doji signals indecision; hammer and hanging man mark "
            "rejection at lows or highs.",
            "Engulfing, piercing and dark-cloud patterns show a shift in "
            "control.",
            "Morning star and evening star are three-candle reversal "
            "structures.",
            "Three white soldiers and three black crows show sustained "
            "pressure.",
            "Patterns matter most at support, resistance and the 200 EMA.",
        ),
        tricks=(
            "Read location first: a hammer in mid-air is not a signal.",
            "Wait for the next candle to confirm before acting.",
            "Put the stop beyond the pattern's wick, where the idea is "
            "invalidated.",
            "Combine with volume; low-volume patterns fail more often.",
        ),
        planning=(
            "Add a candle-confirmation step to the entry checklist.",
            "Keep a pattern journal with location and outcome.",
        ),
    ),
    Book(
        key="trading-brochure",
        title="Trading Strategies for Indian Markets",
        short_title="Trading Strategies for Indian Markets",
        author="NSE Knowledge Hub",
        year="n.d.",
        track="technical",
        level="Beginner",
        file_name="Brochure_Trading_Strategy_for_Market.pdf",
        thesis=(
            "A strategy is a repeatable written set of conditions — "
            "setup, entry, exit and risk — not a feeling. Indicators only "
            "serve the setup."
        ),
        ideas=(
            "Four basic setups: continuation, reversal, range-bound and "
            "breakout.",
            "Bollinger Bands use a 20-day SMA plus or minus two standard "
            "deviations to flag stretched prices.",
            "Momentum tools (RSI, MACD) measure the speed of a move; RSI "
            "70/30 is the common range.",
            "Fibonacci retracements (23.6, 38.2, 50, 61.8, 78.6%) suggest "
            "where a pullback may stall.",
            "Price action with volume, swing trading, and volume/open "
            "interest give context.",
            "Sentiment extremes can be contrarian; benchmark every "
            "strategy against Nifty 50.",
        ),
        tricks=(
            "Write the setup conditions before entering, then only take "
            "trades that match.",
            "Require at least two independent confirmations.",
            "Use Fibonacci levels for entries and stops, never as "
            "guarantees.",
            "Match the strategy to the regime: trend tools in trends, "
            "range tools in ranges.",
            "Benchmark against the index or the strategy proves nothing.",
        ),
        planning=(
            "Use a one-page strategy template for every new idea.",
            "Record the benchmark alongside the strategy's return.",
        ),
    ),
    Book(
        key="options-strategies",
        title="Option Trading Strategies",
        short_title="Option Trading Strategies",
        author="Compiled reference guide",
        year="n.d.",
        track="options",
        level="Intermediate",
        file_name="Option_Trading_Strategies.pdf",
        thesis=(
            "Options are building blocks. Each named strategy expresses a "
            "specific view on direction, volatility or time, with its own "
            "payoff and risk."
        ),
        ideas=(
            "The four basic positions: buy call, buy put, sell call, sell "
            "put.",
            "Straddles and strangles trade volatility; spreads trade "
            "direction with capped risk.",
            "Butterflies and condors sell extremes and profit from a "
            "range.",
            "Covered call and collar overlay an existing stock position.",
            "Every strategy has a payoff diagram, breakeven and maximum "
            "loss.",
            "Short options collect premium but carry margin and tail "
            "risk.",
        ),
        tricks=(
            "Pick the strategy from the view, not the other way round.",
            "Mark maximum profit, maximum loss and breakeven before "
            "entering.",
            "Avoid naked short options unless the account can absorb the "
            "worst case.",
            "Size by the premium or margin at risk, not by the number of "
            "lots.",
        ),
        planning=(
            "Keep an options strategy sheet with view, legs, payoff and "
            "exit.",
            "Budget options risk separately from the long-term portfolio.",
        ),
    ),
    Book(
        key="nse-options",
        title="NSE Options Module",
        short_title="NSE Options Module",
        author="National Stock Exchange of India",
        year="n.d.",
        track="options",
        level="Intermediate",
        file_name="99993845.pdf",
        thesis=(
            "Options are rights with a price. Understanding payoff, time "
            "value and the Greeks turns a direction bet into a "
            "defined-risk strategy."
        ),
        ideas=(
            "A call is the right to buy; a put is the right to sell. The "
            "buyer pays a premium, the seller takes on the obligation.",
            "Premium = intrinsic value + time value; it decays as expiry "
            "approaches.",
            "ITM, ATM and OTM describe where the strike sits versus the "
            "spot price.",
            "Indian index options are European and cash-settled; stock "
            "options are physically settled.",
            "Greeks: delta (direction), gamma (change in delta), theta "
            "(time decay), vega (volatility), rho (rates).",
            "The module walks 22 strategies from long call to short "
            "condor.",
        ),
        tricks=(
            "Draw the payoff and mark maximum profit and loss before "
            "trading.",
            "A buyer can lose the whole premium; a seller faces margin "
            "calls and tail risk.",
            "Theta helps sellers and hurts buyers — know which side you "
            "are on.",
            "Close or roll before expiry if liquidity dries up.",
        ),
        planning=(
            "Add a payoff sketch and Greeks check to every options trade.",
            "Keep an expiry calendar and a separate options risk budget.",
        ),
    ),
    Book(
        key="nifty-ratio",
        title="Nifty Option Strategy — August 2023 Series",
        short_title="Nifty Ratio Spread (Aug 2023)",
        author="Research desk note",
        year="2023",
        track="options",
        level="Intermediate",
        file_name="Nifty_Option_Strategy_for_the_August_2023_Series.pdf",
        thesis=(
            "A fully specified ratio spread shows what a complete trade "
            "plan looks like: view, legs, credit, stop, target, margin and "
            "expiry."
        ),
        ideas=(
            "The note pairs a put ratio (buy 1 × 19,200 PE at ₹73, sell 2 "
            "× 19,000 PE at ₹49) with a call ratio (buy 1 × 20,350 CE at "
            "₹40, sell 2 × 20,500 CE at ₹26).",
            "It is a short-gamma structure that wants the index to expire "
            "inside the sold strikes.",
            "The plan states a ₹37 net credit, a ₹100 debit stop, a ₹150 "
            "target and roughly ₹1.5 lakh margin.",
            "Expiry was 31 August 2023 — every leg, price and risk figure "
            "is written down in advance.",
        ),
        tricks=(
            "Never copy legs without the reasoning and the payoff.",
            "Predefine stop and target in rupees, not in hope.",
            "Size to the margin and the worst case, not to the credit "
            "received.",
            "Ratio spreads carry extra risk on the sold side; exit if the "
            "range breaks.",
        ),
        planning=(
            "Use it as the template for a complete trade plan: view, "
            "legs, credit, stop, target, margin, expiry.",
            "Stress-test the payoff at the sold strikes before entering.",
        ),
    ),
)

BOOK_BY_KEY = {book.key: book for book in BOOKS}


@dataclass(frozen=True)
class PlaybookEntry:
    """One reusable rule, synthesised from one or more books."""

    key: str
    title: str
    principle: str
    rules: tuple[str, ...]
    sources: tuple[str, ...]


PLAYBOOK = (
    PlaybookEntry(
        key="size-first",
        title="Size the position before you like the idea",
        principle=(
            "A good idea at the wrong size is still a bad trade. Decide "
            "what you can lose first, then how many shares or lots that "
            "buys."
        ),
        rules=(
            "Use Murphy's ceilings as hard limits: 5% of capital at risk "
            "per trade, 10–15% in one market, 20–25% per group, 50% "
            "invested at most.",
            "For long-term holdings, size by how much of the portfolio "
            "you can hold through a 50% drawdown without selling.",
            "For options, size by premium or margin at risk — not by the "
            "number of lots that fit.",
            "Write the rupee risk on the trade plan before the entry "
            "order.",
        ),
        sources=("murphy", "nse-options", "options-strategies"),
    ),
    PlaybookEntry(
        key="cut-losses",
        title="Define the loss before entry",
        principle=(
            "The exit is part of the thesis. If you cannot say where the "
            "idea is wrong, you do not yet have a trade."
        ),
        rules=(
            "Place the stop at the price that proves the thesis wrong, "
            "not at a round number you can tolerate.",
            "Never average down into a losing position; add only to a "
            "plan that is working.",
            "Demand at least 3:1 reward-to-risk, so a normal win rate can "
            "still make money.",
            "Record the mistake when a stop is hit, and review the "
            "pattern monthly.",
        ),
        sources=("reminiscences", "murphy", "trading-brochure"),
    ),
    PlaybookEntry(
        key="trend-first",
        title="Trade with the trend, time with the oscillator",
        principle=(
            "Trend tools and range tools answer different questions. "
            "Using the wrong one is how a good indicator becomes a bad "
            "signal."
        ),
        rules=(
            "Define the trend with higher highs and higher lows, or a "
            "rising long moving average.",
            "Use RSI, stochastics and Bollinger Bands to time entries "
            "inside a trend or to fade a range — not to call the trend "
            "itself.",
            "Wait for a confirmation candle at support or resistance "
            "before acting.",
            "Let volume confirm the move; a breakout on thin volume is a "
            "trap.",
        ),
        sources=("murphy", "candlestick-guide", "trading-brochure"),
    ),
    PlaybookEntry(
        key="defined-risk-options",
        title="Only take option risk you can draw",
        principle=(
            "Every option position has a payoff diagram. If you cannot "
            "sketch it, you cannot size it."
        ),
        rules=(
            "Mark maximum profit, maximum loss and breakeven before "
            "entering.",
            "Buyers can lose 100% of premium; sellers face margin calls "
            "and tail risk.",
            "Know whether theta and vega help or hurt the position.",
            "Close or roll before expiry when liquidity dries up; do not "
            "hope for settlement.",
        ),
        sources=("nse-options", "options-strategies", "nifty-ratio"),
    ),
    PlaybookEntry(
        key="written-strategy",
        title="A strategy is a written checklist",
        principle=(
            "A repeatable edge is a set of conditions that can be "
            "checked, not a feeling about the chart."
        ),
        rules=(
            "Write the setup type: continuation, reversal, range-bound or "
            "breakout.",
            "Write the entry trigger, stop, target, size and time limit.",
            "Require at least two independent confirmations.",
            "Benchmark the result against Nifty 50, or you cannot tell "
            "skill from beta.",
        ),
        sources=("trading-brochure", "nifty-ratio", "murphy"),
    ),
    PlaybookEntry(
        key="core-satellite",
        title="Index core, conviction satellite",
        principle=(
            "Most of the money should sit in a boring, low-cost core. "
            "Active ideas get a bounded satellite sleeve."
        ),
        rules=(
            "Use a broad index fund as the default home for long-term "
            "money.",
            "Cap the satellite sleeve so one bad stock idea cannot derail "
            "the plan.",
            "Rebalance on a calendar and on bands, not on headlines.",
            "Audit fees and turnover every year; costs compound against "
            "you.",
        ),
        sources=("random-walk", "buffett-way"),
    ),
    PlaybookEntry(
        key="quality-at-a-price",
        title="Quality business, sensible price",
        principle=(
            "A great company is not automatically a great investment. "
            "The price you pay decides the return."
        ),
        rules=(
            "Run the 12-tenet checklist: business, management, "
            "financials and value.",
            "Estimate owner earnings and a conservative intrinsic value.",
            "Buy only with a margin of safety; a good story is not a "
            "discount.",
            "Hold while the business compounds, and review the thesis "
            "annually.",
        ),
        sources=("buffett-way", "random-walk"),
    ),
    PlaybookEntry(
        key="pay-yourself-first",
        title="Save first, spend what is left",
        principle=(
            "Investing starts with the gap between income and lifestyle, "
            "and that gap is a decision, not a leftover."
        ),
        rules=(
            "Automate at least 10% of every inflow into investments.",
            "Control expenses deliberately instead of spending the "
            "remainder.",
            "Build an emergency fund before taking market risk.",
            "Insure the events that could wipe out years of saving.",
        ),
        sources=("richest-man", "rich-dad", "psychology-money"),
    ),
    PlaybookEntry(
        key="define-enough",
        title="Define enough and build room for error",
        principle=(
            "A plan without an 'enough' number keeps taking risk after "
            "the goal is already met."
        ),
        rules=(
            "Write the number that makes work optional, and stop moving "
            "it after a win.",
            "Hold a cash buffer so you never have to sell at the bottom.",
            "Prefer survival over optimisation: avoid the bet that can end "
            "the game.",
            "Judge decisions over decades, not quarters.",
        ),
        sources=("psychology-money", "buffett-way", "random-walk"),
    ),
    PlaybookEntry(
        key="judge-process",
        title="Judge the process, not the last outcome",
        principle=(
            "One result is a sample of one. Process, sample size and "
            "asymmetry tell you whether a strategy is real."
        ),
        rules=(
            "Evaluate a strategy over 30+ trades and at least one full "
            "market cycle.",
            "Ask what else could have happened from the same process.",
            "Use base rates and the outside view before a forecast.",
            "Keep a decision journal and run a pre-mortem before large "
            "commitments.",
        ),
        sources=(
            "fooled-by-randomness",
            "thinking-fast-slow",
            "reminiscences",
        ),
    ),
)


@dataclass(frozen=True)
class PlanningPhase:
    """One stage of the planning path, from saving to reviewing."""

    key: str
    title: str
    summary: str
    actions: tuple[str, ...]
    sources: tuple[str, ...]


PLANNING_PHASES = (
    PlanningPhase(
        key="foundation",
        title="Build the money base",
        summary=(
            "Before return, build the buffer that keeps you invested. "
            "Savings rate, emergency fund and insurance come first."
        ),
        actions=(
            "List assets, liabilities and monthly cash flow; separate "
            "income-producing assets from consumption.",
            "Set an automatic savings rate of at least 10%.",
            "Build an emergency fund covering 3–6 months of expenses.",
            "Review health and term insurance before taking market risk.",
        ),
        sources=("richest-man", "rich-dad", "psychology-money"),
    ),
    PlanningPhase(
        key="goals",
        title="Write goals with numbers and dates",
        summary=(
            "A goal without an amount and a date cannot set an "
            "allocation."
        ),
        actions=(
            "Write a definite goal statement with amount, date and "
            "monthly contribution.",
            "Bucket money by when it is needed: under 3 years, 3–7 years, "
            "7+ years.",
            "Separate willingness to take risk from ability to survive a "
            "loss.",
            "Write the 'enough' number and the lifestyle it funds.",
        ),
        sources=("think-grow-rich", "random-walk", "psychology-money"),
    ),
    PlanningPhase(
        key="allocation",
        title="Choose the core allocation",
        summary=(
            "The mix of equity, debt and cash does most of the work. "
            "Keep the core simple and the satellite small."
        ),
        actions=(
            "Set a broad, low-cost index fund as the core for long-term "
            "money.",
            "Add debt or cash for goals inside the next three years.",
            "Cap the active satellite sleeve at a size you can hold "
            "through a drawdown.",
            "Write rebalancing bands and a review date.",
        ),
        sources=("random-walk", "buffett-way"),
    ),
    PlanningPhase(
        key="rules",
        title="Write execution rules",
        summary=(
            "Turn the allocation into repeatable actions: what to buy, "
            "when, how much, and when to exit."
        ),
        actions=(
            "Write one strategy template: setup, entry, stop, target, "
            "size and time limit.",
            "Set position-size limits and a per-trade risk limit.",
            "For options, sketch the payoff and cap the risk budget.",
            "Commit to no averaging down and no trading on tips.",
        ),
        sources=("murphy", "reminiscences", "trading-brochure", "nse-options"),
    ),
    PlanningPhase(
        key="behaviour",
        title="Install behaviour guardrails",
        summary=(
            "The plan will be tested by drawdowns. Decide now how you "
            "will behave when it hurts."
        ),
        actions=(
            "Automate contributions and rebalancing so the default is "
            "action, not decision.",
            "Check prices less often; review the plan on a calendar.",
            "Keep a decision journal with facts, forecast and reasoning.",
            "Run a pre-mortem on any large new position and name the exit "
            "in advance.",
        ),
        sources=(
            "thinking-fast-slow",
            "fooled-by-randomness",
            "psychology-money",
        ),
    ),
    PlanningPhase(
        key="review",
        title="Review on a calendar",
        summary=(
            "A plan improves through scheduled review, not through "
            "constant reaction."
        ),
        actions=(
            "Monthly: reconcile cash flow and check the savings transfer.",
            "Quarterly: review holdings, theses and any stopped-out "
            "mistakes.",
            "Yearly: rebalance, audit fees and tax, and compare against "
            "Nifty 50.",
            "Update the goal statement and 'enough' number only with a "
            "written reason.",
        ),
        sources=("random-walk", "trading-brochure", "buffett-way"),
    ),
)

REVIEW_CHECKLIST = (
    "Savings rate and emergency fund still on target",
    "Asset allocation inside its bands",
    "Every holding has a one-line thesis and a reason to own it",
    "Position sizes and option risk within limits",
    "Fees, turnover and tax reviewed",
    "Returns compared with the right benchmark",
    "Decision journal read; recurring mistakes named",
)

# Non-book material kept in the same folder, listed so the library reflects
# the whole shelf without pretending to summarise an image.
EXTRA_REFERENCES = (
    (
        "10-steps-scaled.jpg",
        "One-page infographic kept with the books; open it locally as a "
        "visual recap.",
    ),
)

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


def filter_books(query="", track=None):
    """Books matching a free-text query and/or a track key.

    The query is matched case-insensitively against the title, author,
    thesis, ideas, tricks and planning notes, so a search for "stop"
    finds every book that mentions stops.
    """

    needle = (query or "").strip().lower()
    matches = []
    for book in BOOKS:
        if track and book.track != track:
            continue
        haystack = " ".join(
            (book.title, book.author, book.thesis)
            + book.ideas
            + book.tricks
            + book.planning
        ).lower()
        if needle and needle not in haystack:
            continue
        matches.append(book)
    return tuple(matches)


def source_titles(keys):
    """Short titles for the book keys cited by a playbook or plan entry."""

    return ", ".join(BOOK_BY_KEY[key].short_title for key in keys)
