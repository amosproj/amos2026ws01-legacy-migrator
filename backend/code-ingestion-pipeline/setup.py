"""Install the reference loader and Graphify into one Python 3.12 virtual environment."""

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12) or sys.prefix == sys.base_prefix:
        print(
            "Run setup with a Python 3.12 virtual environment's Python executable.",
            file=sys.stderr,
        )
        return 1

    directory = Path(__file__).resolve().parent
    print(f"Installing the reference loader and Graphify into: {sys.prefix}", flush=True)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(directory / "requirements.txt"),
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    print(
        "Setup complete. Set PYTHONPATH to src and the backend directory, "
        "then run: python -m migration_assistant.bootstrap.cli"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
