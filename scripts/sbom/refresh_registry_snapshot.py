#!/usr/bin/env python3
"""Snapshot missing package creator/license metadata and locked PyPI artifact hashes."""
from __future__ import annotations

import base64
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import tomllib
from pathlib import Path

from license_metadata import normalize_license


ROOT = Path(__file__).resolve().parents[2]


def norm(value: str | None) -> str:
    return re.sub(r"[-_.]+", "-", value or "").lower()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AMOS-SBOM/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.read()
    except (OSError, urllib.error.URLError):
        return subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--max-time", "12", url],
            check=True,
            capture_output=True,
            timeout=15,
        ).stdout


def fetch_artifact(url: str) -> bytes:
    return subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "90", url],
        check=True,
        capture_output=True,
        timeout=100,
    ).stdout


def originator_info(info: dict, ecosystem: str) -> tuple[str | None, str | None, str | None]:
    name = email = url = None
    if ecosystem == "pypi":
        for field in ("author", "maintainer"):
            candidate = info.get(field)
            if candidate and not name:
                name = str(candidate).strip()
        for field in ("author_email", "maintainer_email"):
            candidate = info.get(field)
            if candidate and not email:
                parsed_name, parsed_email = email_utils(str(candidate))
                email = parsed_email or None
                if parsed_name and not name:
                    name = parsed_name
        project_urls = info.get("project_urls") or {}
        preferred = ("source", "source code", "repository", "homepage", "home")
        if isinstance(project_urls, dict):
            for wanted in preferred:
                url = next((str(value).strip() for key, value in project_urls.items() if str(key).strip().casefold() == wanted and str(value).startswith(("https://", "http://"))), None)
                if url:
                    break
        url = url or info.get("home_page")
    else:
        author = info.get("author")
        if isinstance(author, dict):
            name = author.get("name")
            email = author.get("email")
            url = author.get("url")
        elif author:
            parsed_name, parsed_email = email_utils(str(author))
            name, email = parsed_name or str(author).strip(), parsed_email or None
        if not name:
            maintainers = info.get("maintainers") or []
            if maintainers and isinstance(maintainers[0], dict):
                name = maintainers[0].get("username") or maintainers[0].get("name")
                email = email or maintainers[0].get("email")
        url = url or info.get("homepage")
        repository = info.get("repository")
        if isinstance(repository, dict):
            url = url or repository.get("url")
        elif isinstance(repository, str):
            url = url or repository
    if isinstance(url, str):
        url = url.strip()
        if url.startswith("git+"):
            url = url[4:]
        if not url.startswith(("https://", "http://")):
            url = None
    if isinstance(email, str):
        _, parsed_email = email_utils(email)
        email = parsed_email or None
    if name:
        name = re.sub(r"\s*<[^<>]*>\s*", "", str(name)).strip() or None
    return name, email, url


def email_utils(value: str) -> tuple[str, str]:
    name, address = email.utils.parseaddr(value)
    if address and "@" in address:
        return name.strip(), address.strip()
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.I)
    return (name.strip(), match.group(0)) if match else (name.strip(), "")


def choose_pypi_artifact(package: dict) -> dict | None:
    candidates = [item for item in package.get("wheels", []) if item.get("url") and item.get("hash")]
    if package.get("sdist", {}).get("url"):
        candidates.append(package["sdist"])
    if not candidates:
        return None

    def rank(item: dict) -> tuple[int, str]:
        url = item["url"].casefold()
        filename = Path(urllib.parse.urlsplit(url).path).name
        if filename.endswith("py3-none-any.whl") or filename.endswith("py2.py3-none-any.whl"):
            return 0, filename
        if filename.endswith(".whl") and "manylinux" in filename and ("x86_64" in filename or "any" in filename):
            return 1, filename
        if filename.endswith(".whl") and "x86_64" in filename:
            return 2, filename
        if filename.endswith(".whl"):
            return 3, filename
        return 4, filename

    return sorted(candidates, key=rank)[0]


