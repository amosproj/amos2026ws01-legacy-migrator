"""Generate the checked-in JSON Schema from the shared Pydantic contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, TypeAdapter

from shared_contracts.graph_queries import (
    ComponentMigrationStatus,
    CoupledComponent,
    CouplingResult,
    DecommissionCandidate,
    DecommissionResult,
    GraphQueryRequest,
    MigrationStatusResult,
)
from shared_contracts.node_types import SOURCE_LOCATED_NODE_TYPES
from shared_contracts.records import (
    CompareRequest,
    ComparisonResult,
    ExternalSymbolObservationRecord,
    GraphEdge,
    GraphNode,
    MigrationManifest,
    RelationshipRecord,
    SnapshotIdentity,
    SymbolObservationRecord,
    SymbolQueryResult,
    VectorDocumentRecord,
)

ProjectContractPayload = (
    SnapshotIdentity
    | MigrationManifest
    | SymbolObservationRecord
    | ExternalSymbolObservationRecord
    | RelationshipRecord
    | GraphNode
    | GraphEdge
    | SymbolQueryResult
    | ComponentMigrationStatus
    | MigrationStatusResult
    | CoupledComponent
    | CouplingResult
    | DecommissionCandidate
    | DecommissionResult
    | GraphQueryRequest
    | VectorDocumentRecord
    | CompareRequest
    | ComparisonResult
)

ProjectContract = Annotated[
    ProjectContractPayload,
    Field(title="Migration Assistant project contract"),
]


def project_contract_schema() -> dict:
    schema = TypeAdapter(ProjectContract).json_schema(by_alias=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["description"] = (
        "Shared contract for migration inputs, snapshot identities, ingestion facts, typed graph "
        "nodes and edges, query and comparison results, and source-grounded vector documents."
    )
    schema["$defs"]["GraphNode"]["allOf"] = [
        {
            "if": {
                "properties": {
                    "label": {
                        "enum": sorted(node_type.value for node_type in SOURCE_LOCATED_NODE_TYPES)
                    }
                },
                "required": ["label"],
            },
            "then": {
                "properties": {
                    "properties": {
                        "required": ["sourceSpan"],
                        "properties": {"sourceSpan": {"$ref": "#/$defs/SourceSpan"}},
                    }
                }
            },
        }
    ]
    return schema


def validate_project_contract(value: object) -> object:
    """Validate one JSON value using the same types that generate the schema."""
    return TypeAdapter(ProjectContract).validate_python(value)


def write_project_contract_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(project_contract_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "schemas" / "project-contract.schema.json",
    )
    args = parser.parse_args()
    write_project_contract_schema(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
