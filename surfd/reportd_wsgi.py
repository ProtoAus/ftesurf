"""Gunicorn entry point for reportd (ftesurf-reportd.service)."""
import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s %(levelname)s [%(process)d] %(message)s")

from reportd import create_app  # noqa: E402

app = create_app()
