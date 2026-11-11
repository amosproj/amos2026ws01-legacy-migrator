"""Deterministic code entity extractor for the knowledge graph pipeline (Issue #19).

Extracts classes, interfaces, methods, constructors, and database tables from
source files (Java, SQL, TypeScript, Python) and supports predefined/mock parser outputs.
"""

from __future__ import annotations

import ast
import logging
import re
from collections import defaultdict
from typing import Any

from migration_assistant.domain.entities import (
    CodeEntityKind,
    EntityExtractionResult,
    ExtractionSummary,
    SourceSpan,
    SymbolObservation,
    compute_observation_id,
)
from migration_assistant.domain.sources import SourceFile

logger = logging.getLogger(__name__)

# Regular expressions for Java declarations (anchored at line start, no brace bleed)
_JAVA_PACKAGE_PATTERN = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

_JAVA_TYPE_PATTERN = re.compile(
    r"^[ \t]*(?P<modifiers>(?:(?:public|protected|private|static|abstract|final|sealed|non-sealed)\s+)*)"
    r"(?P<kind>class|interface|enum|record)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"(?:<[^>{};]+>)?"
    r"(?:\s+extends\s+[^{;]+)?"
    r"(?:\s+implements\s+[^{;]+)?"
    r"\s*\{",
    re.MULTILINE,
)

_JAVA_CONSTRUCTOR_PATTERN = re.compile(
    r"^[ \t]*(?P<modifiers>(?:(?:public|protected|private)\s+)*)"
    r"(?P<name>[A-Z]\w*)\s*"
    r"\((?P<params>[^){}]*)\)"
    r"(?:\s+throws\s+[^{;]+)?"
    r"\s*\{",
    re.MULTILINE,
)

_JAVA_KEYWORDS = {
    "public",
    "protected",
    "private",
    "static",
    "final",
    "abstract",
    "synchronized",
    "native",
    "default",
    "class",
    "interface",
    "enum",
    "record",
    "return",
    "new",
    "throw",
    "throws",
    "if",
    "for",
    "while",
    "switch",
    "case",
    "catch",
    "finally",
    "try",
}

_JAVA_METHOD_PATTERN = re.compile(
    r"(?:^|[;{}])[ \t]*"
    r"(?P<modifiers>(?:(?:public|protected|private|static|final|synchronized|abstract|native|default)\s+)*)"
    r"(?:<[^>{}]+>\s+)?"
    r"(?P<return_type>[A-Za-z_][A-Za-z0-9_.<>,\[\]]*)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^){}]*)\)"
    r"(?:\s+throws\s+[^{;]+)?"
    r"\s*(?:\{|;)",
    re.MULTILINE,
)

# SQL table pattern
_SQL_CREATE_TABLE_PATTERN = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r'(?:["`]?([\w.]+)["`]?\.)?["`]?([A-Za-z_]\w*)["`]?'
    r"\s*\((?P<body>[\s\S]*?)\);",
    re.IGNORECASE,
)

# TypeScript/JavaScript pattern
_TS_TYPE_PATTERN = re.compile(
    r"^[ \t]*(?P<export>export\s+)?(?P<default>default\s+)?"
    r"(?P<kind>class|interface|type)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"(?:<[^>]+>)?"
    r"(?:\s+extends\s+[^{]+)?"
    r"(?:\s+implements\s+[^{]+)?"
    r"\s*(?:\{|=)",
    re.MULTILINE,
)

_TS_FUNCTION_PATTERN = re.compile(
    r"^[ \t]*(?P<export>export\s+)?(?P<async>async\s+)?function\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*"
    r"(?:<[^>]+>)?"
    r"\((?P<params>[^)]*)\)"
    r"(?:\s*:\s*[^{]+)?"
    r"\s*\{",
    re.MULTILINE,
)


def _clean_docstring(doc: str | None) -> str | None:
    if not doc:
        return None
    cleaned = re.sub(r"^\s*/\*\*?", "", doc, flags=re.MULTILINE)
    cleaned = re.sub(r"\*/\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\*\s?", "", cleaned, flags=re.MULTILINE)
    text = cleaned.strip()
    return text if text else None


