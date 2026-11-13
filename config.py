"""
config.py - settings for StockXpert V1.

What this file does:
    Loads secrets/settings from .env and defines every tunable number
    (weights, thresholds, window sizes) as a named constant in one place.
Input:
    The .env file in the project folder.
Output:
    Module-level constants other files import, plus config_snapshot()
    which returns the non-secret settings for logging.

How to explain this in an interview:
    "All magic numbers live here with a comment, so changing a rule means editing
    one line instead of hunting through the code. Secrets come from .env, which is
    git-ignored, and they are never included in the snapshot that gets logged."
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# The project folder = the folder this file lives in. Using an absolute path means
# the program works no matter which directory you run it from.
PROJECT_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_DIR / "runs"  # every query gets a sub-folder here

load_dotenv(PROJECT_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    """Read one environment variable, stripped of spaces (empty -> default)."""
    value = os.getenv(name, "").strip()
    return value if value else default


# ---------------------------------------------------------------------------
# Secrets and providers (from .env)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = _env("GEMINI_API_KEY")                       # secret: never print or log
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.5-flash-lite")  # cheap/fast default
NEWS_PROVIDER = _env("NEWS_PROVIDER", "yfinance").lower()     # yfinance | finnhub
NEWS_API_KEY = _env("NEWS_API_KEY")                           # secret: only for finnhub/newsapi
SENTIMENT_PROVIDER = _env("SENTIMENT_PROVIDER", "finbert").lower()  # finbert | gemini

# ---------------------------------------------------------------------------
# Ticker resolution
# ---------------------------------------------------------------------------
SEARCH_MAX_RESULTS = 10   # how many raw results to ask Yahoo for (before filtering to stocks)
MAX_CANDIDATES_SHOWN = 5  # how many stock matches to show the user when it is ambiguous

# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------
PRICE_PERIOD = "2y"  # ~500 trading days: comfortably more than the 200-day SMA needs

# ---------------------------------------------------------------------------
# Quant rules (3 votes, each +1 or -1)
# ---------------------------------------------------------------------------
TREND_SMA_WINDOW = 200         # trend vote: is the last close above the 200-day average?
MOMENTUM_LOOKBACK_DAYS = 126   # momentum vote: ~6 months of trading days
VOLATILITY_WINDOW = 60         # risk vote: use the last 60 daily returns (~3 months)
TRADING_DAYS_PER_YEAR = 252    # standard convention to annualize daily volatility
MAX_ANNUAL_VOLATILITY = 0.30   # risk vote is +1 only if annualized volatility is below 30%

# ---------------------------------------------------------------------------
# News fetching and cleaning
# ---------------------------------------------------------------------------
NEWS_ITEMS_TO_FETCH = 10     # instructions say about 8-10 items
NEWS_LOOKBACK_DAYS = 14      # finnhub only: how far back to ask for news
SNIPPET_MAX_CHARS = 500      # snippets are cut to this length before Gemini sees them
MIN_KEPT_NEWS_ITEMS = 3      # fewer kept items than this -> news_score = 0 ("insufficient news")
MAX_SUMMARY_WORDS = 25       # cleaner summaries longer than this are rejected

# Phrases that look like someone talking to an AI rather than reporting news.
# Code checks these as a second line of defence, in case Gemini misses an attack.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above)",
    r"system prompt",
    r"you are (now )?(an?|the) (ai|assistant|language model)",
    r"(as an|dear) (ai|assistant|language model)",
    r"\bnew instructions?\b",
    r"(call|rate|label|mark) (this|the) stock (a |as )?(strong )?(buy|sell)",
]

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
CLEANER_TEMPERATURE = 0.0  # cleaning should be as repeatable as possible
REPORT_TEMPERATURE = 0.2   # a little variety in wording, numbers still come from code
GEMINI_RETRIES = 1         # retry once on a temporary error (e.g. 503 overloaded)
GEMINI_RETRY_WAIT_SECONDS = 5

# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------
FINBERT_MODEL = "ProsusAI/finbert"  # finance-tuned BERT; labels: positive/negative/neutral

# ---------------------------------------------------------------------------
# Combining scores into a signal
# ---------------------------------------------------------------------------
QUANT_WEIGHT = 0.8         # prices are the main evidence
NEWS_WEIGHT = 0.2          # news only nudges the score (it is noisy and few items)
BULLISH_THRESHOLD = 0.25   # final_score >= this -> "bullish"
BEARISH_THRESHOLD = -0.25  # final_score <= this -> "bearish"; in between -> "neutral"
CONFLICT_MIN_NEWS_SCORE = 0.1  # news must be at least this strong (+/-) to count as a "conflict"


def config_snapshot() -> dict:
    """Return all NON-secret settings as a dict, for 00_run_meta.json.

    API keys are reported only as "set"/"missing" so we can debug a missing key
    without ever writing the key itself to disk.
    """
    return {
        "GEMINI_MODEL": GEMINI_MODEL,
        "NEWS_PROVIDER": NEWS_PROVIDER,
        "SENTIMENT_PROVIDER": SENTIMENT_PROVIDER,
        "GEMINI_API_KEY": "set" if GEMINI_API_KEY else "missing",
        "NEWS_API_KEY": "set" if NEWS_API_KEY else "missing",
        "SEARCH_MAX_RESULTS": SEARCH_MAX_RESULTS,
        "MAX_CANDIDATES_SHOWN": MAX_CANDIDATES_SHOWN,
        "PRICE_PERIOD": PRICE_PERIOD,
        "TREND_SMA_WINDOW": TREND_SMA_WINDOW,
        "MOMENTUM_LOOKBACK_DAYS": MOMENTUM_LOOKBACK_DAYS,
        "VOLATILITY_WINDOW": VOLATILITY_WINDOW,
        "TRADING_DAYS_PER_YEAR": TRADING_DAYS_PER_YEAR,
        "MAX_ANNUAL_VOLATILITY": MAX_ANNUAL_VOLATILITY,
        "NEWS_ITEMS_TO_FETCH": NEWS_ITEMS_TO_FETCH,
        "NEWS_LOOKBACK_DAYS": NEWS_LOOKBACK_DAYS,
        "SNIPPET_MAX_CHARS": SNIPPET_MAX_CHARS,
        "MIN_KEPT_NEWS_ITEMS": MIN_KEPT_NEWS_ITEMS,
        "MAX_SUMMARY_WORDS": MAX_SUMMARY_WORDS,
        "INJECTION_PATTERNS": INJECTION_PATTERNS,
        "CLEANER_TEMPERATURE": CLEANER_TEMPERATURE,
        "REPORT_TEMPERATURE": REPORT_TEMPERATURE,
        "GEMINI_RETRIES": GEMINI_RETRIES,
        "FINBERT_MODEL": FINBERT_MODEL,
        "QUANT_WEIGHT": QUANT_WEIGHT,
        "NEWS_WEIGHT": NEWS_WEIGHT,
        "BULLISH_THRESHOLD": BULLISH_THRESHOLD,
        "BEARISH_THRESHOLD": BEARISH_THRESHOLD,
        "CONFLICT_MIN_NEWS_SCORE": CONFLICT_MIN_NEWS_SCORE,
    }


if __name__ == "__main__":
    # Imported here (not at the top) because run_logger imports config;
    # importing it at the top would create a circular import.
    import logging
    import run_logger

    run_dir = run_logger.start_run("config-check")
    log = logging.getLogger("config")
    snapshot = config_snapshot()
    for key, value in snapshot.items():
        log.info("%-24s = %s", key, value)
    run_logger.write_run_meta(run_dir, company_input="(config check)")
    print(f"\nSaved to: {run_dir}")
