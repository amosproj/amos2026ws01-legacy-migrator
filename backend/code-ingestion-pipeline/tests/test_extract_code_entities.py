"""Comprehensive unit tests for Code Entity Extraction (Issue #19).

Verifies all Acceptance Criteria:
- AC1: Code entities required for the first vertical slice are extracted (classes, methods, tables).
- AC2: Each extracted entity contains a unique identifier (observationId).
- AC3: Relevant metadata about the entity is retained (qualifiedName, kind, sourceSpan, etc.).
- AC4: Extraction works with predefined or mock parser output.
- AC5: Extracted entities can be provided to the graph component (canonical JSONL).
"""

import json
from migration_assistant.adapters.extraction.code_entity_extractor import CodeEntityExtractor
from migration_assistant.domain.entities import (
    SymbolObservation,
    compute_observation_id,
)
from migration_assistant.domain.sources import SourceFile

DUMMY_SHA = "a" * 40
SNAPSHOT_ID = "snap-test-123"


def _make_source_file(path: str, content: str, language: str) -> SourceFile:
    return SourceFile(
        repo_id="legacy-example-monolith",
        origin="legacy",
        stage="step-00",
        commit_sha=DUMMY_SHA,
        public_url="https://github.com/example/org",
        path=path,
        language=language,
        size_bytes=len(content.encode("utf-8")),
        content_sha256="dummyhash",
        encoding="utf-8",
        content=content,
    )


# -------------------------------------------------------------------------
# AC1 & AC3: Java Entity Extraction (Classes, Methods, Constructors)
# -------------------------------------------------------------------------


def test_extract_java_class_and_methods():
    java_code = """package com.example.account;

/**
 * Service managing user bank accounts.
 */
public class AccountService {
    private int counter;

    public AccountService() {
        this.counter = 0;
    }

    /**
     * Looks up an account by ID.
     */
    public Account findAccount(String accountId) {
        return null;
    }

    private void reset() {
        this.counter = 0;
    }
}
"""
    file = _make_source_file("src/main/java/com/example/account/AccountService.java", java_code, "java")
    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources([file], SNAPSHOT_ID)

    assert result.summary.total_entities == 4  # Class, constructor, 2 methods
    assert result.summary.counts_by_kind["class"] == 1
    assert result.summary.counts_by_kind["constructor"] == 1
    assert result.summary.counts_by_kind["method"] == 2

    # Verify Class
    cls_entity = next(e for e in result.entities if e.kind == "class")
    assert cls_entity.name == "AccountService"
    assert cls_entity.qualified_name == "com.example.account.AccountService"
    assert "public" in cls_entity.modifiers
    assert cls_entity.docstring == "Service managing user bank accounts."
    assert cls_entity.source_span.start_line == 6
    assert cls_entity.source_span.end_line > 6

    # Verify Method findAccount
    find_method = next(e for e in result.entities if e.name == "findAccount")
    assert find_method.kind == "method"
    assert find_method.qualified_name == "com.example.account.AccountService.findAccount(String)"
    assert find_method.parent_qualified_name == "com.example.account.AccountService"
    assert find_method.docstring == "Looks up an account by ID."
    assert "public" in find_method.modifiers
    assert find_method.metadata["returnType"] == "Account"


def test_extract_java_interface():
    java_code = """package com.example.account;

public interface AccountRepository {
    Account getById(Long id);
}
"""
    file = _make_source_file("src/main/java/com/example/account/AccountRepository.java", java_code, "java")
    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources([file], SNAPSHOT_ID)

    assert len(result.entities) == 2
    interface_entity = next(e for e in result.entities if e.kind == "interface")
    assert interface_entity.name == "AccountRepository"
    assert interface_entity.qualified_name == "com.example.account.AccountRepository"


# -------------------------------------------------------------------------
# AC1 & AC3: SQL Entity Extraction (Tables & Columns)
# -------------------------------------------------------------------------


