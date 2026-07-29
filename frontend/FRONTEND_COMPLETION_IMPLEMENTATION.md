# PetroEdge AI frontend completion

This frontend package extends the existing Vite/React application without replacing the working authentication, real-time, well-log, AI workspace, dataset, training, experiment, alert, model or job modules.

## Added backend-facing workspaces

- Agents
- Workflows
- Digital twins
- Rules
- Events
- Reports
- Edge runtime
- Plugins
- System health

The new workspaces use the existing authenticated `apiRequest` client, React Query cache, Material UI theme and lazy-loaded dashboard architecture.

## Compatibility behaviour

- List responses may be returned directly or wrapped in `items`, `results`, `data`, or a resource-specific collection key.
- Resource cards tolerate additional backend fields without requiring a frontend rebuild.
- Action dialogs expose the relative API endpoint and JSON payload so the live OpenAPI contract can be used without changing source code when an operation name differs between backend revisions.
- API failures are shown in-panel and do not crash the dashboard.

## Installation

From the project root in PowerShell:

```powershell
Copy-Item .\frontend\.env.example .\frontend\.env -ErrorAction SilentlyContinue
Set-Location .\frontend
npm install
npm run build
npm run test -- --run
npm run dev
```

Recommended `.env` value:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

The backend must be running on port 8000 before login and live integration testing.

## Validation completed

- TypeScript strict compilation passed with `tsc`.
- The added operations modules and modified dashboard passed ESLint with zero warnings.
- Full Vite bundling could not be executed in the Linux validation container because the uploaded `node_modules` contains Windows-native Rolldown bindings. Running `npm install` on the target Windows machine installs the correct native binding.
