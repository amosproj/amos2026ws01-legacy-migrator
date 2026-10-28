#!/usr/bin/env python3
"""Unit tests for arc42 view generator (generate.py) and MCP tool handler (arc42_mcp.py).

Validates:
- Deterministic output across repeated runs (byte-identical)
- Mermaid Context, Building Block, and Deployment generation
- Markdown table emission and coupling interaction tracking
- LikeC4 model and Structurizr DSL syntax emission
- Safe escaping of special characters and status styling
- MCP tool execution, scope filtering, and status metric calculation
"""

import json
import tempfile
import unittest
from pathlib import Path

import generate
import arc42_mcp


class TestArc42Generator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_path = Path(__file__).parent / "model" / "views.json"
        with open(cls.fixture_path, "r", encoding="utf-8") as f:
            cls.model_data = json.load(f)

    def setUp(self):
        self.model = generate.load(str(self.fixture_path))

    def test_load_deterministic_sorting(self):
        """Ensure load() sorts containers, actors, and relationships consistently."""
        container_ids = [c["id"] for c in self.model["containers"]]
        self.assertEqual(container_ids, sorted(container_ids))

        actor_ids = [a["id"] for a in self.model["actors"]]
        self.assertEqual(actor_ids, sorted(actor_ids))

        rel_keys = [(r["from"], r["to"]) for r in self.model["relationships"]]
        self.assertEqual(rel_keys, sorted(rel_keys))

    def test_mermaid_context_view(self):
        """Verify Context View generation (actors, system boundary, and interfaces)."""
        content = generate.mermaid_context(self.model)
        self.assertTrue(content.startswith("flowchart LR"))
        self.assertIn('cos["Customer Order Services<br/><i>legacy + target landscape</i>"]', content)
        self.assertIn('shopper(["Shopper"])', content)
        self.assertIn('shopper -->|"Uses"| cos', content)
        self.assertIn("classDef external", content)

    def test_mermaid_building_block_view(self):
        """Verify Building Block View (subgraphs, node styling, status tags)."""
        content = generate.mermaid_building_block(self.model)
        self.assertTrue(content.startswith("flowchart LR"))
        self.assertIn('subgraph legacy_grp["Legacy"]', content)
        self.assertIn('subgraph target_grp["Target"]', content)
        self.assertIn('subgraph data_grp["Data & messaging"]', content)
        self.assertIn(":::legacy", content)
        self.assertIn(":::in_development", content)
        self.assertIn("classDef target fill:#9fc5e8,stroke:#1f5fa8", content)
        self.assertIn("classDef decommissioned fill:#ffffff,stroke:#999999,stroke-dasharray:5,color:#999999", content)

    def test_mermaid_deployment_view(self):
        """Verify Deployment View (nested nodes, instances, runtime relations)."""
        content = generate.mermaid_deployment(self.model)
        self.assertTrue(content.startswith("flowchart TB"))
        self.assertIn('subgraph ocp["OpenShift cluster<br/><i>Kubernetes</i>"]', content)
        self.assertIn('subgraph ns_app["Namespace app-mod-dev<br/><i>Tekton-built images</i>"]', content)
        self.assertIn('catalog_service["Catalog service (strangled)', content)
        self.assertIn("classDef", content)

    def test_markdown_tables(self):
        """Verify accompanying Markdown documentation tables for blocks and coupling."""
        bb_table, cp_table = generate.tables(self.model)
        self.assertIn("| Building block | Technology | Status | Source |", bb_table)
        self.assertIn("| Remaining monolith: orders, customers, cart | Open Liberty, Java EE | legacy |", bb_table)
        self.assertIn("| Catalog service (strangled) | Quarkus reactive | target |", bb_table)

        self.assertIn("| From | To | Interaction | Coupling |", cp_table)
        self.assertIn("shared-data", cp_table)
        self.assertIn("messaging", cp_table)

    def test_likec4_generation(self):
        """Verify LikeC4 DSL generation output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            generate.write_likec4(self.model, out_dir)
            model_c4 = out_dir / "likec4" / "model.c4"
            self.assertTrue(model_c4.exists())
            text = model_c4.read_text(encoding="utf-8")
            self.assertIn("model {", text)
            self.assertIn("shopper = actor 'Shopper'", text)
            self.assertIn("catalog_service = container 'Catalog service (strangled)'", text)
            self.assertIn("#target", text)
            self.assertIn("view context {", text)
            self.assertIn("view building_block of cos {", text)
            self.assertIn("deployment view deployment {", text)

    def test_structurizr_generation(self):
        """Verify Structurizr DSL workspace generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            generate.write_structurizr(self.model, out_dir)
            workspace_dsl = out_dir / "structurizr" / "workspace.dsl"
            self.assertTrue(workspace_dsl.exists())
            text = workspace_dsl.read_text(encoding="utf-8")
            self.assertIn('workspace "Customer Order Services"', text)
            self.assertIn('shopper = person "Shopper"', text)
            self.assertIn('catalog_service = container "Catalog service (strangled)"', text)
            self.assertIn('prod = deploymentEnvironment "OpenShift (app-mod-dev)"', text)
            self.assertIn('systemContext cos "context"', text)
            self.assertIn('container cos "building_block"', text)
            self.assertIn('deployment cos prod "deployment"', text)

    def test_deterministic_output(self):
        """Ensure repeated generator runs produce byte-identical outputs."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = Path(tmp1)
            p2 = Path(tmp2)
            generate.write_mermaid(self.model, p1)
            generate.write_likec4(self.model, p1)
            generate.write_structurizr(self.model, p1)

            generate.write_mermaid(self.model, p2)
            generate.write_likec4(self.model, p2)
            generate.write_structurizr(self.model, p2)

            for f1 in p1.rglob("*"):
                if f1.is_file():
                    rel = f1.relative_to(p1)
                    f2 = p2 / rel
                    self.assertTrue(f2.exists(), f"File {rel} missing in second run")
                    self.assertEqual(f1.read_bytes(), f2.read_bytes(), f"Output difference in {rel}")

    def test_escaping(self):
        """Ensure string escaping prevents formatting and delimiter collisions."""
        self.assertEqual(generate.esc('Hello "World"'), "Hello 'World'")
        self.assertEqual(generate.esc("Plain"), "Plain")

    def test_mcp_tool_all_views(self):
        """Verify arc42_view executes correctly for all standard views."""
        for v in ("context", "building_block", "deployment"):
            res = arc42_mcp.arc42_view(view=v, scope="all", model_data=self.model_data)
            self.assertEqual(res["view"], v)
            self.assertIn("```mermaid", res["formatted_output"])
            self.assertGreater(res["summary"]["target"], 0)

    def test_mcp_tool_scoping(self):
        """Verify arc42_view filters elements correctly when a scope is provided."""
        res = arc42_mcp.arc42_view(view="building_block", scope="catalog", model_data=self.model_data)
        self.assertEqual(res["scope"], "catalog")
        self.assertIn("Catalog service (strangled)", res["formatted_output"])
        self.assertNotIn("Remaining monolith", res["formatted_output"])

    def test_mcp_tool_invalid_view(self):
        """Verify arc42_view raises ValueError on unsupported views."""
        with self.assertRaises(ValueError):
            arc42_mcp.arc42_view(view="invalid_view", model_data=self.model_data)


if __name__ == "__main__":
    unittest.main()
