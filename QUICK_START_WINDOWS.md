# PetroEdge AI Demonstration Release: Windows Quick Start

Use Python 3.11, not Python 3.14.

```powershell
cd "$env:USERPROFILE\Documents\PetroEdge-AI-v1-demo"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\backend[dev,onnx,reports]"
Copy-Item .env.example .env -ErrorAction SilentlyContinue
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

In another PowerShell window:

```powershell
cd "$env:USERPROFILE\Documents\PetroEdge-AI-v1-demo\frontend"
npm install
npm run dev
```

Open:

- Frontend: `http://127.0.0.1:5173`
- API documentation: `http://127.0.0.1:8000/docs`
- Edge capabilities: `http://127.0.0.1:8000/api/v1/edge/capabilities`
