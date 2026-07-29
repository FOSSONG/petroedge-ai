# GitHub Codespaces Development

This path runs PetroEdge AI in GitHub's Linux cloud development environment, bypassing local WSL and Docker Desktop problems.

## 1. Put The Project On GitHub

From the project root:

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026"
git init
git add .
git commit -m "Initial PetroEdge AI platform"
```

Create an empty repository on GitHub, then push:

```powershell
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/petroedge-ai.git
git branch -M main
git push -u origin main
```

GitHub usernames cannot contain spaces. Use the username from your GitHub profile URL, not your display name. For example, if your profile is `https://github.com/guiliannofossong`, use:

```powershell
git remote add origin https://github.com/guiliannofossong/petroedge-ai.git
```

If you already tried to add a bad remote, remove it first:

```powershell
git remote remove origin
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/petroedge-ai.git
```

If Git complains about repository ownership on this machine:

```powershell
git config --global --add safe.directory "C:/Users/GUILIANNO FOSSONG/Documents/NCDMB PROJECT 2026"
```

## 2. Create The Codespace

1. Open the repository on GitHub.
2. Click `Code`.
3. Open the `Codespaces` tab.
4. Click `Create codespace on main`.

GitHub will use `.devcontainer/devcontainer.json` to create a Linux environment with Python 3.11 and Node.js 20.

## 3. Wait For Setup

The `postCreateCommand` installs backend and frontend dependencies:

```bash
python -m pip install -r backend/requirements-windows-dev.txt
cd frontend && npm install
```

If setup fails or you rebuild the container, run those commands manually in the Codespaces terminal.

## 4. Start The Backend

Open a terminal in Codespaces:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

GitHub will forward port `8000`.

API docs:

```text
https://YOUR-CODESPACE-8000.app.github.dev/docs
```

## 5. Start The Frontend

Open a second terminal:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

GitHub will forward port `5173`. Open the forwarded frontend URL from the Ports tab.

Demo login:

- Email: `admin@petroedge.ai`
- Password: `petroedge123`
- MFA code: `123456`

## 6. Run Tests

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm test -- --run
```

## 7. Optional: Full Docker Stack In Codespaces

Codespaces runs on Linux, so it can often run Docker without your local WSL. If you want the full PostgreSQL, TimescaleDB, Redis, Kafka, MLflow, backend, and frontend stack:

```bash
cp .env.example .env
docker compose up --build
```

Forwarded ports:

- `3000` frontend when using Docker Compose
- `8000` backend API
- `5000` MLflow
- `5432` PostgreSQL
- `6379` Redis

If the machine is too small for Kafka, TensorFlow, and MLflow together, resize the codespace to a larger machine or use the native Codespaces run commands above.

## 8. Save Your Work

Commit and push from Codespaces:

```bash
git status
git add .
git commit -m "Update PetroEdge AI"
git push
```

Stop the codespace when done to avoid unnecessary usage.
