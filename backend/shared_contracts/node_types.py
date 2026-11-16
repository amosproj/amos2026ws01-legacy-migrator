"""Node labels already defined by the graph and architecture contracts."""

from enum import StrEnum


class GraphNodeType(StrEnum):
    """Combined node taxonomy from the graph schema and architecture contract."""

    PROJECT = "Project"
    SNAPSHOT = "Snapshot"
    COMPONENT = "Component"
    COMPONENT_STATE = "ComponentState"
    CODE_GRAPH = "CodeGraph"
    FILE = "File"
    CLASS = "Class"
    INTERFACE = "Interface"
    METHOD = "Method"
    FUNCTION = "Function"
    FIELD = "Field"
    ENUM = "Enum"
    TABLE = "Table"
    CODE_ENTITY = "CodeEntity"
    EXTERNAL_SYMBOL = "ExternalSymbol"
    MODULE = "Module"
    SYMBOL_OBSERVATION = "SymbolObservation"
    COMMIT = "Commit"
    ACTOR = "Actor"
    EXTERNAL_SYSTEM = "ExternalSystem"
    BOUNDED_CONTEXT = "BoundedContext"
    DEPLOYMENT_NODE = "DeploymentNode"
    MESSAGING_ROUTE = "MessagingRoute"
    JIRA_ISSUE = "JiraIssue"
    CONFLUENCE_PAGE = "ConfluencePage"
    MARKDOWN_FILE = "MarkdownFile"
    DOC_CHUNK = "DocChunk"
    MIGRATION_STATUS = "MigrationStatus"
    EXTRACTION_RUN = "ExtractionRun"


SOURCE_LOCATED_NODE_TYPES = frozenset(
    {
        GraphNodeType.CLASS,
        GraphNodeType.INTERFACE,
        GraphNodeType.METHOD,
        GraphNodeType.FUNCTION,
        GraphNodeType.FIELD,
        GraphNodeType.ENUM,
        GraphNodeType.TABLE,
        GraphNodeType.CODE_ENTITY,
        GraphNodeType.SYMBOL_OBSERVATION,
    }
)
