# PetroEdge frontend API and real-time integration

## Files

Copy the `src` files into the existing Vite/React frontend and copy
`.env.example` to `.env`.

## Required packages

```powershell
npm install @tanstack/react-query
```

## Query provider

Wrap the application once, normally in `src/main.tsx`:

```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./query/queryClient";

<QueryClientProvider client={queryClient}>
  <App />
</QueryClientProvider>
```

## App integration

Replace the old direct WebSocket block:

```tsx
new WebSocket("ws://localhost:8000/api/v1/stream")
```

with:

```tsx
const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);

const realtime = usePetroEdgeRealtime({
  channels: ["global", "well:PETROEDGE-DEMO-01"],
  onEvent: setLastEvent,
});
```

Import:

```tsx
import { usePetroEdgeRealtime } from "./realtime/usePetroEdgeRealtime";
import type { RealtimeEvent } from "./realtime/client";
```

The hook reconnects automatically and invalidates React Query caches for
alerts, jobs, logs and dashboard data.

## Authentication

After login, use:

```tsx
const response = await login(email, password, mfaCode);
persistSession(response);
onAuthenticated(response.roles);
```

On startup:

```tsx
const restored = restoreSession();
```

On logout:

```tsx
clearSession();
```

## Important backend compatibility

The current client expects:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/wells/{well_id}/logs`
- `GET /api/v1/alerts`
- `GET /api/v1/models`
- `POST /api/v1/analytics/sample`
- `GET /api/v1/dashboard`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `WS /api/v1/realtime/ws`

If a backend response wraps lists inside `items`, adapt the corresponding
client method once rather than modifying every component.
