from typing import Any

from ..domain.models import ResearchProject

# Tool definitions (JSON Schema format compatible with typical LLM function calling)
TOOLS_SCHEMA = [
    {
        "name": "CodeSearch",
        "description": "Search for code symbols (variables, classes, functions) across the project.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Symbol name or partial name to search for"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "ASTQuery",
        "description": "Lookup the AST structural parent or dependencies of a specific code artifact.",
        "parameters": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "The exact artifactId to query."}
            },
            "required": ["artifact_id"]
        }
    },
    {
        "name": "PaperSearch",
        "description": "Search the manuscript sections for a specific keyword or phrase.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "The term to find in the paper"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "ClaimLookup",
        "description": "Fetch all extracted scientific claims or parameter statements from the manuscript.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "EquationLookup",
        "description": "Fetch parsed equations and their variables from the manuscript.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "GraphTraversal",
        "description": "Traverse the deterministic graph downstream from a specific artifact ID to see what is affected.",
        "parameters": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "The source artifactId"}
            },
            "required": ["artifact_id"]
        }
    },
]

def execute_tool(tool_name: str, args: dict[str, Any], project: ResearchProject) -> Any:
    """
    Dispatcher for explicit bounded tools.
    """
    if tool_name == "CodeSearch":
        query = args.get("query", "").lower()
        results = []
        for art in project.artifacts.code:
            if query in (art.symbolName or "").lower():
                results.append({
                    "id": art.artifactId,
                    "name": art.symbolName,
                    "kind": art.symbolKind,
                    "file": art.exactLocation,
                    "value": art.extractedValue
                })
        return {"matches": results[:10]}

    elif tool_name == "ASTQuery":
        art_id = args.get("artifact_id")
        art = next((a for a in project.artifacts.code if a.artifactId == art_id), None)
        if not art:
            return {"error": "Artifact not found"}
        return {
            "id": art.artifactId,
            "name": art.symbolName,
            "kind": art.symbolKind,
            "file": art.exactLocation
        }

    elif tool_name == "PaperSearch":
        kw = args.get("keyword", "").lower()
        results = []
        for sec in project.artifacts.sections:
            if kw in (sec.title or "").lower() or kw in (sec.extractedValue or "").lower():
                results.append({
                    "id": sec.artifactId,
                    "title": sec.title,
                    "snippet": sec.extractedValue[:200] if sec.extractedValue else ""
                })
        return {"matches": results[:5]}
        
    elif tool_name == "ClaimLookup":
        claims = [c for c in project.artifacts.sections if c.artifactType == 'CLAIM']
        results = [{"id": c.artifactId, "value": c.extractedValue} for c in claims]
        return {"claims": results[:10]}
        
    elif tool_name == "EquationLookup":
        eqs = project.artifacts.equations
        results = [{"id": e.artifactId, "label": e.label} for e in eqs]
        return {"equations": results}
        
    elif tool_name == "GraphTraversal":
        art_id = args.get("artifact_id")
        # Find edges where source is art_id
        edges = [e for e in project.evidenceRecords if e.sourceArtifactId == art_id]
        results = [{"targetId": e.targetArtifactId, "relationship": e.relationshipType.value} for e in edges]
        return {"downstream_edges": results}
        
    else:
        return {"error": f"Unknown tool {tool_name}"}
