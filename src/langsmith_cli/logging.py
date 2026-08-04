"""Logging configuration for langsmith-fetch."""

import logging
import sys

logger = logging.getLogger("langsmith-fetch")


def setup_logging(verbose: bool = False):
    """Configure logging for the application.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
