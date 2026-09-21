from __future__ import annotations

from app.workflows.schemas import NodeSpec, WorkflowDefinition


BUILTIN_TEMPLATES: tuple[WorkflowDefinition, ...] = (
    WorkflowDefinition(
        id="well_log_interpretation",
        name="Well-log Interpretation",
        description="QC, feature summary, basic petrophysics, model selection and report.",
        tags=["well-logs", "petrophysics", "ai"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(id="features", type="features.summary", depends_on=["qc"]),
            NodeSpec(id="petrophysics", type="petrophysics.basic", depends_on=["features"]),
            NodeSpec(
                id="model",
                type="ai.model",
                parameters={"model": "random_forest"},
                depends_on=["petrophysics"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Well-log Interpretation Report"},
                depends_on=["qc", "petrophysics", "model"],
            ),
        ],
    ),
    WorkflowDefinition(
        id="production_forecast",
        name="Production Forecast",
        description="Production QC, feature summary and causal GRU capability resolution.",
        tags=["production", "forecasting", "gru"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(id="features", type="features.summary", depends_on=["qc"]),
            NodeSpec(
                id="model",
                type="ai.model",
                parameters={"model": "gru"},
                depends_on=["features"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Production Forecast Report"},
                depends_on=["model"],
            ),
        ],
    ),
    WorkflowDefinition(
        id="historical_replay",
        name="Historical Replay",
        description="Historical contextual analysis using the BiGRU capability.",
        tags=["replay", "bigru", "sequence"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(
                id="model",
                type="ai.model",
                parameters={"model": "bigru"},
                depends_on=["qc"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Historical Replay Report"},
                depends_on=["model"],
            ),
        ],
    ),
    WorkflowDefinition(
        id="multi_agent_interpretation",
        name="Multi-Agent Reservoir Interpretation",
        description="Petrophysical processing followed by coordinated domain-agent analysis.",
        tags=["multi-agent", "petrophysics", "reservoir"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(id="features", type="features.summary", depends_on=["qc"]),
            NodeSpec(id="petrophysics", type="petrophysics.basic", depends_on=["features"]),
            NodeSpec(
                id="agents",
                type="agents.panel",
                parameters={
                    "agents": [
                        "geologist",
                        "petrophysicist",
                        "reservoir_engineer",
                        "production_engineer",
                        "drilling_engineer",
                        "ccus",
                    ]
                },
                depends_on=["petrophysics"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Multi-Agent Reservoir Interpretation"},
                depends_on=["agents"],
            ),
        ],
    ),)