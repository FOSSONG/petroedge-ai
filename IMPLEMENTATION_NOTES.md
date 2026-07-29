# PetroEdge professional UX implementation

This release implements the requested fixes:

- Edge temporal inference now builds its feature matrix from the selected uploaded dataset. No JSON input is exposed.
- Workflow execution sends actual preview rows to the backend and renders QC, petrophysics, agent consensus and report stages as engineering cards.
- Workflow refresh refetches workflows, datasets and dataset preview records.
- Confidence values are rendered as percentages.
- The AI Assistant derives displayed asset names from registered wells or uploaded datasets. No GABO well names are hard-coded.
- Plugin catalogue cards link enabled backend modules to their corresponding frontend workspaces.
- Reservoir Intelligence uses one synchronised, industry-style depth axis across tracks: increasing downward, rounded major depth ticks, and a shared calibrated depth range.
- PetroEdge browser favicon and touch icon assets are included.
- Assets now have a delete action with confirmation.
- Backend adds `DELETE /api/v1/wells/{well_id}` with RBAC, 404/409 handling and event emission.
- Existing report download uses an authenticated Blob download through `/reports/{report_id}/download?format=pdf`.

## Apply

Back up the project, then copy `backend` and `frontend` from this release over the existing folders. Preserve the existing frontend `.env`.

```powershell
Set-Location "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-v1-demo\frontend"
Remove-Item .\node_modules -Recurse -Force -ErrorAction SilentlyContinue
npm install
npm run build
npm run test -- --run
```

Run migrations and backend tests from the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m alembic -c backend\alembic.ini upgrade head
python -m pytest backend\tests -q
```
