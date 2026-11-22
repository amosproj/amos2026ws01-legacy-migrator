#!/usr/bin/env python3
"""Post-process Syft's SPDX 3.0.1 JSON for the repository source release."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tarfile
import tomllib
import urllib.parse
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from license_metadata import normalize_license
from lockfile_relationships import direct_edges
from sbom_version import compute_sbom_version


SBOM_URI = "https://github.com/amosproj/amos2026ws01-legacy-migrator"
PROJECT_NAME = "AMOS Project"
CREATION_INFO_ID = "_:CreationInfo-AMOS"
COMPLETENESS_COMPLETE = (
    "https://spdx.org/rdf/3.0.1/terms/Core/RelationshipCompleteness/complete"
)
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", ".cache",
    "__pycache__", ".pytest_cache", ".ruff_cache", "ba",
}
EXCLUDED_FILES = {
    "sbom.spdx.json", "THIRD_PARTY_NOTICES.md",
}


def norm(value: str | None) -> str:
    return re.sub(r"[-_.]+", "-", value or "").lower()


def package_key(ecosystem: str | None, name: str, version: str) -> tuple[str, str, str]:
    return (ecosystem or "", norm(name), version or "")


def purl_parts(package: dict) -> tuple[str | None, str, str]:
    purl = package.get("software_packageUrl", "")
    if not isinstance(purl, str) or not purl.startswith("pkg:"):
        return None, package.get("name", ""), package.get("software_packageVersion", "")
    value = purl[4:].split("?", 1)[0].split("#", 1)[0]
    ecosystem, _, path = value.partition("/")
    name_version = path.rsplit("@", 1)
    name = urllib.parse.unquote(name_version[0])
    version = urllib.parse.unquote(name_version[1]) if len(name_version) == 2 else ""
    return ecosystem, name, version


def package_lock_name(path: str, metadata: dict) -> str:
    name = metadata.get("name") or path.rsplit("node_modules/", 1)[-1]
    return name.rsplit("node_modules/", 1)[-1]


def agent_name(value: object) -> tuple[str, str] | None:
    if isinstance(value, dict):
        value = value.get("name")
    value = str(value or "").strip()
    if not value:
        return None
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme == "mailto":
        return None
    match = re.match(r"^(.*?)\s*<([^<>]+)>$", value)
    if match:
        value = match.group(1).strip()
    if not value or "@" in value or value.casefold() in {"unknown", "none", "n/a", "not specified"}:
        return None
    org_markers = (
        " foundation", " authority", " team", " project", " software", " inc",
        " llc", " ltd", " limited", " corporation", " corp", " gmbh", " company",
        " university", " institute", " association",
    )
    kind = "Organization" if any(marker in " " + value.casefold() for marker in org_markers) else "Person"
    return kind, value


def agent_contact(metadata: dict, registry: dict, is_project: bool) -> tuple[str, str, str]:
    if is_project:
        return "Organization", PROJECT_NAME, SBOM_URI
    email_value = registry.get("originatorEmail")
    name_value = registry.get("originator")
    url_value = registry.get("originatorUrl")
    if not name_value:
        for key in ("author", "maintainer"):
            candidate = agent_name(metadata.get(key))
            if candidate:
                _, name_value = candidate
                break
    for field in ("author_email", "maintainer_email"):
        if not email_value and metadata.get(field):
            email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", metadata[field], re.I)
            if email_match:
                email_value = email_match.group(0)
    if not url_value:
        for field in ("home_page", "homepage", "project_url", "repository"):
            candidate = metadata.get(field)
            if isinstance(candidate, dict):
                candidate = candidate.get("url")
            if isinstance(candidate, str) and candidate.startswith(("https://", "http://")):
                url_value = candidate
                break
    if not name_value:
        name_value = "Unknown component creator"
    parsed = agent_name(name_value)
    kind, name = parsed or ("Organization", str(name_value))
    return kind, name, ("mailto:" + email_value if email_value else str(url_value or ""))


def add_agent(graph: list[dict], cache: dict, kind: str, name: str, contact: str) -> str:
    key = (kind, name, contact)
    if key in cache:
        return cache[key]
    agent_id = "SPDXRef:Agent-" + hashlib.sha256("\0".join(key).encode()).hexdigest()[:20]
    external_identifier = None
    if contact.startswith("mailto:"):
        external_identifier = {
            "externalIdentifierType": "email",
            "identifier": contact.removeprefix("mailto:"),
            "type": "ExternalIdentifier",
        }
    elif contact.startswith(("https://", "http://")):
        external_identifier = {
            "externalIdentifierType": "urlScheme",
            "identifier": contact,
            "type": "ExternalIdentifier",
        }
    item = {
        "creationInfo": CREATION_INFO_ID,
        "name": name,
        "spdxId": agent_id,
        "type": kind,
    }
    if external_identifier:
        item["externalIdentifier"] = [external_identifier]
    graph.append(item)
    cache[key] = agent_id
    return agent_id


def deterministic_source_archive(root: Path, component: str, version: str) -> tuple[str, str]:
    """Hash a canonical source archive used to identify this source SBOM's root."""
    if component == "SunsetTracker":
        paths = [root / "backend", root / "frontend", root / "docker-compose.yml", root / "LICENSE"]
    elif component == "sunsettracker-backend":
        paths = [
            root / "backend/app", root / "backend/shared_contracts", root / "backend/schemas",
            root / "backend/pyproject.toml", root / "backend/uv.lock", root / "backend/LICENSE",
        ]
    else:
        paths = [
            root / "frontend/src", root / "frontend/public", root / "frontend/package.json",
            root / "frontend/package-lock.json", root / "frontend/nginx.conf", root / "frontend/LICENSE",
        ]
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        files: list[Path] = []
        for path in paths:
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                for current, directories, names in os.walk(path):
                    directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
                    for name in sorted(names):
                        candidate = Path(current) / name
                        if candidate.is_symlink() or candidate.name in EXCLUDED_FILES:
                            continue
                        files.append(candidate)
        for path in sorted(set(files), key=lambda item: item.relative_to(root).as_posix()):
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info, BytesIO(data))
    archive_bytes = buffer.getvalue()
    filename = f"{component}-{version}-source.tar"
    return filename, hashlib.sha512(archive_bytes).hexdigest()


