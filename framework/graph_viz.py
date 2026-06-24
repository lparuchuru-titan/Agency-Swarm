"""LangGraph diagram export for FleetView (video-style graph visualization)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents_registry import GRAPH_NODES


def orchestrator_mermaid(active_node: Optional[str] = None, pipeline: Optional[List[str]] = None) -> str:
    """Mermaid diagram: core LangGraph + dynamic team pipeline."""
    lines = ["graph TD", "  __start__((START))", "  plan[Router / Plan]", "  dispatch[Dispatch loop]", "  finalize[Finalize]", "  __end__((END))"]
    lines.append("  __start__ --> plan")
    lines.append("  plan --> dispatch")
    lines.append("  dispatch --> finalize")
    lines.append("  finalize --> __end__")

    team_pipeline = pipeline or [n["id"] for n in GRAPH_NODES if n["id"].endswith("_team")]
    if team_pipeline:
        lines.append("")
        lines.append("  subgraph teams [Team pipeline]")
        for i, node in enumerate(team_pipeline):
            label = next((g["label"] for g in GRAPH_NODES if g["id"] == node), node)
            nid = node.replace("_team", "_n")
            active_class = ":::active" if active_node == node else ""
            lines.append(f"    {nid}[{label}]{active_class}")
            if i > 0:
                prev = team_pipeline[i - 1].replace("_team", "_n")
                lines.append(f"    {prev} --> {nid}")
        lines.append("  end")
        lines.append("  plan -.-> teams")

    if active_node == "plan":
        lines.append("  class plan activeNode")
    elif active_node == "finalize":
        lines.append("  class finalize activeNode")
    elif active_node == "dispatch":
        lines.append("  class dispatch activeNode")

    lines.extend(
        [
            "",
            "  classDef activeNode fill:#1e3a5f,stroke:#60a5fa,stroke-width:2px,color:#e8edf4",
            "  classDef active fill:#1e3a5f,stroke:#22d3ee,stroke-width:2px",
        ]
    )
    return "\n".join(lines)


def langgraph_native_structure() -> Dict[str, Any]:
    """Nodes/edges from compiled LangGraph app."""
    try:
        from langgraph_orchestrator import build_orchestrator_graph

        app = build_orchestrator_graph()
        g = app.get_graph()
        nodes = list(g.nodes.keys()) if hasattr(g, "nodes") else []
        edges = []
        if hasattr(g, "edges"):
            for e in g.edges:
                if isinstance(e, tuple) and len(e) >= 2:
                    edges.append([str(e[0]), str(e[1])])
                else:
                    edges.append([str(e), ""])
        return {"nodes": nodes, "edges": edges}
    except Exception as exc:  # noqa: BLE001
        return {"nodes": ["plan", "dispatch", "finalize"], "edges": [], "error": str(exc)}


def graph_diagram(
    active_node: Optional[str] = None,
    pipeline: Optional[List[str]] = None,
    router_method: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "mermaid": orchestrator_mermaid(active_node, pipeline),
        "native": langgraph_native_structure(),
        "pipeline": pipeline or [],
        "active_node": active_node,
        "router_method": router_method,
        "team_nodes": GRAPH_NODES,
    }
