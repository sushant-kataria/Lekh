#!/usr/bin/env python3
"""Lekh launcher - see `python3 lekh.py --help`."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from lekhlib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv))