def test_extract_sql_tables():
    sql_code = """
-- Accounts schema
CREATE TABLE IF NOT EXISTS public.accounts (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    balance NUMERIC(15,2),
    created_at TIMESTAMP
);

CREATE TABLE audit_logs (
    log_id SERIAL,
    message TEXT
);
"""
    file = _make_source_file("db/migration/V1__accounts.sql", sql_code, "sql")
    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources([file], SNAPSHOT_ID)

    assert result.summary.total_entities == 2
    assert result.summary.counts_by_kind["table"] == 2

    # Verify public.accounts
    accounts_table = next(e for e in result.entities if e.name == "accounts")
    assert accounts_table.kind == "table"
    assert accounts_table.qualified_name == "public.accounts"
    assert accounts_table.source_span.start_line == 3
    columns = accounts_table.metadata["columns"]
    assert len(columns) == 4
    assert columns[0] == {"name": "id", "type": "BIGINT"}
    assert columns[1] == {"name": "name", "type": "VARCHAR(255)"}

    # Verify audit_logs
    audit_table = next(e for e in result.entities if e.name == "audit_logs")
    assert audit_table.qualified_name == "public.audit_logs"
    assert audit_table.name == "audit_logs"


# -------------------------------------------------------------------------
# TypeScript Entity Extraction
# -------------------------------------------------------------------------


def test_extract_typescript_entities():
    ts_code = """
/**
 * Modern target service client
 */
export class TargetAccountClient {
    private baseUrl: string;

    constructor(url: string) {
        this.baseUrl = url;
    }
}

export async function fetchAccount(id: string): Promise<Account> {
    return null as any;
}
"""
    file = _make_source_file("src/clients/TargetAccountClient.ts", ts_code, "typescript")
    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources([file], SNAPSHOT_ID)

    assert len(result.entities) == 2
    cls = next(e for e in result.entities if e.kind == "class")
    assert cls.name == "TargetAccountClient"
    assert "export" in cls.modifiers
    assert cls.docstring == "Modern target service client"

    fn = next(e for e in result.entities if e.kind == "function")
    assert fn.name == "fetchAccount"
    assert "export" in fn.modifiers
    assert "async" in fn.modifiers


# -------------------------------------------------------------------------
# AC2: Deterministic Unique Identifier (observationId)
# -------------------------------------------------------------------------


def test_observation_id_is_deterministic():
    id1 = compute_observation_id(
        snapshot_id=SNAPSHOT_ID,
        repo_id="monolith",
        path="src/Account.java",
        kind="class",
        qualified_name="com.example.Account",
    )
    id2 = compute_observation_id(
        snapshot_id=SNAPSHOT_ID,
        repo_id="monolith",
        path="src/Account.java",
        kind="class",
        qualified_name="com.example.Account",
    )
    assert id1 == id2
    assert len(id1) == 64  # SHA-256 hex digest length

    # Changing any attribute yields distinct identifier
    id3 = compute_observation_id(
        snapshot_id="different-snapshot",
        repo_id="monolith",
        path="src/Account.java",
        kind="class",
        qualified_name="com.example.Account",
    )
    assert id1 != id3


# -------------------------------------------------------------------------
# AC4: Predefined / Mock Parser Output Support
# -------------------------------------------------------------------------


def test_extract_from_mock_records():
    mock_records = [
        {
            "repoId": "target-service",
            "commitSha": DUMMY_SHA,
            "path": "src/billing/BillingService.kt",
            "kind": "class",
            "name": "BillingService",
            "qualifiedName": "com.target.billing.BillingService",
            "startLine": 10,
            "endLine": 45,
            "language": "kotlin",
            "modifiers": ["public", "open"],
            "metadata": {"boundedContext": "Billing"},
        },
        {
            "repoId": "target-service",
            "commitSha": DUMMY_SHA,
            "path": "src/billing/BillingService.kt",
            "kind": "method",
            "name": "processInvoice",
            "qualifiedName": "com.target.billing.BillingService.processInvoice(Invoice)",
            "parentQualifiedName": "com.target.billing.BillingService",
            "startLine": 20,
            "endLine": 35,
            "language": "kotlin",
            "signature": "fun processInvoice(invoice: Invoice): Result",
            "modifiers": ["public"],
        },
    ]

    extractor = CodeEntityExtractor()
    result = extractor.extract_from_mock(mock_records, SNAPSHOT_ID)

    assert result.summary.total_entities == 2
    assert result.summary.files_scanned == 1
    assert result.summary.counts_by_kind["class"] == 1
    assert result.summary.counts_by_kind["method"] == 1

    entity1, entity2 = result.entities
    assert entity1.name == "BillingService"
    assert entity1.kind == "class"
    assert entity1.metadata["boundedContext"] == "Billing"
    assert len(entity1.observation_id) == 64

    assert entity2.name == "processInvoice"
    assert entity2.parent_qualified_name == "com.target.billing.BillingService"


