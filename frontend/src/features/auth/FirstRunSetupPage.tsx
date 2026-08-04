import { FormEvent, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { ShieldCheck, UserPlus } from "lucide-react";

import { bootstrapAdministrator } from "../../api/client";
import { ApiError } from "../../api/http";
import type {
  AuthenticatedUser,
  BootstrapAdministratorPayload,
  LoginResponse,
} from "../../api/types";
import { persistSession } from "../../auth/session";

interface Props {
  onAuthenticated: (user: AuthenticatedUser) => void;
}

function fallbackUser(
  auth: LoginResponse,
  payload: BootstrapAdministratorPayload,
): AuthenticatedUser {
  return (
    auth.user ?? {
      email: payload.email,
      full_name: payload.full_name,
      roles: ["admin"],
      is_active: true,
    }
  );
}

function setupMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Administrator setup failed.";
}

export function FirstRunSetupPage({
  onAuthenticated,
}: Props) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    const payload: BootstrapAdministratorPayload = {
      email: email.trim().toLowerCase(),
      full_name: fullName.trim(),
      password,
      confirm_password: confirmPassword,
    };

    setLoading(true);

    try {
      const response = await bootstrapAdministrator(payload);
      persistSession(response);
      setPassword("");
      setConfirmPassword("");
      onAuthenticated(fallbackUser(response, payload));
    } catch (caught) {
      setPassword("");
      setConfirmPassword("");
      setError(setupMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box minHeight="100vh" bgcolor="background.default">
      <Container maxWidth="sm" sx={{ pt: { xs: 6, md: 10 } }}>
        <Paper
          component="form"
          autoComplete="off"
          onSubmit={submit}
          variant="outlined"
          sx={{ p: 4 }}
        >
          <Stack spacing={3}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <ShieldCheck size={30} color="#007C89" />

              <Box>
                <Typography variant="h5">
                  Create the PetroEdge administrator
                </Typography>

                <Typography variant="body2" color="text.secondary">
                  This account is created locally for this installation.
                  No default password is stored in the repository.
                </Typography>
              </Box>
            </Stack>

            {error && <Alert severity="error">{error}</Alert>}

            <TextField
              label="Administrator name"
              name="petroedge-admin-name"
              autoComplete="off"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              fullWidth
            />

            <TextField
              label="Administrator email"
              name="petroedge-admin-email-manual"
              type="email"
              autoComplete="off"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              fullWidth
            />

            <TextField
              label="Create password"
              name="petroedge-admin-password-new"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              helperText="Use at least 12 characters."
              required
              fullWidth
            />

            <TextField
              label="Confirm password"
              name="petroedge-admin-password-confirm"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) =>
                setConfirmPassword(event.target.value)
              }
              required
              fullWidth
            />

            <Button
              type="submit"
              variant="contained"
              size="large"
              startIcon={
                loading ? (
                  <CircularProgress size={18} color="inherit" />
                ) : (
                  <UserPlus size={18} />
                )
              }
              disabled={loading}
            >
              {loading ? "Creating administrator..." : "Create administrator"}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}