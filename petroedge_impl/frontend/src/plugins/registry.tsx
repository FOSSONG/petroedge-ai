import { lazy } from "react";
import { Activity, Bot, BrainCircuit, Database, GitBranch, Lightbulb, Network, Orbit, Radio, ScrollText, ShieldCheck, Users, Workflow, Wrench } from "lucide-react";
import type { ModuleDefinition } from "./types";

const AgentsWorkspace = lazy(() => import("../features/operations/AgentsWorkspace").then(m => ({ default: m.AgentsWorkspace })));
const WorkflowsWorkspace = lazy(() => import("../features/operations/WorkflowsWorkspace").then(m => ({ default: m.WorkflowsWorkspace })));
const AiWorkspaceOverview = lazy(() => import("../features/platform/AiWorkspaceOverview").then(m => ({ default: m.AiWorkspaceOverview })));
const ModelMonitoringPanel = lazy(() => import("../features/models/ModelMonitoringPanel").then(m => ({ default: m.ModelMonitoringPanel })));
const ExperimentManagerPanel = lazy(() => import("../features/platform/ExperimentManagerPanel").then(m => ({ default: m.ExperimentManagerPanel })));
const OperationsPanels = {
  monitoring: lazy(() => import("../features/operations/OperationsPanels").then(m => ({ default: m.MonitoringPanel }))),
  twins: lazy(() => import("../features/operations/OperationsPanels").then(m => ({ default: m.TwinsPanel }))),
};

const makePanel = (moduleKey: string, title: string, description: string, resourceClass: "light"|"medium"|"heavy", capabilities: string[]) => lazy(async () => {
  const { CapabilityModulePanel } = await import("../features/plugins/CapabilityModulePanel");
  return { default: () => <CapabilityModulePanel moduleKey={moduleKey} title={title} description={description} resourceClass={resourceClass} capabilities={capabilities}/> };
});

const specs = [
  ["ai-control-centre","AI Control Centre","Unified project, operations, model and governance overview.","light",["Projects","Operations","Models","Validation","Monitoring"],<Activity/>],
  ["multi-agent","Multi-Agent Collaboration","Specialist domain agents coordinated through a governed orchestration layer.","medium",["Geologist agent","Petrophysicist agent","Reservoir agent","CCUS agent","QA agent"],<Bot/>],
  ["reasoning","Geological Reasoning Engine","Physics and geological rules check model predictions for plausibility.","medium",["Archie checks","Density-neutron logic","Stratigraphic ordering","Fluid-contact logic"],<BrainCircuit/>],
  ["knowledge-graph","Knowledge Graph","Context links across basins, fields, formations, wells, intervals and decisions.","medium",["Entities","Relationships","Context retrieval","Provenance"],<Network/>],
  ["workflow","Autonomous Workflow Engine","Governed automation from upload to review and learning eligibility.","light",["Quality checks","Interpretation jobs","Review routing","Learning queue"],<Workflow/>],
  ["recommendations","Recommendation System","Evidence-based next actions with uncertainty and limitations.","light",["Next-best action","Acquisition advice","Review flags","Confidence"],<Lightbulb/>],
  ["lineage","Data Provenance and Lineage","Trace outputs to datasets, model versions, features and reviews.","light",["Dataset versions","Model lineage","Audit trail","Feature provenance"],<GitBranch/>],
  ["governance","Advanced Model Governance","Champion-challenger lifecycle, metrics, approval gates and rollback.","light",["Model registry","Evaluation metrics","Deployment gates","Drift","Rollback"],<ShieldCheck/>],
  ["monitoring","Real-Time Monitoring","Operational health, inference latency, queues and hardware usage.","light",["API health","Latency","CPU and memory","Queue depth","Edge status"],<Radio/>],
  ["collaboration","Collaboration Workspace","Annotations, review requests, comments and role-based approval.","light",["Annotations","Reviews","Comments","Approvals"],<Users/>],
  ["digital-twin","Digital Twin","Well-centric interpretation, time travel, overlays and comparison.","medium",["Playback","Linked logs","Markers","Multi-well comparison","AI overlays"],<Orbit/>],
  ["decision-intelligence","Decision Intelligence","Integrated evidence, geological checks, expert agreement and recommendations.","medium",["Evidence synthesis","Risk","Confidence","Recommended action"],<Wrench/>],
  ["knowledge-repository","Digital Knowledge Repository","Validated interpretations, analogues, rules and lessons learned.","medium",["Case studies","Formation templates","Expert annotations","Retrieval"],<Database/>],
  ["research-hub","Research and Innovation Hub","Benchmark experiments safely without disturbing production models.","medium",["Experiments","Benchmarks","Evaluation","Promotion workflow"],<ScrollText/>],
] as const;

const functionalComponents: Record<string, ModuleDefinition["component"]> = {
  "ai-control-centre": AiWorkspaceOverview,
  "multi-agent": AgentsWorkspace,
  "workflow": WorkflowsWorkspace,
  "governance": ModelMonitoringPanel,
  "monitoring": OperationsPanels.monitoring,
  "digital-twin": OperationsPanels.twins,
  "research-hub": ExperimentManagerPanel,
};

export const builtInModules: ModuleDefinition[] = specs.map(([key,name,description,resourceClass,capabilities,icon]) => ({
  key,name,description,resourceClass,capabilities:[...capabilities],icon,
  component:functionalComponents[key] ?? makePanel(key,name,description,resourceClass,[...capabilities]),
}));
