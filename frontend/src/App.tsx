import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";

import { fetchCurrentUser } from "./api/client";
import {
  AUTH_EXPIRED_EVENT,
  getAccessToken,
} from "./api/http";
import type { AuthenticatedUser } from "./api/types";
import {
  clearSession,
  restoreSession,
} from "./auth/session";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";

import {
  RealtimeProvider,
} from "./realtime";

export default function App() {
  const [user, setUser] =
    useState<AuthenticatedUser | null>(null);

  const [checking, setChecking] =
    useState(true);

  const [startupError, setStartupError] =
    useState("");

  const endSession = useCallback(() => {
    clearSession();
    setUser(null);
    setStartupError("");
  }, []);

  useEffect(() => {
    let active = true;

    async function restoreAuthentication(): Promise<void> {
      setChecking(true);
      setStartupError("");

      const restored = restoreSession();
      const token =
        restored.token ?? getAccessToken();

      if (!token) {
        if (active) {
          setUser(null);
          setChecking(false);
        }

        return;
      }

      try {
        const currentUser =
          (await fetchCurrentUser()) as AuthenticatedUser;

        if (!active) {
          return;
        }

        if (currentUser.is_active === false) {
          clearSession();
          setUser(null);
          setStartupError(
            "This PetroEdge account is inactive.",
          );
          return;
        }

        setUser(currentUser);
      } catch {
        clearSession();

        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setChecking(false);
        }
      }
    }

    void restoreAuthentication();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function handleAuthenticationExpired(): void {
      endSession();
    }

    window.addEventListener(
      AUTH_EXPIRED_EVENT,
      handleAuthenticationExpired,
    );

    return () => {
      window.removeEventListener(
        AUTH_EXPIRED_EVENT,
        handleAuthenticationExpired,
      );
    };
  }, [endSession]);

  if (checking) {
    return (
      <Box
        minHeight="100vh"
        display="grid"
        sx={{
          placeItems: "center",
        }}
      >
        <Stack
          spacing={2}
          alignItems="center"
        >
          <CircularProgress />

          <Typography color="text.secondary">
            Verifying your PetroEdge session...
          </Typography>
        </Stack>
      </Box>
    );
  }

  if (!user) {
    return (
      <Box>
        {startupError && (
          <Box
            maxWidth={600}
            mx="auto"
            pt={3}
            px={2}
          >
            <Alert severity="warning">
              {startupError}
            </Alert>
          </Box>
        )}

        <LoginPage
          onAuthenticated={setUser}
        />
      </Box>
    );
  }

  return (
    <RealtimeProvider
      userId={
        user.id ??
        user.uid ??
        user.email
      }
      initialChannels={[
        "global",
        "alerts",
        "jobs",
        "models",
        "wells",
      ]}
    >
      <DashboardPage
        user={user}
        onLogout={endSession}
      />
    </RealtimeProvider>
  );
}