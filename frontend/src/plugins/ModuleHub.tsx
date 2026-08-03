import { Box, Button, Chip, Paper, Stack, Typography } from "@mui/material";
import { ArrowRight, Boxes, Cpu } from "lucide-react";
import type { ModuleDefinition } from "./types";

export function ModuleHub({ modules, onOpen }: { modules: ModuleDefinition[]; onOpen: (key: string) => void }) {
  return <Stack spacing={3}>
    <Paper className="module-hero" variant="outlined" sx={{ p: { xs: 2.5, md: 4 } }}>
      <Stack direction="row" spacing={1.5} alignItems="center"><Boxes size={28}/><Box><Typography variant="h4" sx={{ color: "inherit" }}>PetroEdge Intelligence Modules</Typography><Typography sx={{ color: "rgba(255,255,255,.88)" }}>Fourteen built-in capabilities, lazy-loaded only when opened.</Typography></Box></Stack>
    </Paper>
    <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "repeat(2,1fr)", xl: "repeat(3,1fr)" }} gap={2}>
      {modules.map((module) => <Paper key={module.key} variant="outlined" sx={{ p: 2.5, display: "flex", flexDirection: "column", minHeight: 235, bgcolor: "background.paper", color: "text.primary", borderColor: "divider", boxShadow: 1 }}>
        <Stack direction="row" justifyContent="space-between" spacing={1}><Box>{module.icon}</Box><Chip size="small" icon={<Cpu size={14}/>} label={module.resourceClass}/></Stack>
        <Typography variant="h6" sx={{ mt: 1.5 }}>{module.name}</Typography>
        <Typography color="text.secondary" sx={{ mt: .75, flex: 1 }}>{module.description}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5 }}>{module.capabilities.slice(0,3).join(" • ")}</Typography>
        <Button sx={{ mt: 1.5, alignSelf: "flex-start" }} endIcon={<ArrowRight size={16}/>} onClick={() => onOpen(module.key)}>Open module</Button>
      </Paper>)}
    </Box>
  </Stack>;
}
