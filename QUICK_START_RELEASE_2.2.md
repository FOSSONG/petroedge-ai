# Release 2.2 Windows deployment

```powershell
Set-Location "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-2.1-Real-Time-Edge"
docker compose down
```

Extract this package to:

```text
C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-2.2-Petrophysical-Edge
```

Then run:

```powershell
Set-Location "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-2.2-Petrophysical-Edge"
Copy-Item ".\backend\.env.example" ".\backend\.env" -Force
docker compose down --remove-orphans
docker compose up -d --build
docker compose ps
```

Open `http://localhost:5173`, hard-refresh with `Ctrl + Shift + R`, select **Edge Computing**, then **Rig-site replay**.
