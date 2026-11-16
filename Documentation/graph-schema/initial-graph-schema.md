# Graph contract

The ingestion record contract in `backend/shared_contracts/records.py` is the
canonical persisted representation. The pipeline emits `CodeGraph` roots,
symbol observations, and relationship records directly; persistence should
store those records without translating them into a second node taxonomy.

Each `CodeGraph` record is scoped to one repository and pinned commit. Its
observation IDs connect the component subgraph to relationship records and to
other component subgraphs in the same snapshot. Source-backed observations use
the shared `SourceSpan` fields: `repoId`, `path`, `commitSha`, `startLine`, and
`endLine`.

Known relationships use `RelationshipType` values. A relationship the
extractor cannot normalize remains a string in `relationshipType`; the record
also retains `originalRelationshipType`, `sourceEdgeId`, the original Graphify
edge, and source evidence when available. Edges without resolvable endpoints
are written to `relationship-issues.jsonl` with their original edge payload.

The ID formulas from the earlier #21 implementation remain available in
`backend/shared_contracts/graph_identity.py`. File IDs include the snapshot,
repository/component key, and normalized path. Entity IDs additionally include
the entity kind and qualified name, with a signature when one is known. These
helpers do not define a separate graph schema.
