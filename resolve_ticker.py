"""
resolve_ticker.py - company name -> stock ticker (no LLM).

What this file does:
    Searches Yahoo Finance (through yfinance's built-in Search) for the company
    name, keeps only stock results (quoteType == "EQUITY"), and picks one.
    If there is more than one stock match, it shows the top 5 and asks the user
    to choose by number. The choice is logged and saved.
Input:
    A company name typed by the user, e.g. "apple" or "reliance".
Output:
    A dict with the candidates and the chosen ticker; saved as 01_resolve.json.

How to explain this in an interview:
    "I deliberately do not use an LLM here: a ticker must be exact, and a search
    API gives real symbols while an LLM could invent one. When the name is
    ambiguous (Apple Inc vs Apple Hospitality REIT) the human decides."
"""

import logging
from pathlib import Path

import yfinance as yf

import config
import run_logger

log = logging.getLogger("resolve")


def search_candidates(company_name: str) -> list[dict]:
    """Ask Yahoo for matches and return only stocks, in Yahoo's relevance order.

    Raises an exception on network problems; the caller decides what to do.
    """
    search = yf.Search(company_name, max_results=config.SEARCH_MAX_RESULTS,
                       news_count=0, lists_count=0, raise_errors=True)
    candidates = []
    for quote in search.quotes:
        # Yahoo also returns futures, ETFs, currencies... we only analyse stocks.
        if quote.get("quoteType") != "EQUITY":
            continue
        candidates.append({
            "symbol": quote.get("symbol"),
            "name": quote.get("longname") or quote.get("shortname") or "",
            "exchange": quote.get("exchDisp") or quote.get("exchange") or "",
            "sector": quote.get("sector") or "",
            "industry": quote.get("industry") or "",
        })
    return candidates


def choose_candidate(candidates: list[dict], input_fn=input) -> tuple[dict | None, str]:
    """Pick one candidate. Returns (chosen, how_it_was_chosen).

    input_fn is a parameter so tests can pass a fake instead of typing.
    """
    if len(candidates) == 1:
        return candidates[0], "only match"

    shown = candidates[:config.MAX_CANDIDATES_SHOWN]
    print("\nMore than one stock matches. Choose one:")
    for number, c in enumerate(shown, start=1):
        print(f"  {number}. {c['symbol']:<12} {c['name']}  [{c['exchange']}]")
    print("  q. cancel")

    # Keep asking until we get a valid number (or q), instead of crashing on typos.
    while True:
        answer = input_fn(f"Your choice (1-{len(shown)}): ").strip().lower()
        if answer == "q":
            return None, "user cancelled"
        if answer.isdigit() and 1 <= int(answer) <= len(shown):
            return shown[int(answer) - 1], f"user chose #{answer}"
        print(f"Please type a number from 1 to {len(shown)}, or q.")


def resolve_ticker(company_name: str, run_dir: Path, input_fn=input) -> dict | None:
    """Full stage: search, choose, log, save 01_resolve.json.

    Returns the chosen candidate dict, or None if nothing usable was found.
    """
    with run_logger.stage("resolve"):
        log.info("Input company name: %r", company_name)
        result = {"query": company_name, "candidates": [], "chosen": None,
                  "choice_method": None, "error": None}

        try:
            result["candidates"] = search_candidates(company_name)
        except Exception as error:  # no internet, Yahoo down, blocked request...
            result["error"] = f"Search failed: {error}"
            log.error(result["error"])
            log.debug("Details", exc_info=True)  # traceback goes to run.log only
            run_logger.save_json(run_dir, "01_resolve.json", result)
            return None

        log.info("Found %d stock candidate(s): %s", len(result["candidates"]),
                 [c["symbol"] for c in result["candidates"]])

        if not result["candidates"]:
            result["error"] = "No stock matches this name"
            log.error(result["error"])
            run_logger.save_json(run_dir, "01_resolve.json", result)
            return None

        chosen, method = choose_candidate(result["candidates"], input_fn)
        result["chosen"], result["choice_method"] = chosen, method
        if chosen:
            log.info("Chosen: %s (%s) - %s", chosen["symbol"], chosen["name"], method)
        else:
            log.warning("No ticker chosen (%s)", method)

        run_logger.save_json(run_dir, "01_resolve.json", result)
        return chosen


if __name__ == "__main__":
    name = input("Company name: ").strip()
    if not name:
        print("Please type a company name.")
    else:
        folder = run_logger.start_run(f"resolve {name}")
        run_logger.write_run_meta(folder, company_input=name)
        chosen = resolve_ticker(name, folder)
        if chosen:
            print(f"\nTicker: {chosen['symbol']}  ({chosen['name']}, {chosen['exchange']})")
        else:
            print("\nCould not resolve a ticker (see run.log).")
        print(f"Saved to: {folder}")
