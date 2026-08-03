import { Alert, Box, Chip, Paper, Stack, Typography } from "@mui/material";
import { CheckCircle2, Cpu, Layers3 } from "lucide-react";

interface Props {
  title: string;
  description: string;
  resourceClass: "light" | "medium" | "heavy";
  capabilities: string[];
}

export function CapabilityModulePanel({ title, description, resourceClass, capabilities }: Props) {
  return (
    <Stack spacing={2.5}>
      <Paper variant="outlined" sx={{ p: { xs: 2.5, md: 4 }, background: "linear-gradient(135deg,#073b4c,#0b6e75)", color: "white" }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between">
          <Box>
            <Stack direction="row" spacing={1} alignItems="center"><Layers3 size={22}/><Typography variant="overline" sx={{ color: "inherit" }}>Built-in lazy module</Typography></Stack>
            <Typography variant="h4" sx={{ mt: 1, color: "inherit" }}>{title}</Typography>
            <Typography sx={{ mt: 1, maxWidth: 820, color: "rgba(255,255,255,.9)" }}>{description}</Typography>
          </Box>
          <Chip icon={<Cpu size={16}/>} label={`${resourceClass} resource class`} sx={{ alignSelf: "flex-start", bgcolor: "rgba(255,255,255,.14)", color: "white" }}/>
        </Stack>
      </Paper>

      <Alert severity="info">This module is loaded only when opened. Its capability boundary is registered now; domain engines are connected incrementally without increasing core startup cost.</Alert>

      <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "repeat(2,1fr)", lg: "repeat(3,1fr)" }} gap={2}>
        {capabilities.map((capability) => (
          <Paper key={capability} variant="outlined" sx={{ p: 2.25 }}>
            <Stack direction="row" spacing={1.25} alignItems="center"><CheckCircle2 size={18}/><Typography fontWeight={700}>{capability}</Typography></Stack>
          </Paper>
        ))}
      </Box>
    </Stack>
  );
}
