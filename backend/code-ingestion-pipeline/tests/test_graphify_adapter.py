"""Direct Graphify API contract, tested without installing Graphify."""

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.adapters.outbound.graphify import GraphifyAdapter
from migration_assistant.bootstrap import cli


@pytest.fixture
def graphify_api(monkeypatch):
    calls = {}
    modules = {}
    names = ("graphify", "graphify.extract", "graphify.build", "graphify.export")
    for name in names:
        module = ModuleType(name)
        modules[name] = module
        monkeypatch.setitem(sys.modules, name, module)
    modules["graphify"].__path__ = []

    def extract(paths, *, root, cache_root):
        calls["extract"] = (paths, root, cache_root)
        source = paths[0].relative_to(root).as_posix()
        result = {
            "nodes": [
                {"id": "a", "label": "A", "source_file": source},
                {"id": "b", "label": "B", "source_file": source},
            ],
            "edges": [
                {"source": "a", "target": "b", "relation": relation, "source_file": source}
                for relation in ("calls", "references")
            ],
        }
        calls["extraction"] = result
        return result

    def build_from_json(extraction, **kwargs):
        calls["build"] = kwargs
        return extraction

    def to_json(graph, communities, output_path, **kwargs):
        calls["json"] = (communities, kwargs)
        Path(output_path).write_text(
            json.dumps({"nodes": graph["nodes"], "links": kwargs["original_links"]})
        )
        return True

    def to_html(graph, communities, output_path, **kwargs):
        calls["html"] = (communities, kwargs)
        Path(output_path).write_text("<html>graph</html>")
        return True

    modules["graphify.extract"].extract = extract
    modules["graphify.build"].build_from_json = build_from_json
    modules["graphify.export"].to_json = to_json
    modules["graphify.export"].to_html = to_html
    return calls, modules


def test_only_selected_original_paths_are_extracted(reference, tmp_path, graphify_api):
    calls, _ = graphify_api
    config = reference.config()
    checkout = LocalGitAdapter().checkout(config)
    loaded = load_sources(config, checkout)
    (member,) = checkout.members
    output = tmp_path / "graph"

    graph_path = GraphifyAdapter().build(member, loaded.files, checkout.workspace, output)

    paths, root, cache_root = calls["extract"]
    assert paths == [member.local_path / file.path for file in loaded.files]
    assert root == member.local_path
    assert cache_root == output
    assert calls["build"] == {"directed": False}
    assert calls["json"][0] == {}
    assert calls["json"][1]["built_at_commit"] == member.commit_sha
    assert calls["html"] == ({}, {"learning_overlay": {}})
    graph = json.loads(graph_path.read_text())
    assert len(graph["links"]) == 2  # Preserve parallel relationships.
    assert all(node["source_file"] == loaded.files[0].path for node in graph["nodes"])
    assert {path.name for path in graph_path.parent.iterdir()} == {"graph.json", "graph.html"}


def test_unparsed_sources_are_reported_without_discarding_extracted_graph(
    reference, tmp_path, graphify_api, caplog
):
    _, modules = graphify_api
    config = reference.config()
    loaded = load_sources(config, LocalGitAdapter().checkout(config))
    extract = modules["graphify.extract"].extract

    def partial(*args, **kwargs):
        return {**extract(*args, **kwargs), "failed_sources": ["pom.xml"]}

    modules["graphify.extract"].extract = partial
    path = GraphifyAdapter().build(
        loaded.checkout.members[0], loaded.files, loaded.checkout.workspace, tmp_path / "graph"
    )
    assert path.is_file()
    assert "pom.xml" in caplog.text
    assert "legacy-example-monolith" in caplog.text
    log = (tmp_path / "graph" / "extract.log").read_text()
    assert "pom.xml" in log
    assert "legacy-example-monolith" in log


def test_html_limit_failure_preserves_json(reference, tmp_path, graphify_api, capsys):
    _, modules = graphify_api

    def too_large(*args, **kwargs):
        raise ValueError("Graph too large for HTML viz")

    modules["graphify.export"].to_html = too_large
    code = cli.main(
        ["--config", str(reference.config_path), "--output-dir", str(tmp_path / "runs")]
    )
    assert code == 1
    assert "legacy-example-monolith" in capsys.readouterr().err
    (run,) = (tmp_path / "runs").iterdir()
    graph = run / "graphs" / "legacy-example-monolith" / "graphify-out" / "graph.json"
    assert graph.is_file()
    assert not graph.with_name("graph.html").exists()
    log = (graph.parent.parent / "extract.log").read_text()
    assert "Traceback" in log
    assert "Graph too large for HTML viz" in log
