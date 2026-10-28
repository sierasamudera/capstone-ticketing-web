"""Entry point agar `python -m ticketing` menjalankan CLI."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
