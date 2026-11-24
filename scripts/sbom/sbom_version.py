"""Compute a stable SBOM version from source inputs and generator versions."""
import hashlib
import json
import os
from pathlib import Path


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", ".cache",
    "__pycache__", ".pytest_cache", ".ruff_cache", "ba",
}
EXCLUDED_FILES = {"sbom.spdx.json", "THIRD_PARTY_NOTICES.md"}
INCLUDED_DIRS = ("backend", "frontend", "scripts/sbom", ".github")
INCLUDED_FILES = ("README.md", "docker-compose.yml")


def _source_files(root):
    files = {root/name for name in INCLUDED_FILES if (root/name).is_file()}
    for directory in INCLUDED_DIRS:
        base = root/directory
        if not base.is_dir():
            continue
        for current, directories, filenames in os.walk(base):
            directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
            for filename in filenames:
                if filename in EXCLUDED_FILES:
                    continue
                path = Path(current)/filename
                if path.is_file() and not path.is_symlink():
                    files.add(path)
    for path in root.glob("LICENSE*"):
        if path.is_file():
            files.add(path)
    licenses_dir = root/"LICENSES"
    if licenses_dir.is_dir():
        files.update(path for path in licenses_dir.rglob("*") if path.is_file() and not path.is_symlink())
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def compute_sbom_version(root, syft_version):
    """Hash the source inventory and tool versions, omitting generated SBOMs."""
    root = Path(root)
    digest = hashlib.sha256()
    digest.update(f"Syft {syft_version}; AMOS SBOM post-processor 1.0\0".encode())
    for path in _source_files(root):
        relative = path.relative_to(root).as_posix().encode()
        content = path.read_bytes()
        if path.name == "registry-license-snapshot.json":
            # Retrieval timestamps describe when evidence was fetched, not the
            # dependency inventory. Ignore them so an identical snapshot refresh
            # does not change the SBOM identity on every CI run.
            snapshot = json.loads(content)

            def remove_retrieval_times(value):
                if isinstance(value, dict):
                    return {
                        key: remove_retrieval_times(item)
                        for key, item in value.items()
                        if key != "retrievedAt"
                    }
                if isinstance(value, list):
                    return [remove_retrieval_times(item) for item in value]
                return value

            content = json.dumps(
                remove_retrieval_times(snapshot),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        content_digest = hashlib.sha256(content).digest()
        digest.update(relative+b"\0"+content_digest+b"\0")
    return digest.hexdigest()
