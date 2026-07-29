# PetroEdge Multi-Agent AI

This milestone adds a deterministic, auditable domain-agent layer.

## Built-in agents

- Geologist
- Petrophysicist
- Reservoir Engineer
- Production Engineer
- Drilling Engineer
- CCUS

## API

- `GET /api/v1/agents`
- `GET /api/v1/agents/{agent_key}`
- `POST /api/v1/agents/{agent_key}/run`
- `POST /api/v1/agents/panel/run`

## Workflow integration

The node type `agents.panel` is available to the Workflow Engine.

The built-in workflow template is:

- `multi_agent_interpretation`

## Important implementation boundary

The current agents use deterministic domain rules and supplied evidence. They do not call an external large language model and do not claim unsupported geological or engineering conclusions. Future LLM-backed reasoning can be introduced behind the same agent interface after governance, prompt versioning, evaluation and audit controls are implemented.