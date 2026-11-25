"""Import the pinned demo stage inside the prebuilt tester image."""

from pathlib import Path
from shutil import copyfile, copytree
from tempfile import TemporaryDirectory

from migration_assistant.api import ingest_step
from migration_assistant.domain.reference_source import load_config


def main() -> None:
    with TemporaryDirectory() as temporary:
        workspace = Path(temporary)
        # Git's local clone requires the source to be owned by the caller.
        reference = copytree("/reference", workspace / "reference", symlinks=True)
        config = load_config("/tester/reference-source.yaml").model_copy(
            update={
                "source": str(reference),
                "stage": "step-06",
                "components": [],
                "workspace": workspace / "checkout",
            }
        )
        result = ingest_step(
            config, workspace / "runs", progress=lambda message: print(message, flush=True)
        )
        destination = Path("/graph-run/current")
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("snapshot-identity.json", "sources.jsonl"):
            copyfile(result.run_directory / name, destination / name).chmod(0o644)
        print(
            f"Imported {result.entity_count} entities and {result.relationship_count} "
            f"relationships for step-06 ({result.snapshot_id}).",
            flush=True,
        )


if __name__ == "__main__":
    main()
