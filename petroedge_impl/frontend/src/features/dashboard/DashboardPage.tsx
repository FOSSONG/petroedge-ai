import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { AppBar, Box, Button, Chip, Container, IconButton, LinearProgress, Tab, Tabs, Toolbar, Tooltip, Typography } from "@mui/material";
import { Activity, Bell, Bot, Boxes, BrainCircuit, BriefcaseBusiness, DatabaseZap, FlaskConical, FolderKanban, Gauge, GitBranch, HeartPulse, LogOut, Moon, Network, PlayCircle, Plug, Presentation, Radio, ScrollText, ShieldCheck, Sun, UploadCloud, Waypoints } from "lucide-react";
import type { AuthenticatedUser } from "../../api/types";
import { RealtimeStatus } from "../../realtime";
import { ModuleHub } from "../../plugins/ModuleHub";
import { builtInModules } from "../../plugins/registry";
import { useThemeMode } from "../../theme";
import { PanelErrorBoundary } from "../../components/PanelErrorBoundary";

const AiWorkspaceOverview = lazy(() => import("../platform/AiWorkspaceOverview").then((m) => ({ default: m.AiWorkspaceOverview })));
const ReservoirIntelligencePanel = lazy(() => import("../platform/ReservoirIntelligencePanel").then((m) => ({ default: m.ReservoirIntelligencePanel })));
const DatasetRegistryPanel = lazy(() => import("../platform/DatasetRegistryPanel").then((m) => ({ default: m.DatasetRegistryPanel })));
const TrainingWorkspacePanel = lazy(() => import("../platform/TrainingWorkspacePanel").then((m) => ({ default: m.TrainingWorkspacePanel })));
const ExperimentManagerPanel = lazy(() => import("../platform/ExperimentManagerPanel").then((m) => ({ default: m.ExperimentManagerPanel })));
const DemoModePanel = lazy(() => import("../platform/DemoModePanel").then((m) => ({ default: m.DemoModePanel })));
const OverviewPanel = lazy(() => import("./OverviewPanel").then((m) => ({ default: m.OverviewPanel })));
const WellLogViewer = lazy(() => import("../welllogs/WellLogViewer").then((m) => ({ default: m.WellLogViewer })));
const AlertsPanel = lazy(() => import("../alerts/AlertsPanel").then((m) => ({ default: m.AlertsPanel })));
const ModelEvaluationPanel = lazy(() => import("../models/ModelEvaluationPanel").then((m) => ({ default: m.ModelEvaluationPanel })));
const ModelMonitoringPanel = lazy(() => import("../models/ModelMonitoringPanel").then((m) => ({ default: m.ModelMonitoringPanel })));
const JobsPanel = lazy(() => import("../jobs/JobsPanel").then((m) => ({ default: m.JobsPanel })));
const RealtimeEventFeed = lazy(() => import("../../realtime/RealtimeEventFeed").then((m) => ({ default: m.RealtimeEventFeed })));
const WellLogPlotlyPanel = lazy(() => import("../platform/WellLogPlotlyPanel").then((m) => ({ default: m.WellLogPlotlyPanel })));
const LasWizardPanel = lazy(() => import("../platform/LasWizardPanel").then((m) => ({ default: m.LasWizardPanel })));
const DigitalReplayPanel = lazy(() => import("../platform/DigitalReplayPanel").then((m) => ({ default: m.DigitalReplayPanel })));
const AiAssistantPanel = lazy(() => import("../platform/AiAssistantPanel").then((m) => ({ default: m.AiAssistantPanel })));
const AssetManagementPanel = lazy(() => import("../platform/AssetManagementPanel").then((m) => ({ default: m.AssetManagementPanel })));
const AgentsPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.AgentsPanel })));
const WorkflowsPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.WorkflowsPanel })));
const TwinsPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.TwinsPanel })));
const RulesPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.RulesPanel })));
const EventsPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.EventsPanel })));
const PluginsPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.PluginsPanel })));
const EdgePanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.EdgePanel })));
const ReportsPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.ReportsPanel })));
const MonitoringPanel = lazy(() => import("../operations/OperationsPanels").then((m) => ({ default: m.MonitoringPanel })));

interface Props { user: AuthenticatedUser; onLogout: () => void; }

type CoreTab = { label: string; icon: JSX.Element; panel: JSX.Element };

