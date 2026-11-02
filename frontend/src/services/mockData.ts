import { SourceEvidence } from '../types/chat';
import { Arc42ViewMetadata } from '../types/arc42';

export const INITIAL_SUGGESTIONS: string[] = [
  "Which parts of the legacy system have already been decommissioned in Step-06?",
  "What is currently implemented in Catalog Service (Step-06 vs Step-05)?",
  "Which legacy and target components still share database tables or routes?",
  "What are the top candidates for the next decommissioning step?"
];

export const MOCK_EVIDENCES: Record<string, SourceEvidence[]> = {
  catalog: [
    {
      id: "ev-01",
      repoId: "legacy-example-monolith",
      repoUrl: "https://github.com/amosproj/legacy-example-monolith",
      filePath: "src/main/java/com/example/legacy/catalog/CatalogItemResource.java",
      startLine: 42,
      endLine: 68,
      commitSha: "e9f3b12879a834e56c7104b281f6927d3598c11e",
      status: "decommissioned",
      snippet: "@Deprecated\n// Replaced by Target Catalog Service v2 in Step-06\n@Path(\"/api/v1/legacy/catalog\")\npublic class CatalogItemResource {\n    // Ingress disabled; routes to Strangler facade\n}",
      description: "Direct legacy REST endpoint deprecated and traffic routed via API Gateway Strangler proxy."
    },
    {
      id: "ev-02",
      repoId: "catalog-service-target",
      repoUrl: "https://github.com/amosproj/catalog-service-target",
      filePath: "src/catalog/domain/item_service.py",
      startLine: 18,
      endLine: 45,
      commitSha: "a1c72093bf65e4395e1d90a842b1093845cfb74a",
      status: "migrated",
      snippet: "class CatalogItemService:\n    \"\"\"Fully handles autonomous inventory and pricing lookups.\"\"\"\n    async def get_item_details(self, item_id: str) -> ItemDTO:\n        return await self.repo.find_by_id(item_id)",
      description: "Target Microservice implementation now handles read and write operations independently."
    },
    {
      id: "ev-03",
      repoId: "legacy-example-monolith",
      repoUrl: "https://github.com/amosproj/legacy-example-monolith",
      filePath: "src/main/resources/db/migration/V12__legacy_inventory_coupling.sql",
      startLine: 12,
      endLine: 24,
      commitSha: "c40761d4a8efb738129812739182379182739182",
      status: "coupled",
      snippet: "-- Shared inventory table still read by OrderProcessingJob\nSELECT item_id, stock_count FROM T_LEGACY_INVENTORY\nWHERE updated_at > :lastRun;",
      description: "Legacy background batch still queries the shared inventory table, blocking final schema drop."
    }
  ]
};

export const MOCK_ARC42_VIEWS: Arc42ViewMetadata[] = [
  {
    id: "context",
    section: "arc42 3. Context & Scope",
    title: "System Context View (Strangler Fig Architecture)",
    description: "External actors, API gateway proxying, and boundary between Legacy and Target systems.",
    mermaidSource: `flowchart TD
    User["Client Browser / Mobile App"]
    APIGateway["Strangler API Gateway"]
    LegacyApp["Legacy Monolith (legacy-example-monolith)"]
    TargetCatalog["Target Catalog Service (Step-06)"]
    TargetOrder["Target Order Service (Planned Step-07)"]
    SharedDB[(Shared PostgreSQL / DB)]

    User -->|HTTP / REST| APIGateway
    APIGateway -->|Route: /api/v1/legacy/*| LegacyApp
    APIGateway -->|Route: /api/v2/catalog/*| TargetCatalog
    LegacyApp -.->|Shared Coupling| SharedDB
    TargetCatalog -->|Autonomous Schema| SharedDB`
  },
  {
    id: "building_block",
    section: "arc42 5. Building Block View",
    title: "Building Block View with Migration Status",
    description: "Whitebox view comparing remaining legacy modules, migrated target services, and active coupling points.",
    mermaidSource: `flowchart LR
    subgraph LegacyMonolith["Legacy Monolith"]
        L_Catalog["CatalogItemResource (Decommissioned)"]:::decommissioned
        L_Order["OrderProcessingJob (Legacy Active)"]:::legacy
        L_Auth["LegacyAuthService (Legacy Active)"]:::legacy
    end

    subgraph TargetServices["Target System"]
        T_Catalog["CatalogService API v2 (Migrated)"]:::migrated
        T_Domain["Catalog Domain Model (Migrated)"]:::migrated
        T_Events["Domain Event Publisher (Migrated)"]:::migrated
    end

    subgraph CouplingBoundary["Remaining Coupling"]
        SharedTable[("T_LEGACY_INVENTORY")]:::coupled
    end

    L_Order -.->|Reads| SharedTable
    T_Catalog -->|Writes| SharedTable

    classDef decommissioned fill:#fef2f2,stroke:#f87171,stroke-width:1.5px,color:#991b1b;
    classDef legacy fill:#f5f5f5,stroke:#d4d4d4,stroke-width:1.5px,color:#404040;
    classDef migrated fill:#ecfdf5,stroke:#34d399,stroke-width:1.5px,color:#065f46;
    classDef coupled fill:#fffbeb,stroke:#fbbf24,stroke-width:1.5px,color:#92400e;`
  },
  {
    id: "deployment",
    section: "arc42 7. Deployment View",
    title: "Deployment View (Docker Compose Local Topology)",
    description: "Containerized deployment matching the industry partner contract (FastAPI, React, Neo4j, Local LLM).",
    mermaidSource: `flowchart TD
    subgraph LocalMachine["Local Developer Host / Docker Compose"]
        subgraph FrontendContainer["Frontend (Port 3000)"]
            ChatUI["SunsetTracker React App"]
        end

        subgraph BackendContainer["Backend (Port 8000)"]
            FastAPI["FastAPI Application"]
            MCP["In-Process MCP Facade"]
            Orchestrator["Chat Orchestrator"]
            LlmAdapter["OpenAI-Compatible Adapter"]
        end

        subgraph DatabaseTier["Persistence"]
            Neo4j[("Neo4j Graph Store (Port 7687)")]
        end

        subgraph LlmTier["Inference"]
            Ollama["Ollama Runtime (Port 11434)"]
        end
    end

    ChatUI -->|HTTP / JSON| FastAPI
    FastAPI --> MCP
    MCP --> Orchestrator
    Orchestrator --> LlmAdapter
    LlmAdapter -->|OpenAI HTTP| Ollama
    Orchestrator -->|Cypher| Neo4j`
  }
];
