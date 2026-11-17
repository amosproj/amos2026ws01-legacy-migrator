"""Extract per-component graphs directly from pinned checkout files."""

import logging
from pathlib import Path

from migration_assistant.application.diagnostics import capture_diagnostics
from migration_assistant.domain.checkout import ComponentCheckout
from migration_assistant.domain.pipeline import PipelineError
from migration_assistant.domain.sources import SourceFile

logger = logging.getLogger(__name__)


class GraphifyAdapter:
    def build(
        self, member: ComponentCheckout, files: list[SourceFile], root: Path, output: Path
    ) -> Path:
        output.mkdir(parents=True, exist_ok=True)
        with (
            (output / "extract.log").open("w", encoding="utf-8") as log,
            capture_diagnostics(log),
        ):
            return self._build(member, files, root, output)

    def _build(
        self, member: ComponentCheckout, files: list[SourceFile], root: Path, output: Path
    ) -> Path:
        try:
            from graphify.build import build_from_json
            from graphify.export import to_html, to_json
            from graphify.extract import extract
        except ImportError as error:
            raise PipelineError(
                "Graphify dependencies are unavailable; run uv sync --locked from backend/."
            ) from error

        component_root = member.local_path.resolve()
        # Develop's per-component runner scans each reconstructed component as
        # its own root. Preserve those relative paths and Graphify node IDs
        # when reading the selected files directly from the checkout instead.
        # Do not prepend repo_id: that would change the canonical handoff.
        paths = [(component_root / file.path).resolve() for file in files]
        artifacts = output / "graphify-out"
        artifacts.mkdir(parents=True, exist_ok=True)
        extraction = extract(paths, root=component_root, cache_root=output)
        if extraction.get("failed_sources"):
            # Graphify also reports unsupported grammars and empty parses here.
            # Keep the extracted portion, matching its code-only CLI behavior.
            logger.warning(
                "Component %s: Graphify produced no nodes for %s",
                member.repo_id,
                extraction["failed_sources"],
            )
        # Use the same graph-building defaults as develop's cluster-only load;
        # original_links below retains parallel edges and their direction even
        # though community calculation and report generation are omitted.
        graph = build_from_json(extraction, directed=bool(extraction.get("directed", False)))
        # Optional: call graphify.cluster.cluster and label_communities_by_hub
        # here, then pass their communities/labels to both exporters below.
        # graphify.cluster.score_all, graphify.analyze and graphify.report.generate
        # can provide analysis and a report if those artifacts are needed later.
        graph_path = artifacts / "graph.json"
        if not to_json(
            graph,
            {},
            str(graph_path),
            built_at_commit=member.commit_sha,
            original_links=extraction["edges"],
        ):
            raise PipelineError("Graphify refused to write graph.json")
        if not to_html(graph, {}, str(artifacts / "graph.html"), learning_overlay={}):
            raise PipelineError("Graphify did not write graph.html")
        for name in ("graph.json", "graph.html"):
            artifact = artifacts / name
            if not artifact.is_file() or not artifact.stat().st_size:
                raise PipelineError(f"Graphify did not produce {name}")
        return graph_path
