import { Component, type ErrorInfo, type ReactNode } from "react";
import { Alert, Button, Paper, Stack, Typography } from "@mui/material";

interface Props { children: ReactNode; panelName?: string; }
interface State { error: Error | null; }

export class PanelErrorBoundary extends Component<Props, State> {
  state: State = { error: null };
  static getDerivedStateFromError(error: Error): State { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[PetroEdge] ${this.props.panelName ?? "Panel"} failed`, error, info.componentStack);
  }
  private reset = () => this.setState({ error: null });
  render() {
    if (!this.state.error) return this.props.children;
    return <Paper variant="outlined" sx={{ p: 3 }}>
      <Stack spacing={2}>
        <Alert severity="error">{this.props.panelName ?? "This module"} could not be rendered.</Alert>
        <Typography variant="body2" color="text.secondary">{this.state.error.message || "An unexpected interface error occurred."}</Typography>
        <Button variant="contained" onClick={this.reset} sx={{ alignSelf: "flex-start" }}>Retry module</Button>
      </Stack>
    </Paper>;
  }
}
