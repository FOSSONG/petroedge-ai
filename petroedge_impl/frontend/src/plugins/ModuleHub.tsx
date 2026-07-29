import { Box, Button, Chip, Paper, Stack, Typography } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { ArrowRight, Boxes, Cpu } from "lucide-react";
import type { ModuleDefinition } from "./types";

export function ModuleHub({ modules, onOpen }: { modules: ModuleDefinition[]; onOpen: (key: string) => void }) {
  const theme=useTheme();
  return <Stack spacing={3}>
    <Paper variant="outlined" sx={{ p: { xs: 2.5, md: 4 }, background: theme.palette.mode==="dark"?"linear-gradient(135deg,#0A3036,#0C5862)":"linear-gradient(135deg,#102a43,#176b74)", color: "#fff", opacity:1, borderColor:alpha("#fff",.28), boxShadow:"0 18px 48px rgba(3,44,51,.22)" }}>
      <Stack direction="row" spacing={1.5} alignItems="center"><Boxes size={28}/><Box><Typography variant="h4" sx={{ color: "#fff", opacity:1 }}>PetroEdge Intelligence Modules</Typography><Typography sx={{ color: "rgba(255,255,255,.94)", opacity:1 }}>Fourteen built-in capabilities, lazy-loaded only when opened.</Typography></Box></Stack>
    </Paper>
    <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "repeat(2,1fr)", xl: "repeat(3,1fr)" }} gap={2}>
      {modules.map((module) => <Paper key={module.key} variant="outlined" className="module-card" sx={{ p: 2.5, display: "flex", flexDirection: "column", minHeight: 235, bgcolor:"background.paper", opacity:1, color:"text.primary", borderColor:"divider", boxShadow:theme.palette.mode==="dark"?"0 10px 28px rgba(0,0,0,.24)":"0 8px 24px rgba(16,44,49,.09)", "&:hover":{borderColor:"primary.main",transform:"translateY(-2px)"}, transition:"transform .18s ease,border-color .18s ease" }}>
        <Stack direction="row" justifyContent="space-between" spacing={1}><Box sx={{color:"primary.main"}}>{module.icon}</Box><Chip size="small" icon={<Cpu size={14}/>} label={module.resourceClass} variant="outlined"/></Stack>
        <Typography variant="h6" sx={{ mt: 1.5, color:"text.primary" }}>{module.name}</Typography>
        <Typography sx={{ mt: .75, flex: 1, color:"text.secondary" }}>{module.description}</Typography>
        <Typography variant="caption" sx={{ mt: 1.5, color:"text.secondary" }}>{module.capabilities.slice(0,3).join(" • ")}</Typography>
        <Button variant="outlined" sx={{ mt: 1.5, alignSelf: "flex-start" }} endIcon={<ArrowRight size={16}/>} onClick={() => onOpen(module.key)}>Open module</Button>
      </Paper>)}
    </Box>
  </Stack>;
}
