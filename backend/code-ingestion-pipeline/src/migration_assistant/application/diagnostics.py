"""Retain Python extraction diagnostics in the former subprocess log files."""

import logging
import traceback
from collections.abc import Generator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import TextIO


@contextmanager
def capture_diagnostics(output: TextIO) -> Generator[None]:
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with redirect_stdout(output), redirect_stderr(output):
            try:
                yield
            except Exception:
                traceback.print_exc(file=output)
                raise
    finally:
        root.removeHandler(handler)
