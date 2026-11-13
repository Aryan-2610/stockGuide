"""
prices.py - download daily closing prices.

What this file does:
    Downloads about 2 years of daily prices for one ticker with yfinance and
    keeps only the (split- and dividend-adjusted) closing price per day.
Input:
    A ticker symbol, e.g. "AAPL" or "RELIANCE.NS".
Output:
    A pandas DataFrame indexed by date with one column "close";
    saved as 02_prices.csv. Returns None if no data could be fetched.

How to explain this in an interview:
    "This file only fetches and tidies data; it makes no decisions. I use adjusted
    closes so a stock split does not look like a 50% crash to the quant rules."
"""

import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

import config
import run_logger

log = logging.getLogger("prices")


def fetch_prices(ticker: str, period: str = config.PRICE_PERIOD) -> pd.DataFrame:
    """Download daily history and return a DataFrame with a single 'close' column.

    Returns an empty DataFrame if Yahoo has no data for the ticker.
    Raises on network errors (the caller logs them).
    """
    # auto_adjust=True: prices are adjusted for splits and dividends.
    history = yf.Ticker(ticker).history(period=period, interval="1d",
                                        auto_adjust=True, raise_errors=False)
    if history is None or history.empty or "Close" not in history:
        return pd.DataFrame(columns=["close"])

    prices = history[["Close"]].rename(columns={"Close": "close"}).dropna()
    # Yahoo gives timezone-aware timestamps; plain dates are easier to read in the CSV.
    prices.index = pd.to_datetime(prices.index).tz_localize(None).normalize()
    prices.index.name = "date"
    return prices


def get_prices(ticker: str, run_dir: Path) -> pd.DataFrame | None:
    """Full stage: fetch, log a summary, save 02_prices.csv. None on failure."""
    with run_logger.stage("prices"):
        log.info("Ticker: %s, period: %s", ticker, config.PRICE_PERIOD)
        try:
            prices = fetch_prices(ticker)
        except Exception as error:  # no internet, Yahoo blocked the request...
            log.error("Price download failed for %s: %s", ticker, error)
            log.debug("Details", exc_info=True)
            return None

        if prices.empty:
            log.error("No price data for %s (bad ticker or delisted?)", ticker)
            return None

        log.info("Got %d daily closes from %s to %s (last close %.2f)",
                 len(prices), prices.index[0].date(), prices.index[-1].date(),
                 prices["close"].iloc[-1])
        run_logger.save_csv(run_dir, "02_prices.csv", prices)
        return prices


if __name__ == "__main__":
    symbol = input("Ticker (e.g. AAPL): ").strip().upper()
    if not symbol:
        print("Please type a ticker.")
    else:
        folder = run_logger.start_run(f"prices {symbol}")
        run_logger.write_run_meta(folder, company_input=symbol)
        data = get_prices(symbol, folder)
        if data is not None:
            print("\nFirst rows:\n", data.head(3).round(2))
            print("\nLast rows:\n", data.tail(3).round(2))
        else:
            print("\nNo prices (see run.log).")
        print(f"\nSaved to: {folder}")
