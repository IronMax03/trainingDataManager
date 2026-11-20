"""Entry point: run with `tdm` or `python -m tdm`."""

import sys

from tdm import __version__


def main() -> int:
    print(f"tdm {__version__}: the interactive shell is not built yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
