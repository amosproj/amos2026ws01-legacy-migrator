#!/usr/bin/env python3
"""Report BSI-relevant SPDX 3.0.1 component completeness before the official check."""
import json
import re
import sys
from pathlib import Path


def main(path: str) -> int:
    bom = json.loads(Path(path).read_text(encoding="utf-8"))
    graph = bom.get("@graph")
    if not isinstance(graph, list):
        print("ERROR: expected SPDX 3 JSON-LD")
        return 1
    elements = {item.get("spdxId"): item for item in graph if item.get("spdxId")}
    packages = [item for item in graph if item.get("type") == "software_Package"]
    relations = [item for item in graph if item.get("type") == "Relationship"]
    files = {item.get("spdxId"): item for item in graph if item.get("type") == "software_File"}
    creators = {item.get("spdxId"): item for item in graph if item.get("type") in ("Person", "Organization")}
    errors = []
    creation = next((item for item in graph if item.get("type") == "CreationInfo"), {})
    if creation.get("specVersion") != "3.0.1":
        errors.append("SPDX specification version is not 3.0.1")
    if not creation.get("created"):
        errors.append("missing SPDX creation timestamp")
    if not any(
        creators.get(creator, {}).get("name") == "AMOS Project"
        and any(identifier.get("externalIdentifierType") == "urlScheme" for identifier in creators.get(creator, {}).get("externalIdentifier", []))
        for creator in creation.get("createdBy", [])
    ):
        errors.append("missing AMOS Project creator URL")
    for package in packages:
        name = package.get("name", "?")
        version = package.get("software_packageVersion", "")
        package_id = package.get("spdxId")
        if not name or not version:
            errors.append(f"{name}: missing component name or version")
        if not str(package.get("software_packageUrl", "")).startswith("pkg:"):
            errors.append(f"{name} {version}: missing PURL")
        if not any(
            creators.get(agent, {}).get("externalIdentifier")
            for agent in package.get("originatedBy", [])
        ):
            errors.append(f"{name} {version}: missing creator email or URL")
        artifact_ids = [
            target
            for relation in relations
            if relation.get("from") == package_id
            and str(relation.get("relationshipType", "")).rsplit("/", 1)[-1] == "hasDistributionArtifact"
            for target in relation.get("to", [])
        ]
        valid_artifact = False
        for artifact_id in artifact_ids:
            artifact = files.get(artifact_id, {})
            if artifact.get("name") and any(
                item.get("type") == "Hash"
                and item.get("algorithm", "").lower() == "sha512"
                and re.fullmatch(r"[0-9a-fA-F]{128}", item.get("hashValue", ""))
                for item in artifact.get("verifiedUsing", [])
            ):
                valid_artifact = True
        if not valid_artifact:
            errors.append(f"{name} {version}: missing distribution filename or SHA-512 hash")
        if not any(
            relation.get("from") == package_id
            and str(relation.get("relationshipType", "")).rsplit("/", 1)[-1] == "hasConcludedLicense"
            and any(
                elements.get(target, {}).get("type") == "simplelicensing_LicenseExpression"
                and elements[target].get("simplelicensing_licenseExpression") not in (None, "", "NOASSERTION")
                for target in relation.get("to", [])
            )
            for relation in relations
        ):
            errors.append(f"{name} {version}: missing concluded SPDX license expression")
    if not any(
        str(relation.get("relationshipType", "")).rsplit("/", 1)[-1] in ("dependsOn", "contains")
        for relation in relations
    ):
        errors.append("missing dependency relationships")
    for error in errors:
        print("ERROR:", error)
    print(f"Completeness: {len(packages)} packages, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_completeness.py sbom.spdx.json")
    raise SystemExit(main(sys.argv[1]))
