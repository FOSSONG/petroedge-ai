# PetroEdge Frontend Functionality Patch

This patch replaces placeholder presentation with API-backed workflows.

## Implemented

- Vitest configured with jsdom so React Testing Library has `document` and `window`.
- Removed the static RealtimeEventFeed barrel export that conflicted with lazy loading.
- Agents now select and consume an uploaded PetroEdge dataset instead of static JSON.
- Workflows now select an uploaded dataset, display registered nodes, call `/workflows/{id}/run`, and show the execution result.
- Plugin catalogue now explains built-in modules, status, resource class and capability boundaries.
- System Health now renders readable status cards instead of raw JSON.
- Reservoir Intelligence and Interactive Logs now calculate robust data-dependent axis ranges using the 2nd to 98th percentile plus padding.
- Intelligence Module cards are fully opaque. Modules with implemented services open their real workspaces: AI Control Centre, Multi-Agent, Workflow, Governance, Monitoring, Digital Twin and Research Hub.
- Remaining intelligence modules bind to uploaded datasets and show live dataset context rather than a faint static placeholder.

## Apply

Copy the contents of `frontend` over the existing project frontend, preserving the local `.env` file. Then run:

```powershell
Set-Location .\frontend
Remove-Item .\node_modules -Recurse -Force -ErrorAction SilentlyContinue
npm install
npm run build
npm run test -- --run
npm run dev
```