def _find_docstring_before(lines: list[str], start_line: int) -> str | None:
    """Find a javadoc/block comment immediately preceding start_line (1-indexed)."""
    idx = start_line - 2  # line above declaration (0-indexed)
    while idx >= 0 and not lines[idx].strip():
        idx -= 1
    if idx < 0:
        return None
    if lines[idx].strip().endswith("*/"):
        doc_lines = []
        while idx >= 0:
            line = lines[idx]
            doc_lines.insert(0, line)
            if "/**" in line or "/*" in line:
                break
            idx -= 1
        raw_doc = "\n".join(doc_lines)
        return _clean_docstring(raw_doc)
    return None


def _clean_signature(sig: str) -> str:
    return " ".join(sig.split())


class CodeEntityExtractor:
    """Extracts code entities into SymbolObservation instances."""

    def extract_from_sources(
        self, sources: list[SourceFile], snapshot_id: str
    ) -> EntityExtractionResult:
        """Extract code entities from a collection of SourceFiles."""
        entities: list[SymbolObservation] = []
        counts_by_kind: dict[str, int] = defaultdict(int)
        counts_by_language: dict[str, int] = defaultdict(int)
        files_scanned = 0

        for file in sources:
            file_entities = self._extract_file(file, snapshot_id)
            if file_entities:
                for entity in file_entities:
                    counts_by_kind[entity.kind] += 1
                    counts_by_language[file.language] += 1
                entities.extend(file_entities)
            files_scanned += 1

        entities.sort(
            key=lambda e: (
                e.path,
                e.source_span.start_line,
                e.kind,
                e.name,
            )
        )

        return EntityExtractionResult(
            snapshot_id=snapshot_id,
            entities=entities,
            summary=ExtractionSummary(
                total_entities=len(entities),
                counts_by_kind=dict(counts_by_kind),
                counts_by_language=dict(counts_by_language),
                files_scanned=files_scanned,
            ),
        )

    def extract_from_mock(
        self, mock_records: list[dict[str, Any]], snapshot_id: str
    ) -> EntityExtractionResult:
        """Accepts mock/predefined parser output for decoupled development (AC4)."""
        entities: list[SymbolObservation] = []
        counts_by_kind: dict[str, int] = defaultdict(int)
        counts_by_language: dict[str, int] = defaultdict(int)
        seen_files: set[str] = set()

        for record in mock_records:
            repo_id = str(record.get("repoId", "mock-repo"))
            commit_sha = str(record.get("commitSha", "0" * 40))
            path = str(record.get("path", "src/Sample.java"))
            kind = str(record.get("kind", "class")).lower()
            name = str(record.get("name", "Sample"))
            qualified_name = str(record.get("qualifiedName", name))
            parent_qualified_name = record.get("parentQualifiedName")
            signature = record.get("signature")
            docstring = record.get("docstring")
            modifiers = list(record.get("modifiers", []))
            metadata = dict(record.get("metadata", {}))

            start_line = int(record.get("startLine", 1))
            end_line = int(record.get("endLine", start_line))
            language = str(record.get("language", "unknown"))

            observation_id = compute_observation_id(
                snapshot_id=snapshot_id,
                repo_id=repo_id,
                path=path,
                kind=kind,
                qualified_name=qualified_name,
            )

            source_span = SourceSpan(
                repo_id=repo_id,
                commit_sha=commit_sha,
                path=path,
                start_line=start_line,
                end_line=end_line,
                start_column=record.get("startColumn"),
                end_column=record.get("endColumn"),
            )

            observation = SymbolObservation(
                observation_id=observation_id,
                snapshot_id=snapshot_id,
                repo_id=repo_id,
                path=path,
                kind=kind,  # type: ignore[arg-type]
                name=name,
                qualified_name=qualified_name,
                source_span=source_span,
                parent_qualified_name=parent_qualified_name,
                signature=signature,
                docstring=docstring,
                modifiers=modifiers,
                metadata=metadata,
            )

            entities.append(observation)
            counts_by_kind[kind] += 1
            counts_by_language[language] += 1
            seen_files.add(path)

        entities.sort(
            key=lambda e: (
                e.path,
                e.source_span.start_line,
                e.kind,
                e.name,
            )
        )

        return EntityExtractionResult(
            snapshot_id=snapshot_id,
            entities=entities,
            summary=ExtractionSummary(
                total_entities=len(entities),
                counts_by_kind=dict(counts_by_kind),
                counts_by_language=dict(counts_by_language),
                files_scanned=len(seen_files),
            ),
        )

    def _extract_file(
        self, file: SourceFile, snapshot_id: str
    ) -> list[SymbolObservation]:
        """Route source file to the corresponding language extractor."""
        lang = file.language.lower()
        try:
            if lang == "java":
                return self._extract_java(file, snapshot_id)
            if lang == "sql":
                return self._extract_sql(file, snapshot_id)
            if lang in ("javascript", "typescript", "js", "ts", "tsx"):
                return self._extract_typescript(file, snapshot_id)
            if lang == "python":
                return self._extract_python(file, snapshot_id)
        except Exception as error:
            logger.warning(
                "Failed to extract entities from %s (%s): %s",
                file.path,
                file.language,
                error,
            )
        return []

    def _extract_java(
        self, file: SourceFile, snapshot_id: str
    ) -> list[SymbolObservation]:
        """Extract Java classes, interfaces, enums, records, and methods."""
        content = file.content
        lines = content.splitlines()
        entities: list[SymbolObservation] = []

        # Find package declaration
        package_match = _JAVA_PACKAGE_PATTERN.search(content)
        package_prefix = f"{package_match.group(1)}." if package_match else ""

        def offset_to_line(offset: int) -> int:
            return content[:offset].count("\n") + 1

        # Track types for enclosing context
        enclosing_type_name: str | None = None
        enclosing_type_qualified: str | None = None

        for match in _JAVA_TYPE_PATTERN.finditer(content):
            kind = match.group("kind")  # class | interface | enum | record
            name = match.group("name")
            raw_mods = match.group("modifiers")
            modifiers = [m for m in raw_mods.split() if m] if raw_mods else []
            decl_start = match.start("modifiers") if raw_mods and raw_mods.strip() else match.start("kind")
            start_line = offset_to_line(decl_start)
            end_line = self._find_closing_brace_line(lines, start_line)
            doc = _find_docstring_before(lines, start_line)

            qualified_name = f"{package_prefix}{name}"
            enclosing_type_name = name
            enclosing_type_qualified = qualified_name

            observation_id = compute_observation_id(
                snapshot_id=snapshot_id,
                repo_id=file.repo_id,
                path=file.path,
                kind=kind,
                qualified_name=qualified_name,
            )

            entities.append(
                SymbolObservation(
                    observation_id=observation_id,
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind=kind,  # type: ignore[arg-type]
                    name=name,
                    qualified_name=qualified_name,
                    source_span=SourceSpan(
                        repo_id=file.repo_id,
                        commit_sha=file.commit_sha,
                        path=file.path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    parent_qualified_name=None,
                    signature=_clean_signature(match.group(0).rstrip("{").strip()),
                    docstring=doc,
                    modifiers=modifiers,
                    metadata={"package": package_match.group(1) if package_match else ""},
                )
            )

        # Extract constructors
        if enclosing_type_name and enclosing_type_qualified:
            for match in _JAVA_CONSTRUCTOR_PATTERN.finditer(content):
                name = match.group("name")
                if name != enclosing_type_name:
                    continue
                params = match.group("params").strip()
                raw_mods = match.group("modifiers")
                modifiers = [m for m in raw_mods.split() if m] if raw_mods else []
                decl_start = match.start("modifiers") if raw_mods and raw_mods.strip() else match.start("name")
                start_line = offset_to_line(decl_start)
                end_line = self._find_closing_brace_line(lines, start_line)
                doc = _find_docstring_before(lines, start_line)

                param_types = self._normalize_params(params)
                qualified_name = (
                    f"{enclosing_type_qualified}.<init>({param_types})"
                )

                observation_id = compute_observation_id(
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind="constructor",
                    qualified_name=qualified_name,
                )

                entities.append(
                    SymbolObservation(
                        observation_id=observation_id,
                        snapshot_id=snapshot_id,
                        repo_id=file.repo_id,
                        path=file.path,
                        kind="constructor",
                        name=name,
                        qualified_name=qualified_name,
                        source_span=SourceSpan(
                            repo_id=file.repo_id,
                            commit_sha=file.commit_sha,
                            path=file.path,
                            start_line=start_line,
                            end_line=end_line,
                        ),
                        parent_qualified_name=enclosing_type_qualified,
                        signature=_clean_signature(f"{name}({params})"),
                        docstring=doc,
                        modifiers=modifiers,
                        metadata={"parameters": params},
                    )
                )

        # Extract methods
        for match in _JAVA_METHOD_PATTERN.finditer(content):
            name = match.group("name")
            return_type = match.group("return_type").strip()
            if name == enclosing_type_name:
                continue
            if return_type in _JAVA_KEYWORDS:
                continue

            params = match.group("params").strip()
            raw_mods = match.group("modifiers")
            modifiers = [m for m in raw_mods.split() if m] if raw_mods else []
            decl_start = match.start("modifiers") if raw_mods and raw_mods.strip() else match.start("return_type")
            start_line = offset_to_line(decl_start)
            end_line = self._find_closing_brace_line(lines, start_line)
            doc = _find_docstring_before(lines, start_line)

            param_types = self._normalize_params(params)
            parent_name = enclosing_type_qualified or f"{package_prefix}Unknown"
            qualified_name = f"{parent_name}.{name}({param_types})"

            observation_id = compute_observation_id(
                snapshot_id=snapshot_id,
                repo_id=file.repo_id,
                path=file.path,
                kind="method",
                qualified_name=qualified_name,
            )

            entities.append(
                SymbolObservation(
                    observation_id=observation_id,
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind="method",
                    name=name,
                    qualified_name=qualified_name,
                    source_span=SourceSpan(
                        repo_id=file.repo_id,
                        commit_sha=file.commit_sha,
                        path=file.path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    parent_qualified_name=enclosing_type_qualified,
                    signature=_clean_signature(f"{return_type} {name}({params})"),
                    docstring=doc,
                    modifiers=modifiers,
                    metadata={"returnType": return_type, "parameters": params},
                )
            )

        return entities

    def _extract_sql(
        self, file: SourceFile, snapshot_id: str
    ) -> list[SymbolObservation]:
        """Extract database tables from DDL files."""
        content = file.content
        entities: list[SymbolObservation] = []

        def offset_to_line(offset: int) -> int:
            return content[:offset].count("\n") + 1

        for match in _SQL_CREATE_TABLE_PATTERN.finditer(content):
            schema = match.group(1) or "public"
            table_name = match.group(2)
            body = match.group("body")
            start_line = offset_to_line(match.start())
            end_line = offset_to_line(match.end())

            columns = self._parse_sql_columns(body)
            qualified_name = f"{schema}.{table_name}"

            observation_id = compute_observation_id(
                snapshot_id=snapshot_id,
                repo_id=file.repo_id,
                path=file.path,
                kind="table",
                qualified_name=qualified_name,
            )

            entities.append(
                SymbolObservation(
                    observation_id=observation_id,
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind="table",
                    name=table_name,
                    qualified_name=qualified_name,
                    source_span=SourceSpan(
                        repo_id=file.repo_id,
                        commit_sha=file.commit_sha,
                        path=file.path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    parent_qualified_name=None,
                    signature=_clean_signature(f"CREATE TABLE {qualified_name}"),
                    docstring=None,
                    modifiers=[],
                    metadata={"schema": schema, "columns": columns},
                )
            )

        return entities

    def _extract_typescript(
        self, file: SourceFile, snapshot_id: str
    ) -> list[SymbolObservation]:
        """Extract classes, interfaces, and functions from TypeScript/JavaScript."""
        content = file.content
        lines = content.splitlines()
        entities: list[SymbolObservation] = []

        def offset_to_line(offset: int) -> int:
            return content[:offset].count("\n") + 1

        for match in _TS_TYPE_PATTERN.finditer(content):
            raw_kind = match.group("kind")
            kind: CodeEntityKind = "class" if raw_kind == "class" else "interface"
            name = match.group("name")
            start_line = offset_to_line(match.start())
            end_line = self._find_closing_brace_line(lines, start_line)
            doc = _find_docstring_before(lines, start_line)

            modifiers = []
            if match.group("export"):
                modifiers.append("export")
            if match.group("default"):
                modifiers.append("default")

            module_prefix = file.path.rsplit(".", 1)[0].replace("/", ".")
            qualified_name = f"{module_prefix}.{name}"

            observation_id = compute_observation_id(
                snapshot_id=snapshot_id,
                repo_id=file.repo_id,
                path=file.path,
                kind=kind,
                qualified_name=qualified_name,
            )

            entities.append(
                SymbolObservation(
                    observation_id=observation_id,
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind=kind,
                    name=name,
                    qualified_name=qualified_name,
                    source_span=SourceSpan(
                        repo_id=file.repo_id,
                        commit_sha=file.commit_sha,
                        path=file.path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    parent_qualified_name=None,
                    signature=_clean_signature(match.group(0).rstrip("{=").strip()),
                    docstring=doc,
                    modifiers=modifiers,
                    metadata={"module": module_prefix},
                )
            )

        for match in _TS_FUNCTION_PATTERN.finditer(content):
            name = match.group("name")
            params = match.group("params").strip()
            start_line = offset_to_line(match.start())
            end_line = self._find_closing_brace_line(lines, start_line)
            doc = _find_docstring_before(lines, start_line)

            modifiers = []
            if match.group("export"):
                modifiers.append("export")
            if match.group("async"):
                modifiers.append("async")

            module_prefix = file.path.rsplit(".", 1)[0].replace("/", ".")
            qualified_name = f"{module_prefix}.{name}()"

            observation_id = compute_observation_id(
                snapshot_id=snapshot_id,
                repo_id=file.repo_id,
                path=file.path,
                kind="function",
                qualified_name=qualified_name,
            )

            entities.append(
                SymbolObservation(
                    observation_id=observation_id,
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind="function",
                    name=name,
                    qualified_name=qualified_name,
                    source_span=SourceSpan(
                        repo_id=file.repo_id,
                        commit_sha=file.commit_sha,
                        path=file.path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    parent_qualified_name=None,
                    signature=_clean_signature(f"function {name}({params})"),
                    docstring=doc,
                    modifiers=modifiers,
                    metadata={"module": module_prefix, "parameters": params},
                )
            )

        return entities

    def _extract_python(
        self, file: SourceFile, snapshot_id: str
    ) -> list[SymbolObservation]:
        """Extract Python classes, methods, and functions using Python's native AST."""
        try:
            tree = ast.parse(file.content, filename=file.path)
        except SyntaxError as error:
            logger.warning("Python syntax error in %s: %s", file.path, error)
            return []

        entities: list[SymbolObservation] = []
        module_prefix = file.path.rsplit(".", 1)[0].replace("/", ".")

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                qualified_name = f"{module_prefix}.{node.name}"
                observation_id = compute_observation_id(
                    snapshot_id=snapshot_id,
                    repo_id=file.repo_id,
                    path=file.path,
                    kind="class",
                    qualified_name=qualified_name,
                )
                entities.append(
                    SymbolObservation(
                        observation_id=observation_id,
                        snapshot_id=snapshot_id,
                        repo_id=file.repo_id,
                        path=file.path,
                        kind="class",
                        name=node.name,
                        qualified_name=qualified_name,
                        source_span=SourceSpan(
                            repo_id=file.repo_id,
                            commit_sha=file.commit_sha,
                            path=file.path,
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                        ),
                        signature=f"class {node.name}",
                        docstring=doc,
                        modifiers=[],
                        metadata={"module": module_prefix},
                    )
                )

                # Class methods
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_doc = ast.get_docstring(sub)
                        method_kind = "constructor" if sub.name == "__init__" else "method"
                        method_qual = f"{qualified_name}.{sub.name}"
                        obs_id = compute_observation_id(
                            snapshot_id=snapshot_id,
                            repo_id=file.repo_id,
                            path=file.path,
                            kind=method_kind,
                            qualified_name=method_qual,
                        )
                        entities.append(
                            SymbolObservation(
                                observation_id=obs_id,
                                snapshot_id=snapshot_id,
                                repo_id=file.repo_id,
                                path=file.path,
                                kind=method_kind,  # type: ignore[arg-type]
                                name=sub.name,
                                qualified_name=method_qual,
                                source_span=SourceSpan(
                                    repo_id=file.repo_id,
                                    commit_sha=file.commit_sha,
                                    path=file.path,
                                    start_line=sub.lineno,
                                    end_line=getattr(sub, "end_lineno", sub.lineno),
                                ),
                                parent_qualified_name=qualified_name,
                                signature=f"def {sub.name}(...)",
                                docstring=method_doc,
                                modifiers=["async"] if isinstance(sub, ast.AsyncFunctionDef) else [],
                                metadata={"module": module_prefix},
                            )
                        )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if getattr(node, "parent", None) is None:
                    doc = ast.get_docstring(node)
                    qualified_name = f"{module_prefix}.{node.name}()"
                    observation_id = compute_observation_id(
                        snapshot_id=snapshot_id,
                        repo_id=file.repo_id,
                        path=file.path,
                        kind="function",
                        qualified_name=qualified_name,
                    )
                    entities.append(
                        SymbolObservation(
                            observation_id=observation_id,
                            snapshot_id=snapshot_id,
                            repo_id=file.repo_id,
                            path=file.path,
                            kind="function",
                            name=node.name,
                            qualified_name=qualified_name,
                            source_span=SourceSpan(
                                repo_id=file.repo_id,
                                commit_sha=file.commit_sha,
                                path=file.path,
                                start_line=node.lineno,
                                end_line=getattr(node, "end_lineno", node.lineno),
                            ),
                            signature=f"def {node.name}(...)",
                            docstring=doc,
                            modifiers=["async"] if isinstance(node, ast.AsyncFunctionDef) else [],
                            metadata={"module": module_prefix},
                        )
                    )

        return entities

    def _normalize_params(self, params_str: str) -> str:
        """Extract only simple parameter types for a concise method signature."""
        if not params_str.strip():
            return ""
        types = []
        for param in params_str.split(","):
            parts = param.strip().split()
            if len(parts) >= 2:
                types.append(parts[-2])
            elif parts:
                types.append(parts[0])
        return ",".join(types)

    def _parse_sql_columns(self, body: str) -> list[dict[str, str]]:
        """Extract column definitions from a CREATE TABLE body."""
        columns = []
        for line in body.splitlines():
            cleaned = line.strip().rstrip(",")
            if not cleaned or cleaned.upper().startswith(
                ("CONSTRAINT", "PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "INDEX")
            ):
                continue
            parts = cleaned.split()
            if len(parts) >= 2:
                col_name = parts[0].strip('"`')
                col_type = parts[1].upper()
                columns.append({"name": col_name, "type": col_type})
        return columns

    def _find_closing_brace_line(self, lines: list[str], start_line: int) -> int:
        """Count braces starting from start_line (1-indexed) to locate closing brace."""
        depth = 0
        started = False
        for idx in range(start_line - 1, len(lines)):
            line = lines[idx]
            for char in line:
                if char == "{":
                    depth += 1
                    started = True
                elif char == "}":
                    depth -= 1
                    if started and depth == 0:
                        return idx + 1
        return start_line
