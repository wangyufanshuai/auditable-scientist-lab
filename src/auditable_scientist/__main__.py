"""Versioned package CLI entry point; historical console-script CLI remains intact."""

from .cli_v2 import main


if __name__ == "__main__":
    raise SystemExit(main())
