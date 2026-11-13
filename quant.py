"""
quant.py - three simple price rules ("votes") and a quant score.

What this file does:
    Applies three rules to a series of daily closes. Each rule votes +1 or -1:
      trend:    last close > 200-day simple moving average
      momentum: return over the last 126 trading days > 0
      risk:     annualized volatility of the last 60 daily returns < 0.30
    quant_score = sum(votes) / 3, so it is one of -1, -1/3, +1/3, +1.
Input:
    A pandas Series of daily closes (oldest first), e.g. prices["close"].
Output:
    A dict with each vote, the raw number behind it, and quant_score;
    saved as 07_quant.json.

How to explain this in an interview:
    "These are three classic, transparent rules: is the price above its long-term
    average, has it gone up over six months, and is it calm enough. Each rule
    returns its raw number too, so the report can explain the score instead of
    just stating it."
"""

import logging
import math
from pathlib import Path

import pandas as pd

import config
import run_logger

log = logging.getLogger("quant")

# The longest look-back any rule needs. Momentum needs 126 days *plus* today,
# and volatility needs 60 returns, i.e. 61 prices.
MIN_PRICES_NEEDED = max(config.TREND_SMA_WINDOW,
                        config.MOMENTUM_LOOKBACK_DAYS + 1,
                        config.VOLATILITY_WINDOW + 1)


def _vote(condition: bool) -> int:
    """+1 if the rule is satisfied, otherwise -1 (there is no 0 vote)."""
    return 1 if condition else -1


def trend_vote(closes: pd.Series) -> dict:
    """Trend: is the last close above the 200-day simple moving average?"""
    last_close = float(closes.iloc[-1])
    sma = float(closes.iloc[-config.TREND_SMA_WINDOW:].mean())
    return {
        "name": "trend",
        "rule": f"last close > {config.TREND_SMA_WINDOW}-day SMA",
        "vote": _vote(last_close > sma),
        "last_close": last_close,
        "sma": sma,
        "pct_above_sma": last_close / sma - 1,
    }


def momentum_vote(closes: pd.Series) -> dict:
    """Momentum: price change over the last 126 trading days (~6 months)."""
    last_close = float(closes.iloc[-1])
    # iloc[-1] is today, so 126 trading days ago is iloc[-127].
    past_close = float(closes.iloc[-1 - config.MOMENTUM_LOOKBACK_DAYS])
    period_return = last_close / past_close - 1
    return {
        "name": "momentum",
        "rule": f"return over last {config.MOMENTUM_LOOKBACK_DAYS} trading days > 0",
        "vote": _vote(period_return > 0),
        "last_close": last_close,
        "past_close": past_close,
        "past_date": str(closes.index[-1 - config.MOMENTUM_LOOKBACK_DAYS])[:10],
        "return": period_return,
    }


def risk_vote(closes: pd.Series) -> dict:
    """Risk: annualized volatility of the last 60 daily returns.

    Daily standard deviation * sqrt(252) converts "typical daily move" into a
    yearly number, which is the usual way volatility is quoted.
    """
    daily_returns = closes.pct_change().dropna().iloc[-config.VOLATILITY_WINDOW:]
    annual_vol = float(daily_returns.std() * math.sqrt(config.TRADING_DAYS_PER_YEAR))
    return {
        "name": "risk",
        "rule": f"annualized volatility of last {config.VOLATILITY_WINDOW} returns "
                f"< {config.MAX_ANNUAL_VOLATILITY}",
        "vote": _vote(annual_vol < config.MAX_ANNUAL_VOLATILITY),
        "annualized_volatility": annual_vol,
        "threshold": config.MAX_ANNUAL_VOLATILITY,
    }


def compute_quant(closes: pd.Series) -> dict:
    """Run all three votes and average them into quant_score (-1 to +1).

    Raises ValueError if there is not enough history, because a 200-day average
    of 50 days of data would be silently wrong.
    """
    closes = closes.dropna()
    if len(closes) < MIN_PRICES_NEEDED:
        raise ValueError(f"Need at least {MIN_PRICES_NEEDED} daily closes, "
                         f"got {len(closes)} (recently listed stock?)")

    votes = [trend_vote(closes), momentum_vote(closes), risk_vote(closes)]
    quant_score = sum(v["vote"] for v in votes) / len(votes)
    return {
        "as_of_date": str(closes.index[-1])[:10],
        "num_prices": len(closes),
        "votes": votes,
        "quant_score": quant_score,
    }


def run_quant(closes: pd.Series, run_dir: Path) -> dict | None:
    """Full stage: compute, log each vote, save 07_quant.json. None on failure."""
    with run_logger.stage("quant"):
        try:
            result = compute_quant(closes)
        except ValueError as error:
            log.error("Quant failed: %s", error)
            return None

        for v in result["votes"]:
            raw = {k: (round(x, 4) if isinstance(x, float) else x)
                   for k, x in v.items() if k not in ("name", "rule", "vote")}
            log.info("%-8s vote %+d  %s", v["name"], v["vote"], raw)
        log.info("quant_score = %+.3f (as of %s)", result["quant_score"], result["as_of_date"])
        run_logger.save_json(run_dir, "07_quant.json", result)
        return result


if __name__ == "__main__":
    import prices  # only needed when this file runs alone

    symbol = input("Ticker (e.g. AAPL): ").strip().upper()
    if not symbol:
        print("Please type a ticker.")
    else:
        folder = run_logger.start_run(f"quant {symbol}")
        run_logger.write_run_meta(folder, company_input=symbol)
        price_data = prices.get_prices(symbol, folder)
        result = run_quant(price_data["close"], folder) if price_data is not None else None
        if result:
            print(f"\n{symbol} as of {result['as_of_date']}")
            for v in result["votes"]:
                print(f"  {v['name']:<9} {v['vote']:+d}   ({v['rule']})")
            print(f"  quant_score = {result['quant_score']:+.3f}")
        else:
            print("\nNo quant result (see run.log).")
        print(f"Saved to: {folder}")