def sbom_packages(path: Path) -> list[tuple[str, str, str]]:
    bom = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(bom.get("@graph"), list):
        return [
            (ecosystem, name, version)
            for item in bom["@graph"]
            if item.get("type") == "software_Package"
            for ecosystem, name, version in [purl_parts_v3(item)]
            if ecosystem in ("npm", "pypi")
        ]
    return [
        (ecosystem, item.get("name", ""), item.get("versionInfo", ""))
        for item in bom.get("packages", [])
        for ecosystem in [purl_ecosystem_v2(item)]
        if ecosystem in ("npm", "pypi")
    ]


def purl_parts_v3(item: dict) -> tuple[str | None, str, str]:
    purl = item.get("software_packageUrl", "")
    if not isinstance(purl, str) or not purl.startswith("pkg:"):
        return None, "", ""
    value = purl[4:].split("?", 1)[0].split("#", 1)[0]
    ecosystem, _, path = value.partition("/")
    bits = path.rsplit("@", 1)
    return ecosystem, urllib.parse.unquote(bits[0]), urllib.parse.unquote(bits[1]) if len(bits) == 2 else ""


def purl_ecosystem_v2(item: dict) -> str | None:
    for reference in item.get("externalRefs", []):
        value = reference.get("referenceLocator", "")
        if reference.get("referenceType") == "purl" and value.startswith("pkg:"):
            return value.split(":", 1)[1].split("/", 1)[0]
    return None


if len(sys.argv) < 2:
    raise SystemExit("usage: refresh_registry_snapshot.py SYFT.spdx.json [PYTHON-DISTS.json]")
bom_packages_list = sbom_packages(Path(sys.argv[1]))
python_metadata = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else {}
runtime_python = {(norm(item.get("name")), item.get("version", "")) for item in python_metadata.values()}
python_lock = tomllib.loads((ROOT / "backend/uv.lock").read_text(encoding="utf-8"))
python_lock_by_key = {
    (norm(item.get("name")), item.get("version", "")): item
    for item in python_lock.get("package", [])
}
npm_lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
npm_lock_by_key: dict[tuple[str, str], list[dict]] = {}
for path, metadata in npm_lock.get("packages", {}).items():
    if not path.startswith("node_modules/"):
        continue
    name = metadata.get("name") or path.rsplit("node_modules/", 1)[-1]
    name = name.rsplit("node_modules/", 1)[-1]
    npm_lock_by_key.setdefault((norm(name), metadata.get("version", "")), []).append(metadata)
local_license_metadata: set[tuple[str, str, str]] = set()
for metadata in python_metadata.values():
    license_value = normalize_license(metadata.get("license_expression") or metadata.get("license"))
    if not license_value:
        for classifier in metadata.get("classifiers", []):
            if classifier.startswith("License :: OSI Approved :: "):
                license_value = normalize_license(classifier.rsplit(" :: ", 1)[-1])
                if license_value:
                    break
    if license_value:
        local_license_metadata.add(("pypi", norm(metadata.get("name")), metadata.get("version", "")))
for (name, version), entries in npm_lock_by_key.items():
    if any(normalize_license(item.get("license")) for item in entries):
        local_license_metadata.add(("npm", name, version))

snapshot_path = ROOT / "scripts/sbom/registry-license-snapshot.json"
snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {"schemaVersion": 1, "packages": {}}
jobs = []
for ecosystem, name, version in sorted(set(bom_packages_list)):
    normalized = norm(name)
    if normalized in {"sunsettracker", "sunsettracker-backend", "amos-sunset-tracker-frontend"}:
        continue
    if ecosystem == "npm":
        matching_lock_entries = npm_lock_by_key.get((normalized, version), [])
        if not matching_lock_entries or all(item.get("dev") is True for item in matching_lock_entries):
            continue
    key = f"{ecosystem}:{normalized}@{version}"
    entry = snapshot["packages"].get(key, {})
    if ecosystem == "pypi" and runtime_python and (normalized, version) not in runtime_python:
        continue
    creator_lookup_needed = not entry.get("creatorContactChecked")
    license_missing = (
        not normalize_license(entry.get("license"))
        and not entry.get("licenseChecked")
        and (ecosystem, normalized, version) not in local_license_metadata
    )
    artifact_needed = ecosystem == "pypi" and not entry.get("artifact", {}).get("sha512")
    if creator_lookup_needed or license_missing or artifact_needed:
        jobs.append((key, ecosystem, name, version, entry, creator_lookup_needed, license_missing, artifact_needed))


