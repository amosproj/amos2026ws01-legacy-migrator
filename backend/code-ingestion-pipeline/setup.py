"""Add Graphify to the virtual environment prepared by the reference-loader guide."""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12) or sys.prefix == sys.base_prefix:
        print("Activate a Python 3.12 virtual environment before running setup.", file=sys.stderr)
        return 1
    if any(importlib.util.find_spec(name) is None for name in ("pydantic", "yaml")):
        print(
            "Complete Documentation/ingestion/reference-loader.md setup first, "
            "then run this script in the same environment.",
            file=sys.stderr,
        )
        return 1

    directory = Path(__file__).resolve().parent
    print(f"Installing Graphify into the existing environment: {sys.prefix}", flush=True)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(directory / "requirements-graphify.txt"),
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    print("Setup complete. From backend/code-ingestion-pipeline/, run: python run_pipeline.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