def npm_artifact(name: str, version: str, lock_entries: dict) -> dict | None:
    candidates = lock_entries.get((norm(name), version), [])
    for path, metadata in candidates:
        url = metadata.get("resolved")
        integrity = metadata.get("integrity", "")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        for token in integrity.split():
            if token.startswith("sha512-"):
                try:
                    digest = base64.b64decode(token.removeprefix("sha512-").split("?", 1)[0], validate=True).hex()
                except (ValueError, base64.binascii.Error):
                    continue
                filename = Path(urllib.parse.urlsplit(url).path).name
                if filename:
                    return {"filename": filename, "sha512": digest, "url": url}
    return None


def relation(from_id: str, relation_type: str, to_ids: list[str], label: str, complete: bool = False) -> dict:
    relation_id = "SPDXRef:Relationship-" + hashlib.sha256(
        (from_id + "\0" + relation_type + "\0" + "\0".join(sorted(to_ids)) + "\0" + label).encode()
    ).hexdigest()[:20]
    item = {
        "creationInfo": CREATION_INFO_ID,
        "from": from_id,
        "relationshipType": relation_type,
        "spdxId": relation_id,
        "to": sorted(set(to_ids)),
        "type": "Relationship",
    }
    if complete:
        item["completeness"] = COMPLETENESS_COMPLETE
    return item


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: enrich_sbom.py SYFT.spdx.json PYTHON-DISTS.json REPOSITORY THIRD_PARTY_NOTICES.md")
    bom_path, py_meta_path, root_arg, notices_path = map(Path, sys.argv[1:])
    root = root_arg.resolve()
    bom = json.loads(bom_path.read_text(encoding="utf-8"))
    if not isinstance(bom.get("@graph"), list):
        raise SystemExit("Syft output must be SPDX 3 JSON-LD (spdx-json@3.0)")
    raw_graph = bom["@graph"]
    syft_creation = next((item for item in raw_graph if item.get("type") == "CreationInfo"), {})
    syft_tool = next((item for item in raw_graph if item.get("type") == "Tool" and str(item.get("name", "")).startswith("syft-")), None)
    if not syft_tool:
        raise SystemExit("Syft tool version missing from SPDX 3 creation information")
    syft_version = syft_tool["name"].removeprefix("syft-")
    digest = compute_sbom_version(root, syft_version)
    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    py = json.loads(py_meta_path.read_text(encoding="utf-8"))
    python_metadata = {
        ("pypi", norm(item.get("name")), item.get("version", "")): item
        for item in py.values()
    }
    npm_lock = json.loads((root / "frontend/package-lock.json").read_text(encoding="utf-8"))
    npm_root = json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))
    npm_lock_entries: dict[tuple[str, str], list[tuple[str, dict]]] = defaultdict(list)
    for lock_path, metadata in npm_lock.get("packages", {}).items():
        if not lock_path.startswith("node_modules/"):
            continue
        name = package_lock_name(lock_path, metadata)
        npm_lock_entries[(norm(name), metadata.get("version", ""))].append((lock_path, metadata))
    registry_path = root / "scripts/sbom/registry-license-snapshot.json"
    registry_snapshot = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"packages": {}}

    # Keep only locked runtime packages plus the two first-party applications and
    # the product root. This drops packages found in local ingestion fixtures.
    candidate_packages = []
    for package in raw_graph:
        if package.get("type") != "software_Package":
            continue
        ecosystem, name, version = purl_parts(package)
        key = package_key(ecosystem, name, version)
        if name == "SunsetTracker":
            candidate_packages.append(package)
        elif ecosystem == "pypi" and (key in python_metadata or norm(name) == "sunsettracker-backend"):
            candidate_packages.append(package)
        elif ecosystem == "npm":
            matches = npm_lock_entries.get((norm(name), version), [])
            if norm(name) == norm(npm_root.get("name")) or (
                matches and any(meta.get("dev") is not True for _, meta in matches)
            ):
                candidate_packages.append(package)

    # Deduplicate duplicate catalog records for an identical package URL/version.
    package_by_identity: dict[tuple[str, str], dict] = {}
    old_to_new: dict[str, str] = {}
    for package in candidate_packages:
        purl = package.get("software_packageUrl", "")
        version = package.get("software_packageVersion", "")
        identity = (purl, version)
        previous = package_by_identity.get(identity)
        if previous is None or len(package) > len(previous):
            package_by_identity[identity] = package
    packages = list(package_by_identity.values())
    package_ids = {package.get("spdxId") for package in packages}
    package_by_key: dict[tuple[str, str, str], dict] = {}
    for package in packages:
        eco, name, version = purl_parts(package)
        package_by_key[package_key(eco, name, version)] = package

    root_package = next((package for package in packages if package.get("name") == "SunsetTracker"), None)
    if root_package is None:
        raise SystemExit("Syft did not identify the SunsetTracker product package")
    root_package.setdefault("software_packageUrl", "pkg:generic/sunsettracker@0.1.0")
    root_package["software_packageVersion"] = root_package.get("software_packageVersion") or "0.1.0"
    root_key = package_key("generic", "sunsettracker", root_package["software_packageVersion"])
    package_by_key[root_key] = root_package

    local_licenses: dict[tuple[str, str, str], tuple[str, dict]] = {}
    for key, metadata in python_metadata.items():
        license_expr = normalize_license(metadata.get("license_expression") or metadata.get("license"))
        if not license_expr:
            for classifier in metadata.get("classifiers", []):
                if classifier.startswith("License :: OSI Approved :: "):
                    license_expr = normalize_license(classifier.rsplit(" :: ", 1)[-1])
                    if license_expr:
                        break
        if license_expr:
            local_licenses[key] = (license_expr, metadata.get("licence_files", {}))

    npm_node_modules = Path(os.environ.get("SBOM_FRONTEND_NODE_MODULES", str(root / "frontend/node_modules")))
    for (normalized_name, version), entries in npm_lock_entries.items():
        if all(metadata.get("dev") is True for _, metadata in entries):
            continue
        path, metadata = entries[0]
        name = package_lock_name(path, metadata)
        license_expr = normalize_license(metadata.get("license"))
        license_texts: dict[str, str] = {}
        package_json = npm_node_modules / path.removeprefix("node_modules/") / "package.json"
        if package_json.is_file():
            try:
                installed_metadata = json.loads(package_json.read_text(encoding="utf-8"))
                license_expr = normalize_license(installed_metadata.get("license")) or license_expr
                for license_path in package_json.parent.iterdir():
                    if license_path.is_file() and license_path.name.lower().split(".", 1)[0] in {
                        "license", "licence", "notice", "copying",
                    }:
                        license_texts[license_path.name] = license_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, json.JSONDecodeError):
                pass
        if license_expr:
            local_licenses[("npm", normalized_name, version)] = (license_expr, license_texts)

    # Collect Syft's original declared license strings as a last deterministic
    # source when installed/lock metadata does not contain a license.
    syft_licenses: dict[str, str] = {}
    element_by_id = {item.get("spdxId"): item for item in raw_graph if item.get("spdxId")}
    for item in raw_graph:
        if item.get("type") != "Relationship" or item.get("relationshipType") not in ("hasDeclaredLicense", "hasConcludedLicense"):
            continue
        target_ids = item.get("to", []) if isinstance(item.get("to"), list) else [item.get("to")]
        target_names = []
        for target_id in target_ids:
            target = element_by_id.get(target_id, {})
            candidate = target.get("name") or target.get("simplelicensing_licenseExpression")
            candidate = normalize_license(candidate)
            if candidate:
                target_names.append(candidate)
        if target_names:
            syft_licenses[item.get("from", "")] = " OR ".join(sorted(set(target_names)))

    py_lock = tomllib.loads((root / "backend/uv.lock").read_text(encoding="utf-8"))
    python_artifact_by_key: dict[tuple[str, str, str], dict] = {}
    for item in py_lock.get("package", []):
        key = package_key("pypi", item.get("name", ""), item.get("version", ""))
        if key not in python_metadata:
            continue
        snapshot = registry_snapshot.get("packages", {}).get(f"pypi:{key[1]}@{key[2]}", {})
        artifact = snapshot.get("artifact")
        if artifact and artifact.get("sha256") in {
            candidate.get("hash", "").removeprefix("sha256:")
            for candidate in ([item.get("sdist")] if item.get("sdist") else []) + item.get("wheels", [])
        }:
            python_artifact_by_key[key] = artifact

    # Normalize package identity, create SPDX agent/license/file nodes, and retain
    # source evidence for the rendered Legal Notices page.
    out_graph = []
    agent_cache: dict[tuple[str, str, str], str] = {}
    licenses: dict[str, str] = {}
    artifacts: list[dict] = []
    notices: list[str] = []
    evidence_by_id: dict[str, str] = {}
    package_for_canonical: dict[tuple[str, str, str], dict] = {}
    for package in packages:
        ecosystem, name, version = purl_parts(package)
        name = package.get("name") or name
        key = package_key(ecosystem, name, version)
        first_party = ecosystem == "generic" or norm(name) in {
            "sunsettracker", "sunsettracker-backend", norm(npm_root.get("name")),
        }
        registry_key = f"{ecosystem}:{key[1]}@{key[2]}"
        registry = registry_snapshot.get("packages", {}).get(registry_key, {})
        metadata = python_metadata.get(key, {})
        if ecosystem == "npm":
            matches = npm_lock_entries.get((key[1], key[2]), [])
            npm_meta = matches[0][1] if matches else {}
            node_modules_package = npm_node_modules / matches[0][0].removeprefix("node_modules/") / "package.json" if matches else None
            if node_modules_package and node_modules_package.is_file():
                try:
                    metadata = json.loads(node_modules_package.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    metadata = npm_meta
            else:
                metadata = npm_meta
        license_item = ("MIT", {}) if first_party else local_licenses.get(key)
        license_source = "repository LICENSE" if first_party else "locked package metadata"
        if not license_item and registry.get("license"):
            normalized = normalize_license(registry.get("license"))
            if normalized:
                license_item = (normalized, {})
                license_source = f"{registry.get('source', 'registry snapshot')}: {registry.get('sourceUrl', '')}"
        if not license_item and syft_licenses.get(package.get("spdxId")):
            normalized = normalize_license(syft_licenses[package["spdxId"]])
            if normalized:
                license_item = (normalized, {})
                license_source = "Syft package/license catalog"
        if license_item:
            license_expr = license_item[0]
            licenses[package["spdxId"]] = license_expr
            evidence_by_id[package["spdxId"]] = license_source
            for filename, contents in license_item[1].items():
                if contents:
                    notices.append(
                        f"### {name} {version} — {filename}\n\n```text\n{contents.rstrip()}\n```"
                    )
        else:
            licenses[package["spdxId"]] = "NOASSERTION"
            evidence_by_id[package["spdxId"]] = "No license evidence in lockfile, installed metadata, Syft, or committed registry snapshot"

        agent_type, creator_name, contact = agent_contact(metadata, registry, first_party)
        agent_id = add_agent(out_graph, agent_cache, agent_type, creator_name, contact)
        package["creationInfo"] = CREATION_INFO_ID
        package["originatedBy"] = [agent_id]
        package.pop("suppliedBy", None)
        package.pop("verifiedUsing", None)
        package["software_sourceInfo"] = (package.get("software_sourceInfo", "") + "; creator/license evidence from pinned registry and lockfile metadata").strip("; ")
        package_for_canonical[key] = package

        if first_party:
            filename, sha512 = deterministic_source_archive(root, name, version or "0.1.0")
            artifact = {"filename": filename, "sha512": sha512, "url": SBOM_URI}
            package["software_downloadLocation"] = SBOM_URI
        elif ecosystem == "npm":
            artifact = npm_artifact(name, version, npm_lock_entries)
        elif ecosystem == "pypi":
            artifact = python_artifact_by_key.get(key)
        else:
            artifact = None
        if not artifact or not re.fullmatch(r"[0-9a-fA-F]{128}", str(artifact.get("sha512", ""))):
            raise SystemExit(
                f"missing verified SHA-512 distribution artifact for {name} {version}; "
                "refresh the committed registry snapshot or complete the manual component entry"
            )
        if not artifact.get("filename"):
            raise SystemExit(f"distribution filename missing for {name} {version}")
        if artifact.get("url"):
            package["software_downloadLocation"] = artifact["url"]
        file_id = "SPDXRef:DistributionArtifact-" + hashlib.sha256(
            f"{key[0]}\0{key[1]}\0{key[2]}\0{artifact['filename']}\0{artifact['sha512']}".encode()
        ).hexdigest()[:20]
        file_node = {
            "creationInfo": CREATION_INFO_ID,
            "name": artifact["filename"],
            "software_additionalPurpose": ["archive", "container"],
            "software_fileKind": "file",
            "spdxId": file_id,
            "type": "software_File",
            "verifiedUsing": [{
                "algorithm": "sha512",
                "hashValue": artifact["sha512"].lower(),
                "type": "Hash",
            }],
        }
        artifacts.append(file_node)
        evidence_by_id[package["spdxId"]] += f"; artifact={artifact.get('url') or artifact['filename']}; sha512={artifact['sha512']}"

    # Preserve Syft's lockfile-derived transitive edges after filtering; add the
    # first-party direct edges explicitly from both committed lockfiles.
    dependency_edges: set[tuple[str, str]] = set()
    for item in raw_graph:
        if item.get("type") != "Relationship" or item.get("relationshipType") not in ("dependsOn", "https://spdx.org/rdf/3.0.1/terms/Core/RelationshipType/dependsOn"):
            continue
        from_id = item.get("from")
        target_ids = item.get("to", []) if isinstance(item.get("to"), list) else [item.get("to")]
        for target in target_ids:
            if from_id in package_ids and target in package_ids:
                dependency_edges.add((from_id, target))
    for parent, child in direct_edges(root):
        parent_key = package_key(*parent)
        child_key = package_key(*child)
        parent_package = package_by_key.get(parent_key)
        child_package = package_by_key.get(child_key)
        if parent_package and child_package:
            dependency_edges.add((parent_package["spdxId"], child_package["spdxId"]))

    license_nodes: dict[str, dict] = {}
    generated_relations: list[dict] = []
    for package in packages:
        expression = licenses[package["spdxId"]]
        expression_id = "SPDXRef:LicenseExpression-" + hashlib.sha256(expression.encode()).hexdigest()[:20]
        license_nodes.setdefault(expression_id, {
            "creationInfo": CREATION_INFO_ID,
            "name": expression,
            "simplelicensing_licenseExpression": expression,
            "spdxId": expression_id,
            "type": "simplelicensing_LicenseExpression",
        })
        for kind in ("hasDeclaredLicense", "hasConcludedLicense"):
            generated_relations.append(relation(package["spdxId"], kind, [expression_id], expression))
        generated_relations.append(relation(
            package["spdxId"], "hasDistributionArtifact",
            [next(file["spdxId"] for file in artifacts if file["spdxId"].endswith(hashlib.sha256(
                f"{purl_parts(package)[0]}\0{purl_parts(package)[1] and norm(purl_parts(package)[1])}\0{purl_parts(package)[2]}\0{file['name']}\0{file['verifiedUsing'][0]['hashValue']}".encode()
            ).hexdigest()[:20]))],
            "distribution artifact",
        ))
    for from_id, to_id in sorted(dependency_edges):
        generated_relations.append(relation(from_id, "dependsOn", [to_id], "lockfile dependency", complete=True))

    # Rebuild the graph from the cataloged packages and SPDX relationships. This
    # keeps the published document compact and removes incidental source files.
    tool_node = dict(syft_tool)
    tool_node["spdxId"] = "SPDXRef:Tool-Syft-" + syft_version.replace(".", "-")
    tool_node["creationInfo"] = CREATION_INFO_ID
    project_agent = next((item for item in out_graph if item.get("name") == PROJECT_NAME), None)
    if project_agent is None:
        raise SystemExit("failed to create AMOS Project SBOM creator")
    creation_info = {
        "@id": CREATION_INFO_ID,
        "comment": f"SBOM-Version: sha256:{digest}; SPDX 3.0.1 source SBOM; generated from backend/uv.lock and frontend/package-lock.json.",
        "created": created,
        "createdBy": [project_agent["spdxId"]],
        "createdUsing": [tool_node["spdxId"]],
        "specVersion": "3.0.1",
        "type": "CreationInfo",
    }
    # Add the post-processor as a tool without claiming that it produced the inventory.
    postprocessor_id = "SPDXRef:Tool-AMOS-SBOM-Postprocessor-1-0"
    postprocessor = {
        "creationInfo": CREATION_INFO_ID,
        "name": "AMOS SBOM post-processor 1.0",
        "spdxId": postprocessor_id,
        "type": "Tool",
    }
    creation_info["createdUsing"].append(postprocessor_id)
    for package in packages:
        package["creationInfo"] = CREATION_INFO_ID
    cc0 = next((item for item in raw_graph if item.get("type") == "expandedlicensing_ListedLicense" and item.get("name") == "CC0-1.0"), None)
    if cc0 is None:
        cc0 = {
            "creationInfo": CREATION_INFO_ID,
            "name": "CC0-1.0",
            "simplelicensing_licenseText": "NOASSERTION",
            "spdxId": "SPDXRef:DataLicense-CC0-1.0",
            "type": "expandedlicensing_ListedLicense",
        }
    else:
        cc0 = dict(cc0)
        cc0["creationInfo"] = CREATION_INFO_ID
    sbom_id = "SPDXRef:SBOM-1"
    sbom_node = {
        "creationInfo": CREATION_INFO_ID,
        "element": [],
        "rootElement": [root_package["spdxId"]],
        "software_sbomType": ["source"],
        "spdxId": sbom_id,
        "type": "software_Sbom",
    }
    namespace = f"https://spdx.org/spdxdocs/SunsetTracker-{digest}#"
    document_node = {
        "creationInfo": CREATION_INFO_ID,
        "dataLicense": cc0["spdxId"],
        "name": "SunsetTracker",
        "namespaceMap": [{"namespace": namespace, "prefix": "SPDXRef", "type": "NamespaceMap"}],
        "profileConformance": ["core", "software"],
        "rootElement": [sbom_id],
        "spdxId": namespace,
        "type": "SpdxDocument",
    }
    all_elements = out_graph + [tool_node, postprocessor, *packages, *artifacts, *license_nodes.values(), *generated_relations, cc0, sbom_node]
    ids = {item.get("spdxId") for item in all_elements if item.get("spdxId")}
    sbom_node["element"] = sorted(item_id for item_id in ids if item_id != namespace and item_id != sbom_id)
    graph = [creation_info, *all_elements, document_node]
    graph.sort(key=lambda item: (item.get("type", ""), item.get("spdxId", item.get("@id", ""))))
    bom = {"@context": bom.get("@context", "https://spdx.org/rdf/3.0.1/spdx-context.jsonld"), "@graph": graph}

    lines = [
        "# Third-party legal notices", "",
        "Generated from `sbom.spdx.json` and locked package metadata. Review license terms before release.", "",
        "## Dependency licenses", "",
        "| Package | Version | License | Evidence |", "|---|---:|---|---|",
    ]
    for package in sorted(packages, key=lambda item: (item.get("name", "").casefold(), item.get("software_packageVersion", ""))):
        if package.get("name") in ("NOASSERTION", ""):
            continue
        expression = licenses.get(package["spdxId"], "NOASSERTION")
        if expression in ("NOASSERTION", "NONE"):
            continue
        lines.append(
            "| " + package.get("name", "Unknown").replace("|", r"\|") +
            " | " + package.get("software_packageVersion", "Unknown") +
            " | " + expression + " | " + evidence_by_id.get(package["spdxId"], "Package metadata") + " |"
        )
    if notices:
        lines.extend(["", "## Included license and notice texts", "", *sorted(set(notices))])
    bom_path.write_text(json.dumps(bom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    notices_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Generated SPDX 3.0.1: {len(packages)} packages, {len(dependency_edges)} dependency edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