def lookup(job: tuple) -> tuple[str, dict, str | None]:
    key, ecosystem, name, version, entry, creator_lookup_needed, license_missing, artifact_needed = job
    url = (
        f"https://pypi.org/pypi/{urllib.parse.quote(name, safe='')}/{urllib.parse.quote(version, safe='')}/json"
        if ecosystem == "pypi"
        else f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/{urllib.parse.quote(version, safe='')}"
    )
    try:
        raw = fetch(url)
        data = json.loads(raw)
        info = data.get("info", {}) if ecosystem == "pypi" else data
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        response_hash = hashlib.sha256(raw).hexdigest()
        if not entry.get("reviewed"):
            entry.update({
                "source": "PyPI registry" if ecosystem == "pypi" else "npm registry",
                "sourceUrl": url,
                "retrievedAt": now,
                "responseSha256": response_hash,
            })
        if license_missing:
            raw_license = info.get("license_expression") or info.get("license")
            license_value = normalize_license(raw_license)
            if not license_value and ecosystem == "pypi":
                for classifier in info.get("classifiers", []):
                    if classifier.startswith("License :: OSI Approved :: "):
                        candidate = classifier.rsplit(" :: ", 1)[-1]
                        license_value = normalize_license(candidate)
                        raw_license = raw_license or candidate
                        if license_value:
                            break
            entry["licenseChecked"] = True
            if license_value:
                entry["license"] = str(license_value)
            elif raw_license:
                entry["licenseRaw"] = str(raw_license)[:500]
        if creator_lookup_needed:
            creator, creator_email, creator_url = originator_info(info, ecosystem)
            if creator:
                entry["originator"] = creator
            if creator_email:
                entry["originatorEmail"] = creator_email
            if creator_url:
                entry["originatorUrl"] = creator_url
            entry["creatorContactChecked"] = True
            entry["creatorLookupUrl"] = url
            entry["creatorLookupResponseSha256"] = response_hash
        if artifact_needed and ecosystem == "pypi":
            locked_package = python_lock_by_key.get((norm(name), version))
            artifact = choose_pypi_artifact(locked_package or {})
            if not artifact:
                raise ValueError("uv.lock has no hashed wheel or source archive")
            expected_sha256 = artifact["hash"].removeprefix("sha256:")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
                raise ValueError("locked artifact does not have a SHA-256 pin")
            contents = fetch_artifact(artifact["url"])
            actual_sha256 = hashlib.sha256(contents).hexdigest()
            if actual_sha256.lower() != expected_sha256.lower():
                raise ValueError(f"download SHA-256 {actual_sha256} does not match uv.lock {expected_sha256}")
            entry["artifact"] = {
                "filename": Path(urllib.parse.urlsplit(artifact["url"]).path).name,
                "sha256": actual_sha256,
                "sha512": hashlib.sha512(contents).hexdigest(),
                "url": artifact["url"],
            }
        return key, entry, None
    except Exception as exc:  # report package-specific network/metadata gaps
        return key, entry, str(exc)


failures = []
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for key, entry, error in pool.map(lookup, jobs):
        if error:
            failures.append(key)
            print(f"lookup failed for {key}: {error}", file=sys.stderr)
        else:
            snapshot["packages"][key] = entry
            print(
                f"snapshotted {key}: creator-contact={'yes' if entry.get('originatorEmail') or entry.get('originatorUrl') else 'unknown'}, "
                f"license={'yes' if entry.get('license') else 'unresolved'}, "
                f"artifact-sha512={'yes' if entry.get('artifact', {}).get('sha512') else 'not-needed'}"
            )
snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if failures:
    print(f"registry snapshot refresh failed for {len(failures)} package(s): " + ", ".join(failures), file=sys.stderr)
    raise SystemExit(1)