export function DashboardPage({ user, onLogout }: Props) {
  const {mode,toggle}=useThemeMode();
  const [selectedTab, setSelectedTab] = useState(0);
  const [openedModuleKey, setOpenedModuleKey] = useState<string | null>(null);
  useEffect(() => {
    const handler = (event: Event) => {
      const label = (event as CustomEvent<string>).detail;
      const index = coreTabs.findIndex((tab) => tab.label === label);
      if (index >= 0) { setSelectedTab(index); setOpenedModuleKey(null); window.scrollTo({ top: 0, behavior: "smooth" }); }
    };
    window.addEventListener("petroedge:navigate", handler);
    return () => window.removeEventListener("petroedge:navigate", handler);
  }, []);

  const coreTabs: CoreTab[] = useMemo(() => [
    { label: "AI Workspace", icon: <FolderKanban size={17}/>, panel: <AiWorkspaceOverview/> },
    { label: "Agents", icon: <Bot size={17}/>, panel: <AgentsPanel/> },
    { label: "Workflows", icon: <GitBranch size={17}/>, panel: <WorkflowsPanel/> },
    { label: "Digital Twins", icon: <Network size={17}/>, panel: <TwinsPanel/> },
    { label: "Rules", icon: <ShieldCheck size={17}/>, panel: <RulesPanel/> },
    { label: "Events", icon: <Radio size={17}/>, panel: <EventsPanel/> },
    { label: "Reports", icon: <ScrollText size={17}/>, panel: <ReportsPanel/> },
    { label: "Edge", icon: <Activity size={17}/>, panel: <EdgePanel/> },
    { label: "Plugins", icon: <Plug size={17}/>, panel: <PluginsPanel/> },
    { label: "System Health", icon: <HeartPulse size={17}/>, panel: <MonitoringPanel/> },
    { label: "Reservoir Intelligence", icon: <Gauge size={17}/>, panel: <ReservoirIntelligencePanel/> },
    { label: "Interactive Logs", icon: <Waypoints size={17}/>, panel: <WellLogPlotlyPanel/> },
    { label: "Assets", icon: <BriefcaseBusiness size={17}/>, panel: <AssetManagementPanel/> },
    { label: "Datasets", icon: <DatabaseZap size={17}/>, panel: <DatasetRegistryPanel/> },
    { label: "Training", icon: <BrainCircuit size={17}/>, panel: <TrainingWorkspacePanel/> },
    { label: "Experiments", icon: <FlaskConical size={17}/>, panel: <ExperimentManagerPanel/> },
    { label: "LAS Wizard", icon: <UploadCloud size={17}/>, panel: <LasWizardPanel/> },
    { label: "Digital Replay", icon: <PlayCircle size={17}/>, panel: <DigitalReplayPanel/> },
    { label: "AI Assistant", icon: <Bot size={17}/>, panel: <AiAssistantPanel/> },
    { label: "Demo Mode", icon: <Presentation size={17}/>, panel: <DemoModePanel/> },
    { label: "Intelligence Modules", icon: <Boxes size={17}/>, panel: <ModuleHub modules={builtInModules} onOpen={(key) => setOpenedModuleKey(key)}/> },
    { label: "Operations", icon: <Activity size={17}/>, panel: <OverviewPanel/> },
    { label: "Well logs", icon: <Waypoints size={17}/>, panel: <WellLogViewer/> },
    { label: "Alerts", icon: <Bell size={17}/>, panel: <AlertsPanel/> },
    { label: "Models", icon: <DatabaseZap size={17}/>, panel: <ModelMonitoringPanel/> },
    { label: "Model Evaluation", icon: <Gauge size={17}/>, panel: <ModelEvaluationPanel/> },
    { label: "Jobs", icon: <BriefcaseBusiness size={17}/>, panel: <JobsPanel/> },
    { label: "Live events", icon: <Radio size={17}/>, panel: <RealtimeEventFeed/> },
  ], []);

  const openedModule = openedModuleKey ? builtInModules.find((module) => module.key === openedModuleKey) : undefined;
  const ActiveModule = openedModule?.component;
  const visiblePanel = openedModule && ActiveModule
    ? <Box><Button sx={{ mb: 2 }} onClick={() => setOpenedModuleKey(null)}>Back to all modules</Button><ActiveModule/></Box>
    : coreTabs[selectedTab]?.panel;
  const activeLabel = openedModule?.name ?? coreTabs[selectedTab]?.label ?? "Module";

  return <Box minHeight="100vh">
    <AppBar position="sticky" elevation={0} color="inherit" sx={{ backdropFilter: "blur(16px)", bgcolor: mode==="dark"?"rgba(7,20,23,.94)":"rgba(255,255,255,.92)" }}>
      <Toolbar sx={{ gap: 1.5, borderBottom: 1, borderColor: "divider", minHeight: 70 }}>
        <Box component="img" src="/petroedge-logo.png" alt="PetroEdge AI" sx={{ width:58,height:42,objectFit:"cover",borderRadius:1.5 }}/>
        <Box flex={1}><Typography variant="h6" lineHeight={1.15}>PetroEdge AI</Typography><Typography variant="caption" color="text.secondary">Sovereign reservoir intelligence · {user.email}</Typography></Box>
        {(user.roles ?? []).slice(0, 2).map((role: string) => <Chip key={role} label={role} size="small" variant="outlined"/>)}
        <Chip label="V1.1 Modular CPU Edition" color="success" size="small"/>
        <RealtimeStatus compact/>
        <Tooltip title={`Switch to ${mode==="light"?"dark":"light"} mode`}><IconButton onClick={toggle} color="inherit" aria-label="Toggle dark mode">{mode==="light"?<Moon size={19}/>:<Sun size={19}/>}</IconButton></Tooltip>
        <Button color="inherit" startIcon={<LogOut size={17}/>} onClick={onLogout}>Logout</Button>
      </Toolbar>
      <Tabs value={selectedTab} onChange={(_event, value: number) => { setSelectedTab(value); setOpenedModuleKey(null); }} variant="scrollable" scrollButtons="auto" sx={{ px: 2, bgcolor: "background.paper", "& .MuiTab-root": { minHeight: 54, textTransform: "none", fontWeight: 650 } }}>
        {coreTabs.map((item) => <Tab key={item.label} icon={item.icon} iconPosition="start" label={item.label}/>) }
      </Tabs>
    </AppBar>
    <Container maxWidth="xl" sx={{ py: { xs: 2, md: 3.5 } }}><PanelErrorBoundary key={`${activeLabel}-${selectedTab}`} panelName={activeLabel}><Suspense fallback={<LinearProgress/>}>{visiblePanel}</Suspense></PanelErrorBoundary></Container>
  </Box>;
}
