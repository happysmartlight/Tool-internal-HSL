"""
utils/logger.py
Centralised logging setup.
"""
import logging
import sys
from pathlib import Path

from utils.paths import get_user_data_dir

LOG_FILE = get_user_data_dir() / "app.log"

def get_logger(name: str) -> logging.Logger:
    """Return a named logger with file + console output."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # File handler (always INFO+)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    # Console handler (WARNING+ by default)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
