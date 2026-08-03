import { Suspense, useEffect, useMemo, useState } from "react";
import {
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  Tab,
  Tabs,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Activity,
  Bell,
  Bot,
  Boxes,
  BrainCircuit,
  BriefcaseBusiness,
  ChevronDown,
  CloudCog,
  Cpu,
  DatabaseZap,
  FlaskConical,
  FolderKanban,
  Gauge,
  LogOut,
  Orbit,
  Moon,
  PlayCircle,
  Presentation,
  Radio,
  Sun,
  UploadCloud,
  Users,
  Waypoints,
  Workflow,
} from "lucide-react";
import type { AuthenticatedUser } from "../../api/types";
import { RealtimeStatus } from "../../realtime";
import { ModuleHub } from "../../plugins/ModuleHub";
import { builtInModules } from "../../plugins/registry";
import { PanelErrorBoundary } from "../../components/PanelErrorBoundary";
import { usePetroEdgeTheme } from "../../theme";
import { lazyWithRetry } from "../../utils/lazyWithRetry";

const AiWorkflowsPanel = lazyWithRetry(() => import("../platform/AiWorkflowsPanel").then((m) => ({ default: m.AiWorkflowsPanel })));
const ReservoirIntelligencePanel = lazyWithRetry(() => import("../platform/ReservoirIntelligencePanel").then((m) => ({ default: m.ReservoirIntelligencePanel })));
const DatasetRegistryPanel = lazyWithRetry(() => import("../platform/DatasetRegistryPanel").then((m) => ({ default: m.DatasetRegistryPanel })));
const TrainingWorkspacePanel = lazyWithRetry(() => import("../platform/TrainingWorkspacePanel").then((m) => ({ default: m.TrainingWorkspacePanel })));
const ExperimentManagerPanel = lazyWithRetry(() => import("../platform/ExperimentManagerPanel").then((m) => ({ default: m.ExperimentManagerPanel })));
const DemoModePanel = lazyWithRetry(() => import("../platform/DemoModePanel").then((m) => ({ default: m.DemoModePanel })));
const OverviewPanel = lazyWithRetry(() => import("./OverviewPanel").then((m) => ({ default: m.OverviewPanel })));
const WellLogViewer = lazyWithRetry(() => import("../welllogs/WellLogViewer").then((m) => ({ default: m.WellLogViewer })));
const AlertsPanel = lazyWithRetry(() => import("../alerts/AlertsPanel").then((m) => ({ default: m.AlertsPanel })));
const ModelMonitoringPanel = lazyWithRetry(() => import("../models/ModelMonitoringPanel").then((m) => ({ default: m.ModelMonitoringPanel })));
const JobsPanel = lazyWithRetry(() => import("../jobs/JobsPanel").then((m) => ({ default: m.JobsPanel })));
const RealtimeEventFeed = lazyWithRetry(() => import("../../realtime/RealtimeEventFeed").then((m) => ({ default: m.RealtimeEventFeed })));
const WellLogPlotlyPanel = lazyWithRetry(() => import("../platform/WellLogPlotlyPanel").then((m) => ({ default: m.WellLogPlotlyPanel })));
const LasWizardPanel = lazyWithRetry(() => import("../platform/LasWizardPanel").then((m) => ({ default: m.LasWizardPanel })));
const DigitalReplayPanel = lazyWithRetry(() => import("../platform/DigitalReplayPanel").then((m) => ({ default: m.DigitalReplayPanel })));
const ReservoirDigitalTwinPanel = lazyWithRetry(() => import("../platform/ReservoirDigitalTwinPanel").then((m) => ({ default: m.ReservoirDigitalTwinPanel })));
const AiAssistantPanel = lazyWithRetry(() => import("../platform/AiAssistantPanel").then((m) => ({ default: m.AiAssistantPanel })));
const AssetManagementPanel = lazyWithRetry(() => import("../platform/AssetManagementPanel").then((m) => ({ default: m.AssetManagementPanel })));
const EdgeComputingPanel = lazyWithRetry(() => import("../platform/EdgeComputingPanel").then((m) => ({ default: m.EdgeComputingPanel })));
const ModelEvaluationPanel = lazyWithRetry(() => import("../platform/ModelEvaluationPanel").then((m) => ({ default: m.ModelEvaluationPanel })));
const AiAgentsPanel = lazyWithRetry(() => import("../platform/AiAgentsPanel").then((m) => ({ default: m.AiAgentsPanel })));
const CcusWorkspacePanel = lazyWithRetry(() => import("../platform/CcusWorkspacePanel").then((m) => ({ default: m.CcusWorkspacePanel })));

