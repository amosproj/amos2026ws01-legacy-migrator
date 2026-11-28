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

**Moves.** Inside one component, files that exist only in the earlier stage
are paired with files that exist only in the later one, in two passes:

1. **Same `contentSha256`** → *moved*. Symbols are paired by `kind` + `name`,
   with the start line to tell apart repeated names (the content is identical,
   so the lines match).
2. **Same file name (basename)** among the files still unpaired → *moved_modified*
   (or *moved* if the content turns out identical). Symbols are paired by
   `kind` + `name` only, because edits shift lines.

A hash or basename is only used when it is unique among that component's
remaining removed and added files; otherwise the files stay removed + added.
`name` is the symbol payload's `name` field, because the part of `qualifiedName`
after the path still contains a path-derived graph ID. Paired symbols get the
file's status, unpaired ones stay added / removed. Relationship endpoints are
renamed to their paired keys before comparing, so a relationship that only
moved counts as unchanged.

## Statuses

- **added / removed**: present only in the later / earlier stage.
- **modified**: file hash changed; symbol in both stages and its file changed;
  component has any changed file or symbol.
- **moved**: file or symbol at a new path with identical content.
- **moved_modified**: file paired by its unique basename but with changed
  content, and the symbols paired inside it.
- **unchanged**: everything else. Relationships are only added, removed or
  unchanged.

## Change categories

Every changed file gets one category from its path. The rules live in
`CATEGORY_RULES` in `stage_compare.py`: an ordered tuple of `(category, regex)`
pairs, matched case-insensitively, where the first match wins.

| Category | Rule |
|---|---|
| deployment | `Dockerfile*`, `docker-compose*.yml`, `nginx*.conf`, `*.yaml`/`*.yml` under a folder containing `deploy` or `ocp` |
| db_access | `*.sql`, `persistence.xml`, `orm.xml`, `repository` or `dao` anywhere in the path |
| config | other `*.xml`, `*.properties`, `*.yaml`/`*.yml`, `*.conf` (e.g. `server.xml`, `web.xml`, `pom.xml`) |
| code | everything else (`.java`, `.js`, `.html`, `.sh`, …) |

Moved files are categorized by their new path. Each component has
`changedFilesByCategory` counts, and the Markdown report has a
"Deployment & DB-access changes" section.

## Result: step-05 → step-06

Counts are `+added / -removed / ~modified / >moved / >~moved_modified / =unchanged`.

| Component | Status | Commit | Files | Changed files by category | Symbols | Relationships |
|---|---|---|---|---|---|---|
| catalog-service | added | 474422cf | +10 | deployment 1, db_access 1, config 2, code 6 | +52 | +136 |
| db2 | modified | 4f4f3d27 → 129ed26b | ~1 / =5 | deployment 1 | =74 | =72 |
| frontend-dojo | modified | efe22530 → 3b8b20d6 | ~3 / =81 | deployment 1, code 2 | ~1 / =294 | =879 |
| monolith | modified | fc150cc6 → 73ab85cd | +7 / -11 / ~1 / >20 / >~9 | deployment 1, db_access 2, config 13, code 32 | +30 / -8 / >158 / >~38 / =29 | +114 / -46 / =615 |
| proxy | modified | 2345af93 → c52d9434 | +2 / ~1 / =3 | deployment 3 | — | — |
| external symbols | | | | | +9 / -2 / =65 | — |

No relationship had an endpoint missing from the entities. The monolith moved
`CustomerOrderServices/ejbModule/...` and `CustomerOrderServicesWeb/...` to
`src/main/...`. Without move detection it showed +36 / -40 files and
+226 / -204 symbols. With exact moves only, it showed +16 / -20 files and
+68 / -46 symbols.

Deployment and DB-access changes:

- deployment: Dockerfile added in catalog-service and modified in db2,
  frontend-dojo and monolith; proxy adds `nginx-all-quarkus.conf` and
  `nginx-catalog-native.conf` and modifies `nginx-catalog.conf`.
- db_access: catalog-service adds `import.sql`; monolith removes
  `ejbModule/META-INF/orm.xml` and moves + edits `persistence.xml` to
  `src/main/resources/META-INF/`.

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

- **Moved and edited files are paired only by a unique basename.** A file that
  is renamed and edited, or whose name repeats in the component, stays
  removed + added. In step-06 this affects the monolith's four removed
  `pom.xml` files and the new root `pom.xml`, and also
  `CustomerServicesApp.java` → `CustomerServicesApplication.java`. Pairing by
  symbol overlap would cover these. A unique basename can also, in rare cases,
  pair two files that are not related.
- **Symbol pairing needs unique `kind` + `name` per file**, so overloaded
  methods in a moved and edited file stay added / removed.
- **Symbol "modified" is coarse**: any symbol in a changed file counts as
  modified, even if the symbol itself did not change.
- **Categories come from the path only.** JPA entities (`@Entity` classes),
  `populateDB.sh` and Liberty `server.xml` (data sources, features) are not
  marked db_access or deployment. Using symbol or annotation data from the
  entities would be the next step.
- **Neo4j-based version later**: this compares JSONL run folders. Once both
  stages are persisted in Neo4j, the same rules can run as graph queries over
  the stored snapshots.
