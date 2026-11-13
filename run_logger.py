"""
run_logger.py - one folder + one log per query.

What this file does:
    Creates runs/<YYYY-MM-DD_HH-MM-SS>_<slug>/, sets up Python logging to write
    to both run.log (in that folder) and the console, and gives small helpers
    to save JSON / text / CSV files into the folder.
Input:
    A label such as the company name ("Apple Inc") when a run starts.
Output:
    The run folder path; log lines in run.log and on screen; saved files.

How to explain this in an interview:
    "Every query gets its own timestamped folder, so I can open it later and see
    exactly what was fetched, filtered and scored. Each module logs under its
    own stage name, and a filter masks API keys so they can never leak into logs."
"""

import json
import logging
import platform
import re
import time
from contextlib import contextmanager
from datetime import datetime
from importlib import metadata
from pathlib import Path

import config

LOG_FORMAT = "%(asctime)s | %(name)-10s | %(levelname)-7s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Libraries whose versions go into 00_run_meta.json (missing ones are skipped).
TRACKED_LIBRARIES = ["yfinance", "pandas", "numpy", "requests", "python-dotenv",
                     "google-genai", "transformers", "torch"]


def slugify(text: str, max_length: int = 40) -> str:
    """Turn 'Apple Inc.' into 'apple-inc' so it is safe as a folder name."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length] or "query"


def create_run_folder(label: str) -> Path:
    """Create runs/<timestamp>_<slug>/ and return its path."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = config.RUNS_DIR / f"{timestamp}_{slugify(label)}"
    # exist_ok=True: two runs in the same second for the same label share a folder
    # instead of crashing; rare and harmless for a console tool.
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _redact_secrets(record: logging.LogRecord) -> bool:
    """Logging filter: replace any API key value in a log line with '***'.

    Defence in depth: the code should never log a key, but if an error message
    from a library happens to contain one, it still will not reach the log.
    """
    message = record.getMessage()
    for secret in (config.GEMINI_API_KEY, config.NEWS_API_KEY):
        if secret:
            message = message.replace(secret, "***")
    record.msg, record.args = message, None
    return True  # True = keep the record (we only modified it)


def setup_logging(run_dir: Path) -> None:
    """Send log lines to run_dir/run.log (DEBUG and up) and the console (INFO and up).

    The file gets DEBUG so tracebacks of errors are kept for debugging, while the
    console stays clean and only shows short messages.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # Remove handlers from a previous run so lines are not written twice.
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    file_handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
        handler.addFilter(_redact_secrets)
        root.addHandler(handler)

    # Third-party libraries are chatty at DEBUG; we only want their warnings.
    for noisy in ("yfinance", "urllib3", "peewee", "httpx", "httpcore",
                  "google", "filelock", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def start_run(label: str) -> Path:
    """Create the run folder and set up logging. Returns the folder path."""
    run_dir = create_run_folder(label)
    setup_logging(run_dir)
    logging.getLogger("run").info("Run folder: %s", run_dir)
    return run_dir


@contextmanager
def stage(name: str):
    """Log start, end and duration of a pipeline stage.

    Usage:
        with stage("prices"):
            ...work...
    """
    log = logging.getLogger(name)
    log.info("START")
    started = time.perf_counter()
    try:
        yield log
    finally:
        log.info("END (%.2fs)", time.perf_counter() - started)


def save_json(run_dir: Path, filename: str, data) -> Path:
    """Write data as pretty JSON. default=str turns dates/Paths into text."""
    path = run_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")
    logging.getLogger("run").debug("Saved %s", path.name)
    return path


def save_text(run_dir: Path, filename: str, text: str) -> Path:
    """Write plain text / markdown (also used for prompts_used/*.txt)."""
    path = run_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    logging.getLogger("run").debug("Saved %s", path.name)
    return path


def save_csv(run_dir: Path, filename: str, dataframe) -> Path:
    """Write a pandas DataFrame to CSV."""
    path = run_dir / filename
    dataframe.to_csv(path)
    logging.getLogger("run").debug("Saved %s", path.name)
    return path


def library_versions() -> dict:
    """Installed versions of the libraries we use (helps reproduce a run)."""
    versions = {"python": platform.python_version()}
    for name in TRACKED_LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def write_run_meta(run_dir: Path, company_input: str) -> Path:
    """Save 00_run_meta.json: what was asked, when, with which settings."""
    meta = {
        "company_input": company_input,
        "start_time": datetime.now().isoformat(timespec="seconds"),
        "models": {
            "gemini_model": config.GEMINI_MODEL,
            "sentiment_provider": config.SENTIMENT_PROVIDER,
            "news_provider": config.NEWS_PROVIDER,
        },
        "config": config.config_snapshot(),
        "library_versions": library_versions(),
    }
    return save_json(run_dir, "00_run_meta.json", meta)


if __name__ == "__main__":
    # Demo: create a folder, log from two fake stages, save a JSON and a text file.
    label = input("Label for a test run folder (e.g. 'logger test'): ").strip() or "logger-test"
    folder = start_run(label)
    write_run_meta(folder, company_input=label)
    with stage("demo") as log:
        log.info("This line goes to the console and to run.log")
        save_json(folder, "demo.json", {"hello": "world", "when": datetime.now()})
        save_text(folder, "demo.txt", "plain text works too\n")
    print(f"\nOpen this folder to see the files: {folder}")