interface Props {
  user: AuthenticatedUser;
  onLogout: () => void;
}

type CoreTab = { label: string; icon: JSX.Element; panel: JSX.Element };
type OperationsKey = "Operations" | "Models" | "Alerts" | "Jobs" | "Live Events";

const operationsPanels: Record<OperationsKey, JSX.Element> = {
  Operations: <OverviewPanel />,
  Models: <ModelMonitoringPanel />,
  Alerts: <AlertsPanel />,
  Jobs: <JobsPanel />,
  "Live Events": <RealtimeEventFeed />,
};

const operationsIcons: Record<OperationsKey, JSX.Element> = {
  Operations: <Activity size={17} />,
  Models: <DatabaseZap size={17} />,
  Alerts: <Bell size={17} />,
  Jobs: <BriefcaseBusiness size={17} />,
  "Live Events": <Radio size={17} />,
};

export function DashboardPage({ user, onLogout }: Props) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [operationsView, setOperationsView] = useState<OperationsKey>("Operations");
  const [operationsAnchor, setOperationsAnchor] = useState<HTMLElement | null>(null);
  const { mode, toggleMode } = usePetroEdgeTheme();
  const [openedModuleKey, setOpenedModuleKey] = useState<string | null>(null);

  const coreTabs: CoreTab[] = useMemo(() => [
    { label: "AI Workflows", icon: <Workflow size={17} />, panel: <AiWorkflowsPanel /> },
    { label: "Edge Computing", icon: <Cpu size={17} />, panel: <EdgeComputingPanel /> },
    { label: "Datasets", icon: <DatabaseZap size={17} />, panel: <DatasetRegistryPanel /> },
    { label: "LAS Wizard", icon: <UploadCloud size={17} />, panel: <LasWizardPanel /> },
    { label: "Training", icon: <BrainCircuit size={17} />, panel: <TrainingWorkspacePanel /> },
    { label: "Reservoir Intelligence", icon: <Gauge size={17} />, panel: <ReservoirIntelligencePanel /> },
    { label: "Interactive Logs", icon: <Waypoints size={17} />, panel: <WellLogPlotlyPanel /> },
    { label: "Well Logs", icon: <Waypoints size={17} />, panel: <WellLogViewer /> },
    { label: "CCUS", icon: <CloudCog size={17} />, panel: <CcusWorkspacePanel /> },
    { label: "AI Agents", icon: <Users size={17} />, panel: <AiAgentsPanel /> },
    { label: "Assets", icon: <BriefcaseBusiness size={17} />, panel: <AssetManagementPanel /> },
    { label: "Experiments", icon: <FlaskConical size={17} />, panel: <ExperimentManagerPanel /> },
    { label: "Model Evaluation", icon: <Gauge size={17} />, panel: <ModelEvaluationPanel /> },
    { label: "AI Assistant", icon: <Bot size={17} />, panel: <AiAssistantPanel /> },
    { label: "Digital Twin", icon: <Orbit size={17} />, panel: <ReservoirDigitalTwinPanel /> },
    { label: "Digital Replay", icon: <PlayCircle size={17} />, panel: <DigitalReplayPanel /> },
    { label: "Demo Mode", icon: <Presentation size={17} />, panel: <DemoModePanel /> },
    { label: "System Operations", icon: <Activity size={17} />, panel: operationsPanels[operationsView] },
    {
      label: "Intelligence Modules",
      icon: <Boxes size={17} />,
      panel: (
        <ModuleHub
          modules={builtInModules}
          onOpen={(key) => {
            const routes: Record<string, string> = {
              "multi-agent": "AI Agents",
              governance: "Model Evaluation",
              monitoring: "Edge Computing",
              "digital-twin": "Digital Twin",
              "research-hub": "Experiments",
              "ai-control-centre": "AI Workflows",
            };
            const tab = routes[key];
            if (tab) {
              window.dispatchEvent(new CustomEvent("petroedge:navigate", { detail: { tab } }));
              return;
            }
            setOpenedModuleKey(key);
          }}
        />
      ),
    },
  ], [operationsView]);

  const systemOperationsIndex = coreTabs.findIndex((item) => item.label === "System Operations");

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: string }>).detail;
      if (!detail?.tab) return;

      const requested = detail.tab.toLowerCase();
      const operation = (Object.keys(operationsPanels) as OperationsKey[]).find(
        (key) => key.toLowerCase() === requested,
      );
      if (operation) {
        setOperationsView(operation);
        setSelectedTab(systemOperationsIndex);
        setOpenedModuleKey(null);
        return;
      }

      const index = coreTabs.findIndex((item) => item.label.toLowerCase() === requested);
      if (index >= 0) {
        setSelectedTab(index);
        setOpenedModuleKey(null);
      }
    };
    window.addEventListener("petroedge:navigate", handler);
    return () => window.removeEventListener("petroedge:navigate", handler);
  }, [coreTabs, systemOperationsIndex]);

  const openedModule = openedModuleKey ? builtInModules.find((module) => module.key === openedModuleKey) : undefined;
  const ActiveModule = openedModule?.component;
  const visiblePanel = openedModule && ActiveModule
    ? (
      <Box>
        <Button sx={{ mb: 2 }} onClick={() => setOpenedModuleKey(null)}>Back to all modules</Button>
        <ActiveModule />
      </Box>
    )
    : coreTabs[selectedTab]?.panel;

  const selectOperation = (operation: OperationsKey) => {
    setOperationsView(operation);
    setSelectedTab(systemOperationsIndex);
    setOpenedModuleKey(null);
    setOperationsAnchor(null);
  };

  return (
    <Box minHeight="100vh">
      <AppBar position="sticky" elevation={0} color="inherit" sx={{ backdropFilter: "blur(16px)", bgcolor: "background.paper" }}>
        <Toolbar sx={{ gap: 1.5, borderBottom: 1, borderColor: "divider", minHeight: 70 }}>
          <Box component="img" src="/petroedge-logo.png" alt="PetroEdge AI" sx={{ width: 58, height: 42, objectFit: "cover", borderRadius: 1.5 }} />
          <Box flex={1}>
            <Typography variant="h6" lineHeight={1.15}>PetroEdge AI</Typography>
            <Typography variant="caption" color="text.secondary">Sovereign reservoir intelligence · {user.email}</Typography>
          </Box>
          {(user.roles ?? []).slice(0, 2).map((role: string) => <Chip key={role} label={role} size="small" variant="outlined" />)}
          <Chip label="PetroEdge AI - Release 4.5" color="success" size="small" />
          <Tooltip title={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}>
            <IconButton color="inherit" onClick={toggleMode} aria-label="Toggle colour mode">
              {mode === "dark" ? <Sun size={19} /> : <Moon size={19} />}
            </IconButton>
          </Tooltip>
          <RealtimeStatus compact />
          <Button color="inherit" startIcon={<LogOut size={17} />} onClick={onLogout}>Logout</Button>
        </Toolbar>
        <Tabs
          value={selectedTab}
          onChange={(_event, value: number) => {
            if (value === systemOperationsIndex) return;
            setSelectedTab(value);
            setOpenedModuleKey(null);
          }}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ px: 2, bgcolor: "background.paper", "& .MuiTab-root": { minHeight: 54, textTransform: "none", fontWeight: 650 } }}
        >
          {coreTabs.map((item, index) => (
            <Tab
              key={item.label}
              icon={index === systemOperationsIndex ? operationsIcons[operationsView] : item.icon}
              iconPosition="start"
              label={index === systemOperationsIndex ? `${operationsView}` : item.label}
              onClick={index === systemOperationsIndex ? (event) => setOperationsAnchor(event.currentTarget) : undefined}
              aria-haspopup={index === systemOperationsIndex ? "menu" : undefined}
              aria-expanded={index === systemOperationsIndex ? Boolean(operationsAnchor) : undefined}
            />
          ))}
        </Tabs>
        <Menu anchorEl={operationsAnchor} open={Boolean(operationsAnchor)} onClose={() => setOperationsAnchor(null)}>
          {(Object.keys(operationsPanels) as OperationsKey[]).map((operation) => (
            <MenuItem key={operation} selected={operation === operationsView} onClick={() => selectOperation(operation)}>
              <Box component="span" sx={{ display: "inline-flex", mr: 1 }}>{operationsIcons[operation]}</Box>
              {operation}
              {operation === operationsView && <ChevronDown size={15} style={{ marginLeft: 8 }} />}
            </MenuItem>
          ))}
        </Menu>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: { xs: 2, md: 3.5 } }}>
        <PanelErrorBoundary
          key={`${selectedTab}-${operationsView}-${openedModuleKey ?? "core"}`}
          panelName={openedModule?.name ?? coreTabs[selectedTab]?.label}
        >
          <Suspense fallback={<LinearProgress />}>{visiblePanel}</Suspense>
        </PanelErrorBoundary>
      </Container>
    </Box>
  );
}
