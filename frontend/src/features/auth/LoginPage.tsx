import {
  normaliseRoles,
} from "../../api/typeGuards";
import {
  FormEvent,
  useState,
} from "react";

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

import {
  Lock,
  ShieldCheck,
} from "lucide-react";

import {
  fetchCurrentUser,
  login,
} from "../../api/client";
import { ApiError } from "../../api/http";
import type {
  AuthenticatedUser,
  LoginResponse,
} from "../../api/types";
import { persistSession } from "../../auth/session";

interface Props {
  onAuthenticated: (
    user: AuthenticatedUser,
  ) => void;
}

function authenticationMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return (
        "Cannot reach the PetroEdge API. " +
        "Confirm that FastAPI is running on port 8000."
      );
    }

    if (error.status === 401) {
      return "The email or password is incorrect.";
    }

    if (error.status === 403) {
      return (
        "This account is inactive or is not authorised " +
        "to access PetroEdge."
      );
    }

    if (error.status === 422) {
      return "The API rejected the login request format.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Authentication failed because of an unexpected error.";
}

function fallbackUser(
  auth: LoginResponse,
  email: string,
): AuthenticatedUser {
  return (
    auth.user ?? {
      email,
      roles: normaliseRoles(auth.roles),
      is_active: true,
    }
  );
}

export function LoginPage({
  onAuthenticated,
}: Props) {
  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  const [mfa, setMfa] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const normalisedEmail =
      email.trim().toLowerCase();

    setError("");
    setLoading(true);

    try {
      const auth = await login(
        normalisedEmail,
        password,
        mfa.trim() || undefined,
      );

      persistSession(auth);

      let authenticatedUser: AuthenticatedUser;

      try {
        authenticatedUser =
          await fetchCurrentUser() as AuthenticatedUser;
      } catch {
        authenticatedUser =
          fallbackUser(auth, normalisedEmail);
      }

      onAuthenticated(authenticatedUser);
    } catch (caught) {
      setError(authenticationMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box
      minHeight="100vh"
      bgcolor="background.default"
    >
      <Container
        maxWidth="sm"
        sx={{ pt: { xs: 8, md: 12 } }}
      >
        <Paper
          component="form"
          onSubmit={submit}
          variant="outlined"
          sx={{ p: 4 }}
        >
          <Stack spacing={3}>
            <Stack
              direction="row"
              spacing={1.5}
              alignItems="center"
            >
              <ShieldCheck
                size={30}
                color="#007C89"
              />

              <Box>
                <Typography variant="h5">
                  PetroEdge AI
                </Typography>

                <Typography
                  variant="body2"
                  color="text.secondary"
                >
                  Secure well-logging analytics console
                </Typography>
              </Box>
            </Stack>

            {error && (
              <Alert severity="error">
                {error}
              </Alert>
            )}

            <TextField
              label="Email"
              type="email"
              name="petroedge-login-email-manual"
              autoComplete="off"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              required
              fullWidth
            />

            <TextField
              label="Password"
              type="password"
              name="petroedge-login-password-manual"
              autoComplete="new-password"
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              required
              fullWidth
            />

            <TextField
              label="MFA code"
              value={mfa}
              onChange={(event) =>
                setMfa(event.target.value)
              }
              inputProps={{
                inputMode: "numeric",
                maxLength: 8,
              }}
              helperText={
                "Leave blank unless MFA is enabled."
              }
              fullWidth
            />

            <Button
              type="submit"
              variant="contained"
              size="large"
              startIcon={
                loading ? (
                  <CircularProgress
                    size={18}
                    color="inherit"
                  />
                ) : (
                  <Lock size={18} />
                )
              }
              disabled={loading}
            >
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
