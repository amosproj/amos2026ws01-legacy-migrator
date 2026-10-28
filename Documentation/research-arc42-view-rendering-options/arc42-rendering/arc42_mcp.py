#!/usr/bin/env python3
"""Prototype MCP tool handler for arc42 architecture view generation.

Provides:
- arc42_view(view: str, scope: str = "all", model_data: dict = None) -> dict
  Returns formatted Mermaid diagram + Markdown tables ready for chat rendering,
  along with status metrics (legacy, target, in-development, decommissioned).
"""

from typing import Any, Dict, Optional
from pathlib import Path
import json

from generate import (
    load,
    mermaid_context,
    mermaid_building_block,
    mermaid_deployment,
    tables,
    STATUS_STYLE,
)

VALID_VIEWS = ("context", "building_block", "deployment")


def filter_by_scope(model: Dict[str, Any], scope: str) -> Dict[str, Any]:
    """Filters containers and relationships by bounded context / scope."""
    if not scope or scope.lower() == "all":
        return model

    scope_lower = scope.lower()
    scoped_containers = [
        c for c in model.get("containers", [])
        if scope_lower in c.get("id", "").lower()
        or scope_lower in c.get("name", "").lower()
        or scope_lower in c.get("group", "").lower()
    ]
    scoped_ids = {c["id"] for c in scoped_containers}
    valid_endpoints = (
        scoped_ids
        | {a["id"] for a in model.get("actors", [])}
        | {e["id"] for e in model.get("external_systems", [])}
        | {model.get("system", {}).get("id", "")}
    )

    scoped_relationships = [
        r for r in model.get("relationships", [])
        if r["from"] in valid_endpoints and r["to"] in valid_endpoints
    ]

    filtered = dict(model)
    filtered["containers"] = scoped_containers
    filtered["relationships"] = scoped_relationships
    return filtered


def get_status_summary(model: Dict[str, Any]) -> Dict[str, int]:
    """Computes distribution of components across migration lifecycle."""
    counts = {k: 0 for k in STATUS_STYLE.keys()}
    for c in model.get("containers", []):
        st = c.get("status", "legacy")
        counts[st] = counts.get(st, 0) + 1
    return counts


def arc42_view(
    view: str,
    scope: str = "all",
    model_path: Optional[str] = None,
    model_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """MCP tool execution function for arc42 view rendering.

    Args:
        view: One of 'context', 'building_block', or 'deployment'.
        scope: Filter scope ('all', or a keyword/bounded context name).
        model_path: Optional filesystem path to views.json.
        model_data: In-memory dictionary representing graph query result.

    Returns:
        Dictionary with:
          - 'view': view type
          - 'scope': applied scope
          - 'diagram': Mermaid code block
          - 'tables': Markdown documentation table
          - 'summary': Component count per migration status
          - 'formatted_output': Full markdown string ready for LLM chat UI response
    """
    view_lower = view.lower().strip()
    if view_lower not in VALID_VIEWS:
        raise ValueError(
            f"Invalid view '{view}'. Supported views: {', '.join(VALID_VIEWS)}"
        )

    if model_data is not None:
        model = dict(model_data)
    elif model_path is not None:
        model = load(model_path)
    else:
        default_fixture = Path(__file__).parent / "model" / "views.json"
        if default_fixture.exists():
            model = load(str(default_fixture))
        else:
            raise FileNotFoundError("No view model provided and default fixture not found.")

    scoped_model = filter_by_scope(model, scope)
    summary = get_status_summary(scoped_model)

    if view_lower == "context":
        title = "arc42 §3 - System Context & Interfaces"
        diagram = mermaid_context(scoped_model)
        _, table_text = tables(scoped_model)
    elif view_lower == "building_block":
        title = "arc42 §5 - Building Block View (Level 1)"
        diagram = mermaid_building_block(scoped_model)
        table_text, _ = tables(scoped_model)
    else:  # deployment
        title = "arc42 §7 - Deployment & Runtime Topology"
        diagram = mermaid_deployment(scoped_model)
        bb_table, cp_table = tables(scoped_model)
        table_text = f"### Coupling & Interfaces\n\n{cp_table}"

    # Build human-readable response formatted for chat UI / LibreChat
    formatted = [
        f"## {title}",
        f"**Scope:** `{scope}` | **Components:** {len(scoped_model.get('containers', []))} total "
        f"({summary.get('target', 0)} target, {summary.get('in-development', 0)} in-dev, "
        f"{summary.get('legacy', 0)} legacy, {summary.get('decommissioned', 0)} decommissioned)\n",
        "```mermaid",
        diagram,
        "```\n",
        "### Documentation Table\n",
        table_text,
    ]

    return {
        "view": view_lower,
        "scope": scope,
        "diagram": diagram,
        "table": table_text,
        "summary": summary,
        "formatted_output": "\n".join(formatted),
    }


if __name__ == "__main__":
    import sys

    view_arg = sys.argv[1] if len(sys.argv) > 1 else "building_block"
    scope_arg = sys.argv[2] if len(sys.argv) > 2 else "all"
    res = arc42_view(view_arg, scope_arg)
    print(res["formatted_output"])
