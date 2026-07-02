import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert as MuiAlert,
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Toolbar,
  Typography
} from '@mui/material';
import { Activity, Bell, DatabaseZap, LineChart, Lock, Play, ShieldCheck } from 'lucide-react';
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { analyzeSample, fetchAlerts, fetchLogs, fetchModelStatus, login, setToken } from './api/client';
import type { AnalyticsResult, WellLogSample } from './types';

function LoginPanel({ onAuthenticated }: { onAuthenticated: (roles: string[]) => void }) {
  const [username, setUsername] = useState('admin@petroedge.ai');
  const [password, setPassword] = useState('petroedge123');
  const [mfaCode, setMfaCode] = useState('123456');
  const [error, setError] = useState('');

  async function submit() {
    setError('');
    try {
      const response = await login(username, password, mfaCode);
      setToken(response.access_token);
      onAuthenticated(response.roles);
    } catch {
      setError('Authentication failed');
    }
  }

  return (
    <Box className="min-h-screen bg-[#F7F8FA]">
      <Container maxWidth="sm" className="pt-24">
        <Paper className="p-6" elevation={0} variant="outlined">
          <Stack spacing={3}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <ShieldCheck size={28} color="#007C89" />
              <Box>
                <Typography variant="h5">PetroEdge AI</Typography>
                <Typography variant="body2" color="text.secondary">
                  Secure well logging analytics console
                </Typography>
              </Box>
            </Stack>
            {error && <MuiAlert severity="error">{error}</MuiAlert>}
            <TextField label="Email" value={username} onChange={(event) => setUsername(event.target.value)} fullWidth />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              fullWidth
            />
            <TextField label="MFA code" value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} fullWidth />
            <Button variant="contained" startIcon={<Lock size={18} />} onClick={submit}>
              Sign in
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}

function KpiStrip({ latest }: { latest?: AnalyticsResult }) {
  const items = [
    ['HC probability', latest ? `${Math.round(latest.hydrocarbon_probability * 100)}%` : '--'],
    ['Porosity', latest ? latest.porosity.toFixed(3) : '--'],
    ['Water sat', latest ? latest.water_saturation.toFixed(3) : '--'],
    ['Permeability', latest ? `${latest.permeability_md.toFixed(1)} md` : '--'],
    ['QC score', latest ? latest.qc_score.toFixed(2) : '--']
  ];
  return (
    <Box className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {items.map(([label, value]) => (
        <Paper key={label} variant="outlined" elevation={0} className="p-4">
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="h5">{value}</Typography>
        </Paper>
      ))}
    </Box>
  );
}

function TrackViewer({ rows, analytics }: { rows: WellLogSample[]; analytics?: AnalyticsResult }) {
  const limitedRows = rows.slice(0, 42);
  return (
    <Paper variant="outlined" elevation={0} className="overflow-x-auto">
      <Box className="track-grid bg-white">
        {['Depth', 'GR', 'Resistivity', 'Density', 'Lithology', 'HC Prob'].map((header) => (
          <Box key={header} className="track-cell font-semibold text-shale">
            {header}
          </Box>
        ))}
        {limitedRows.map((row) => {
          const hc = analytics?.input.depth_m === row.depth_m ? analytics.hydrocarbon_probability : undefined;
          return [
            row.depth_m.toFixed(1),
            row.gamma_ray_api.toFixed(0),
            row.resistivity_ohmm.toFixed(1),
            row.density_gcc.toFixed(2),
            analytics?.input.depth_m === row.depth_m ? analytics.lithology : 'pending',
            hc === undefined ? '--' : `${Math.round(hc * 100)}%`
          ].map((value, index) => (
            <Box key={`${row.depth_m}-${index}`} className="track-cell">
              {value}
            </Box>
          ));
        })}
      </Box>
    </Paper>
  );
}

