"""Versioned package CLI entry point with historical replay routing."""

from .cli_v3 import main


if __name__ == "__main__":
    raise SystemExit(main())
