PetroEdge AI Release 3 repair package

Run this script from any folder:
  Set-ExecutionPolicy -Scope Process Bypass
  .\REPAIR-PETROEDGE-RELEASE-3.ps1

It:
- removes the invalid standalone platformApi.release3.addition.ts file
- avoids all self-copy operations
- validates backend Python before rebuilding
- rebuilds backend and frontend
- waits for actual backend and frontend HTTP readiness
- verifies the Release 3 OpenAPI routes
- captures logs and rolls back safely if a failure occurs
