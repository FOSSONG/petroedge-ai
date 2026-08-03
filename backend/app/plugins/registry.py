from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ResourceClass = Literal["light", "medium", "heavy"]


@dataclass(frozen=True, slots=True)
class BuiltinModule:
    key: str
    name: str
    description: str
    resource_class: ResourceClass
    capabilities: tuple[str, ...]
    enabled: bool = True
    lazy: bool = True


BUILTIN_MODULES: tuple[BuiltinModule, ...] = (
    BuiltinModule("ai-control-centre", "AI Control Centre", "Unified project, operation, model and governance overview.", "light", ("projects", "operations", "models", "validation", "monitoring")),
    BuiltinModule("multi-agent", "Multi-Agent Collaboration", "Coordinated specialist agents with a governance review stage.", "medium", ("orchestration", "geology agent", "petrophysics agent", "reservoir agent", "QA agent")),
    BuiltinModule("reasoning", "Geological Reasoning Engine", "Physics and geological-rule checks alongside model predictions.", "medium", ("Archie checks", "density-neutron logic", "stratigraphic ordering", "fluid-contact logic")),
    BuiltinModule("knowledge-graph", "Knowledge Graph", "Links basins, fields, formations, wells, intervals, predictions and reviews.", "medium", ("entities", "relationships", "provenance", "context retrieval")),
    BuiltinModule("workflow", "Autonomous Workflow Engine", "Governed automation from upload through interpretation and validation.", "light", ("quality checks", "interpretation jobs", "review routing", "learning queue")),
    BuiltinModule("recommendations", "Recommendation System", "Evidence-based next actions with uncertainty and limitations.", "light", ("data acquisition advice", "review flags", "next-best action", "confidence")),
    BuiltinModule("lineage", "Data Provenance and Lineage", "Trace predictions to data, model versions, features and expert decisions.", "light", ("dataset versions", "model lineage", "audit trail", "feature provenance")),
    BuiltinModule("governance", "Advanced Model Governance", "Champion-challenger lifecycle, approval gates, drift and retirement.", "light", ("registry", "evaluation metrics", "deployment gates", "rollback")),
    BuiltinModule("monitoring", "Real-Time Monitoring", "Operational health, inference latency, queues and resource usage.", "light", ("API health", "latency", "CPU and memory", "edge status")),
    BuiltinModule("collaboration", "Collaboration Workspace", "Multidisciplinary annotations, reviews, comments and approvals.", "light", ("annotations", "review requests", "comments", "role-based approval")),
    BuiltinModule("digital-twin", "Digital Twin", "Lazy-loaded well-centric interpretation and comparison workspace.", "medium", ("playback", "linked logs", "markers", "multi-well comparison", "AI overlays")),
    BuiltinModule("decision-intelligence", "Decision Intelligence", "Combines predictions, geological checks, expert agreement and recommendations.", "medium", ("integrated evidence", "risk", "confidence", "recommended action")),
    BuiltinModule("knowledge-repository", "Digital Knowledge Repository", "Validated interpretations, rules, analogues and lessons learned.", "medium", ("case studies", "formation templates", "expert annotations", "retrieval")),
    BuiltinModule("research-hub", "Research and Innovation Hub", "Safe experimentation and benchmarking without affecting production models.", "medium", ("experiments", "benchmarks", "evaluation", "promotion workflow")),
)


def module_catalogue() -> list[dict[str, object]]:
    return [asdict(module) for module in BUILTIN_MODULES]
