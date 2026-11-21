"""Coordinate pinned source loading and independent component graph extraction."""

from collections import defaultdict
from collections.abc import Callable
from io import StringIO
from pathlib import Path

from migration_assistant.application.diagnostics import capture_diagnostics
from migration_assistant.application.ports.git_repo import GitRepo
from migration_assistant.application.ports.pipeline import (
    GraphBuilder,
    HandoffWriter,
    PipelineStorage,
    SourceLoader,
    PersistenceWriter
)
from migration_assistant.domain.pipeline import PipelineError, PipelineResult
from migration_assistant.domain.reference_source import ReferenceSourceConfig
from migration_assistant.domain.sources import LoadResult, SourceFile


class PipelineService:
    def __init__(
        self,
        *,
        git_repo: GitRepo,
        source_loader: SourceLoader,
        graph_builder: GraphBuilder,
        handoff_writer: HandoffWriter,
        storage: PipelineStorage,
        persistence_writer: PersistenceWriter
    ) -> None:
        self.git_repo = git_repo
        self.source_loader = source_loader
        self.graph_builder = graph_builder
        self.handoff_writer = handoff_writer
        self.storage = storage
        self.persistence_writer = persistence_writer

    def run(
        self,
        config: ReferenceSourceConfig,
        output: Path,
        *,
        source_export: Path | None = None,
        on_loaded: Callable[[LoadResult], None] | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> PipelineResult:
        output = output.expanduser().resolve()
        if source_export is not None:
            source_export = source_export.expanduser().resolve()
        bootstrap_log = StringIO()
        with capture_diagnostics(bootstrap_log):
            print(f"Loading stage: {config.stage}")
            checkout = self.git_repo.checkout(config)
            loaded = self.source_loader(config, checkout)
            for member in checkout.members:
                print(f"component: {member.repo_id} {member.commit_sha}")
            print(f"files loaded: {loaded.counts.loaded}")
        if not loaded.files:
            raise PipelineError(
                "No source files selected; check the stage, components and filters."
            )
        if on_loaded is not None:
            on_loaded(loaded)

        run = self.storage.create_run(output)
        (run / "bootstrap.log").write_text(bootstrap_log.getvalue(), encoding="utf-8")
        if progress is not None:
            progress(f"Run folder: {run}")
        try:
            sources_jsonl = run / "sources.jsonl"
            self.storage.write_sources(sources_jsonl, loaded.files)
            if source_export is not None:
                self.storage.write_sources(source_export, loaded.files)
            by_component: dict[str, list[SourceFile]] = defaultdict(list)
            for file in loaded.files:
                by_component[file.repo_id].append(file)
            graphs = {}
            for member in sorted(checkout.members, key=lambda member: member.repo_id):
                files = by_component.get(member.repo_id, [])
                if not files:
                    continue
                if progress is not None:
                    progress(f"Generating graph: {member.repo_id}")
                try:
                    graphs[member.repo_id] = self.graph_builder.build(
                        member, files, checkout.workspace, run / "graphs" / member.repo_id
                    )
                except (PipelineError, OSError, ValueError, RuntimeError) as error:
                    raise PipelineError(
                        f"Graph generation failed for component '{member.repo_id}': {error}"
                    ) from error
            try:
                handoff = self.handoff_writer(
                    list(graphs.values()), sources_jsonl, run, graph_mode="per-component"
                )
            except (OSError, ValueError, RuntimeError) as error:
                raise PipelineError(f"Canonical handoff failed: {error}") from error

            try:
                self.persistence_writer.persist_handoff(handoff)
            #TODO handle errors more gracefully here. This does not catch neo4j errors
            except (OSError, ValueError, RuntimeError) as error:
                raise PipelineError(f"Persistng code graph to neo4j failed: {error}") from error

        except (PipelineError, OSError, ValueError) as error:
            raise PipelineError(f"{error}; partial outputs: {run}") from error
        return PipelineResult(
            loaded,
            run,
            graphs,
            handoff.entity_count,
            handoff.relationship_count,
            handoff.snapshot_id,
        )
