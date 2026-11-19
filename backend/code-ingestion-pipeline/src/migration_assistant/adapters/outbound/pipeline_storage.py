"""Create run directories and write local ingestion artifacts."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from migration_assistant.domain.sources import SourceFile


class LocalPipelineStorage:
    def create_run(self, output: Path) -> Path:
        output.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-")
        return Path(tempfile.mkdtemp(prefix=stamp, dir=output))

    def write_sources(self, out: Path, files: list[SourceFile]) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            for file in files:
                handle.write(file.model_dump_json(by_alias=True) + "\n")