function Dashboard({ roles }: { roles: string[] }) {
  const [selected, setSelected] = useState<AnalyticsResult | undefined>();
  const logsQuery = useQuery({ queryKey: ['logs'], queryFn: () => fetchLogs() });
  const alertsQuery = useQuery({ queryKey: ['alerts'], queryFn: fetchAlerts });
  const modelsQuery = useQuery({ queryKey: ['models'], queryFn: fetchModelStatus });

  const rows = logsQuery.data ?? [];
  const latestSample = rows[Math.min(20, Math.max(rows.length - 1, 0))];

  async function runAnalysis(sample?: WellLogSample) {
    if (!sample) return;
    const result = await analyzeSample(sample);
    setSelected(result);
  }

  const crossplot = useMemo(
    () =>
      rows.map((row) => ({
        gr: row.gamma_ray_api,
        resistivity: row.resistivity_ohmm,
        density: row.density_gcc,
        depth: row.depth_m
      })),
    [rows]
  );

  return (
    <Box>
      <AppBar position="sticky" elevation={0} color="inherit" className="border-b border-gray-200">
        <Toolbar className="gap-3">
          <DatabaseZap size={24} color="#007C89" />
          <Typography variant="h6" className="flex-1">
            PetroEdge AI
          </Typography>
          {roles.map((role) => (
            <Chip key={role} label={role} size="small" />
          ))}
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" className="py-6">
        <Stack spacing={3}>
          <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" gap={2}>
            <Box>
              <Typography variant="h5">Real-time well logging analytics</Typography>
              <Typography variant="body2" color="text.secondary">
                PETROEDGE-DEMO-01 | Niger Delta Demo Field
              </Typography>
            </Box>
            <Button variant="contained" startIcon={<Play size={18} />} onClick={() => runAnalysis(latestSample)}>
              Analyze current depth
            </Button>
          </Stack>

          {(logsQuery.isLoading || alertsQuery.isLoading || modelsQuery.isLoading) && <LinearProgress />}
          <KpiStrip latest={selected} />

          <Box className="grid gap-3 lg:grid-cols-[1.25fr_0.75fr]">
            <Paper variant="outlined" elevation={0} className="p-4">
              <Stack direction="row" alignItems="center" spacing={1} className="mb-3">
                <Activity size={18} color="#007C89" />
                <Typography variant="h6">Well log viewer</Typography>
              </Stack>
              <TrackViewer rows={rows} analytics={selected} />
            </Paper>

            <Paper variant="outlined" elevation={0} className="p-4">
              <Stack direction="row" alignItems="center" spacing={1} className="mb-3">
                <LineChart size={18} color="#007C89" />
                <Typography variant="h6">Crossplot</Typography>
              </Stack>
              <Box height={340}>
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="gr" name="GR" unit=" API" />
                    <YAxis dataKey="resistivity" name="RT" unit=" ohmm" />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                    <Scatter data={crossplot} fill="#D98E04" />
                  </ScatterChart>
                </ResponsiveContainer>
              </Box>
            </Paper>
          </Box>

          <Box className="grid gap-3 lg:grid-cols-3">
            <Paper variant="outlined" elevation={0} className="p-4 lg:col-span-2">
              <Typography variant="h6" className="mb-3">
                Correlation panel
              </Typography>
              <Box height={280}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={rows.slice(0, 120)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="depth_m" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="gamma_ray_api" stroke="#4A5568" dot={false} />
                    <Line type="monotone" dataKey="resistivity_ohmm" stroke="#1E9A5A" dot={false} />
                    <Line type="monotone" dataKey="density_gcc" stroke="#007C89" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </Box>
            </Paper>

            <Paper variant="outlined" elevation={0} className="p-4">
              <Stack direction="row" alignItems="center" spacing={1} className="mb-2">
                <Bell size={18} color="#D98E04" />
                <Typography variant="h6">Alert center</Typography>
              </Stack>
              <Stack divider={<Divider flexItem />} spacing={1}>
                {(alertsQuery.data ?? []).map((alert) => (
                  <Box key={alert.id} className="py-2">
                    <Chip label={alert.severity} size="small" color={alert.severity === 'high' ? 'error' : 'warning'} />
                    <Typography variant="body2" className="mt-1">
                      {alert.message}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {alert.well_id}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </Paper>
          </Box>

          <Paper variant="outlined" elevation={0} className="p-4">
            <Typography variant="h6">Model monitoring and explainable AI</Typography>
            <Box className="mt-3 grid gap-3 md:grid-cols-2">
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Registered models
                </Typography>
                <Stack direction="row" gap={1} flexWrap="wrap" className="mt-2">
                  {(modelsQuery.data?.registered_models ?? []).map((model) => (
                    <Chip key={model} label={model} size="small" />
                  ))}
                </Stack>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Explanation
                </Typography>
                <Typography variant="body2" className="mt-2">
                  {selected
                    ? `${selected.explanation.primary_driver}; porosity contribution ${selected.explanation.porosity_contribution}`
                    : 'Run analysis to inspect prediction drivers.'}
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Stack>
      </Container>
    </Box>
  );
}

export default function App() {
  const [roles, setRoles] = useState<string[] | null>(null);
  if (!roles) return <LoginPanel onAuthenticated={setRoles} />;
  return <Dashboard roles={roles} />;
}

