# Stage comparison (research, #131)

Compares two persisted ingestion runs of the reference project (for example
`step-05` against `step-06`) and reports which components, files, symbols and
relationships changed, with evidence for both sides. Code:
[`backend/app/stage_compare.py`](../backend/app/stage_compare.py), tests:
[`backend/tests/test_stage_compare.py`](../backend/tests/test_stage_compare.py).

## Run

From `backend/`:

```bash
uv run python -m app.stage_compare <earlier_run_dir> <later_run_dir> [--md out.md]
```

A run folder must contain `snapshot-identity.json`, `sources.jsonl`,
`entities.jsonl` and `relationships.jsonl`. The Markdown report goes to stdout
(and to `--md`, whose folder must exist). The exit code is `0` for a ready
comparison and `2` for insufficient data. In Python, `compare_stages()` returns a
typed `StageComparison` and `render_markdown()` renders it.

## Matching rules

Everything is discovered from the run data; nothing is specific to a stage.

| Item | Key | Notes |
|---|---|---|
| Component | `repoId` from `snapshot-identity.json` `sourceMembers` | commit SHAs of both sides are reported |
| File | `(repoId, path)` from `sources.jsonl` | modified when `contentSha256` differs |
| Symbol | `(repoId, qualifiedName)` from `entities.jsonl` | all three record types, see decisions |
| Relationship | `(relationshipType, sourceKey, targetKey)` | observation IDs mapped to symbol keys per stage |

**Moves.** Inside one component, a removed and an added file with the same
`contentSha256` are one *moved* file (old path → new path), provided the hash is
unique on both sides. Symbols of a moved file are paired by `kind` and `name`,
using the start line to tell apart repeated names (the content is identical, so
the lines match), and are reported as *moved*. Relationships whose endpoints
only moved count as unchanged.

## Statuses

- **added / removed**: present only in the later / earlier stage.
- **modified**: file hash changed; symbol in both stages and its file changed;
  component has any changed file or symbol.
- **moved**: file or symbol at a new path with identical content.
- **unchanged**: everything else. Relationships are only added, removed or
  unchanged.

## Result: step-05 → step-06

Counts are `+added / -removed / ~modified / >moved / =unchanged`.

| Component | Status | Commit | Files | Symbols | Relationships |
|---|---|---|---|---|---|
| catalog-service | added | 474422cf | +10 | +52 | +136 |
| db2 | modified | 4f4f3d27 → 129ed26b | ~1 / =5 | =74 | =72 |
| frontend-dojo | modified | efe22530 → 3b8b20d6 | ~3 / =81 | ~1 / =294 | =879 |
| monolith | modified | fc150cc6 → 73ab85cd | +16 / -20 / ~1 / >20 | +68 / -46 / >158 / =29 | +391 / -322 / =339 |
| proxy | modified | 2345af93 → c52d9434 | +2 / ~1 / =3 | — | — |
| external symbols | | | | +9 / -2 / =65 | — |

No relationship had an endpoint missing from the entities. Without move
detection the monolith showed +36 / -40 files and +226 / -204 symbols, because
it moved `CustomerOrderServices/ejbModule/...` to `src/main/java/...`.

## Decisions

- **External symbols** have no `repoId`. Their key is `(None, qualifiedName)`
  and they are counted outside any component.
- **Duplicate unresolved symbols**: several `UnresolvedSymbolObservation`s share
  a `(repoId, qualifiedName)` (for example `Override`) and have no other stable
  field. They are merged into one symbol that keeps all observation IDs. They
  have no file, so they are never modified.
- **Relationship counts**: the same key can occur several times in one stage
  (73 extra copies in each of these runs), so relationships are compared as counts:
  going from 1 to 2 copies is one addition. A relationship belongs to the
  component of its source symbol, or of its target if the source is external.
- **Insufficient data**: if a run folder or file is missing, a line is
  malformed, a component has no files, a commit SHA in `sources.jsonl`
  contradicts `snapshot-identity.json`, or a symbol's file is not in
  `sources.jsonl`, the result is `insufficient_data` with every problem listed.
  No partial comparison is returned.

## Limitations and next steps

- **Moved and edited files** stay removed + added; so do files whose hash is
  shared by several moved candidates. In step-06 this affects for example
  `CustomerOrderServicesImpl.java`, `persistence.xml` and `server.xml` in the
  monolith. A similarity-based pairing (same file name, symbol overlap) would
  cover them.
- **Symbol "modified" is coarse**: any symbol in a changed file counts as
  modified, even if the symbol itself did not change.
- **No change categories yet**: deployment changes (Dockerfiles, OpenShift
  YAML, `server.xml`) and database-access changes (`persistence.xml`, SQL, JPA
  entities) are not separated from other code changes.
- **Neo4j-based version later**: this compares JSONL run folders. Once both
  stages are persisted in Neo4j, the same rules can run as graph queries over
  the stored snapshots.
