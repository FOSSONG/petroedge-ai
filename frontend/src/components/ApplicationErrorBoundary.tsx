import { Component, type ErrorInfo, type ReactNode } from "react";
import { Alert, Box, Button, Paper, Stack, Typography } from "@mui/material";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ApplicationErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("PetroEdge frontend failure", {
      error,
      componentStack: info.componentStack,
    });
  }

  private reload = (): void => {
    window.location.reload();
  };

  private clearTemporaryState = (): void => {
    sessionStorage.removeItem("petroedge:lazy-reload-attempted");
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <Box minHeight="100vh" display="grid" sx={{ placeItems: "center", p: 3 }}>
        <Paper variant="outlined" sx={{ width: "min(680px, 100%)", p: 3 }}>
          <Stack spacing={2}>
            <Typography variant="h5">
              PetroEdge could not render this view
            </Typography>

            <Alert severity="error">
              {this.state.error.message || "An unexpected frontend error occurred."}
            </Alert>

            <Typography color="text.secondary">
              Your datasets and models remain stored in the backend.
            </Typography>

            <Stack direction={{ xs: "column", sm: "row" }} gap={1}>
              <Button variant="contained" onClick={this.reload}>
                Reload interface
              </Button>

              <Button variant="outlined" onClick={this.clearTemporaryState}>
                Clear temporary UI state
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Box>
    );
  }
}