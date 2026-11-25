"""Resolve first-party direct dependency edges from the committed lockfiles."""
import json
import re
import tomllib
from pathlib import Path


def normalize(name):
    return re.sub(r"[-_.]+", "-", name or "").lower()


def direct_edges(root):
    """Return (parent ecosystem/name/version, child ecosystem/name/version) edges."""
    edges = []
    uv = tomllib.loads((root/"backend/uv.lock").read_text())
    uv_packages = uv.get("package", [])
    backend = next((item for item in uv_packages if normalize(item.get("name")) == "sunsettracker-backend"), None)
    if backend:
        backend_version = backend.get("version", "0.1.0")
        edges.append((("generic", "sunsettracker", "0.1.0"), ("pypi", backend["name"], backend_version)))
        for dependency in backend.get("dependencies", []):
            name = dependency.get("name")
            if not name:
                continue
            for locked in uv_packages:
                if normalize(locked.get("name")) == normalize(name):
                    edges.append((("pypi", backend["name"], backend_version), ("pypi", locked["name"], locked.get("version", ""))))

    package_lock = json.loads((root/"frontend/package-lock.json").read_text())
    packages = package_lock.get("packages", {})
    frontend = packages.get("") or json.loads((root/"frontend/package.json").read_text())
    frontend_name = frontend.get("name", "amos-sunset-tracker-frontend")
    frontend_version = frontend.get("version", "0.1.0")
    edges.append((("generic", "sunsettracker", "0.1.0"), ("npm", frontend_name, frontend_version)))
    for dependency_name in sorted(set(frontend.get("dependencies", {})) | set(frontend.get("devDependencies", {}))):
        path = "node_modules/"+dependency_name
        locked = packages.get(path)
        if not locked:
            continue
        name = locked.get("name", dependency_name)
        edges.append((("npm", frontend_name, frontend_version), ("npm", name, locked.get("version", ""))))

    # Syft can omit optional or peer dependency edges even when npm's lockfile
    # resolves both ends. Add those relationships from the v3 lockfile itself.
    # Walk outward through Node's nested node_modules locations so scoped and
    # nested packages resolve to the exact locked version.
    for parent_path, parent in packages.items():
        if not parent_path.startswith("node_modules/") or not parent.get("version"):
            continue
        dependencies = {}
        for field in ("dependencies", "optionalDependencies", "peerDependencies"):
            dependencies.update(parent.get(field, {}))
        prefixes = [parent_path]
        current = parent_path
        while "/node_modules/" in current:
            current = current.rsplit("/node_modules/", 1)[0]
            if current not in prefixes:
                prefixes.append(current)
        prefixes.append("")
        for dependency_name in sorted(dependencies):
            child = None
            for prefix in prefixes:
                candidate = f"{prefix}/node_modules/{dependency_name}" if prefix else f"node_modules/{dependency_name}"
                child = packages.get(candidate)
                if child:
                    break
            if child and child.get("version"):
                edges.append((
                    ("npm", parent.get("name", parent_path.rsplit("node_modules/", 1)[-1]), parent["version"]),
                    ("npm", child.get("name", dependency_name), child["version"]),
                ))

    return edges