# -------------------------------------------------------------------------
# AC5: Canonical JSONL Graph Export (Architecture Contract §3.2 & D2)
# -------------------------------------------------------------------------


def test_canonical_jsonl_fact_records():
    java_code = "package test;\npublic class Item { public void ping() {} }"
    file = _make_source_file("Item.java", java_code, "java")
    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources([file], SNAPSHOT_ID)

    jsonl_lines = result.to_jsonl_lines()
    assert len(jsonl_lines) == 2

    # Verify each line is valid JSON with required contract fields
    for line in jsonl_lines:
        record = json.loads(line)
        assert record["schemaVersion"] == "1.0.0"
        assert record["recordType"] == "SymbolObservation"
        assert "recordId" in record
        assert record["snapshotId"] == SNAPSHOT_ID
        assert "payload" in record
        assert "evidenceReferences" in record
        assert record["evidenceReferences"][0].startswith("git:legacy-example-monolith@")


# -------------------------------------------------------------------------
# Integration with Real Loaded Reference Fixture (conftest.py)
# -------------------------------------------------------------------------


def test_extract_from_loaded_reference_fixture(reference):
    from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
    from migration_assistant.adapters.outbound.git.source_loader import load_sources

    config = reference.config()
    loaded = load_sources(config, LocalGitAdapter().checkout(config))

    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources(loaded.files, SNAPSHOT_ID)

    # In step-00, loaded has src/Main.java, pom.xml, and legacy.sql
    assert result.summary.files_scanned == 3
    # Main.java declares class Main
    main_cls = next((e for e in result.entities if e.name == "Main"), None)
    assert main_cls is not None
    assert main_cls.kind == "class"
    assert main_cls.path == "src/Main.java"
    assert main_cls.qualified_name == "Main"
    assert len(main_cls.observation_id) == 64


# -------------------------------------------------------------------------
# CLI Tests (extract_entities_cli.py)
# -------------------------------------------------------------------------


def test_cli_extract_from_mock_json(tmp_path):
    from migration_assistant.bootstrap.extract_entities_cli import main as cli_main

    mock_input = tmp_path / "mock.json"
    mock_input.write_text(
        json.dumps(
            [
                {
                    "repoId": "svc",
                    "commitSha": DUMMY_SHA,
                    "path": "Service.java",
                    "kind": "class",
                    "name": "Service",
                    "qualifiedName": "com.Service",
                    "startLine": 1,
                    "endLine": 10,
                }
            ]
        ),
        encoding="utf-8",
    )
    out_file = tmp_path / "entities.jsonl"

    exit_code = cli_main(["--mock", str(mock_input), "--out", str(out_file), "--snapshot-id", "snap-cli"])
    assert exit_code == 0
    assert out_file.is_file()

    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 1
    assert lines[0]["recordType"] == "SymbolObservation"
    assert lines[0]["snapshotId"] == "snap-cli"


def test_cli_extract_from_sources_jsonl(tmp_path):
    from migration_assistant.bootstrap.extract_entities_cli import main as cli_main

    file = _make_source_file("Account.java", "package com;\npublic class Account { void save() {} }", "java")
    sources_file = tmp_path / "sources.jsonl"
    sources_file.write_text(file.model_dump_json(by_alias=True) + "\n", encoding="utf-8")
    out_file = tmp_path / "entities.jsonl"

    exit_code = cli_main(["--sources", str(sources_file), "--out", str(out_file), "--snapshot-id", "snap-cli"])
    assert exit_code == 0
    assert out_file.is_file()

    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2  # class Account, method save


# -------------------------------------------------------------------------
# Error Resilience & Edge Cases
# -------------------------------------------------------------------------


def test_unparseable_or_empty_files_handled_gracefully():
    empty_file = _make_source_file("Empty.java", "", "java")
    malformed_sql = _make_source_file("broken.sql", "THIS IS NOT SQL AT ALL", "sql")

    extractor = CodeEntityExtractor()
    result = extractor.extract_from_sources([empty_file, malformed_sql], SNAPSHOT_ID)

    assert result.summary.total_entities == 0
    assert result.summary.files_scanned == 2
    assert len(result.entities) == 0
