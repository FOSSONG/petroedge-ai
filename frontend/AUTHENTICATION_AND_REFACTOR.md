# Authentication repair and frontend refactor

The old login caught every error as `Authentication failed`, hiding the real cause. The new login reports unreachable API, 401, 403 and 422 separately. It also makes MFA optional and uses the unified `petroedge_access_token` session key.

## Required checks

1. Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_WS_BASE_URL=ws://127.0.0.1:8000/api/v1
```

2. Restart Vite after editing `.env`.

3. Test the backend directly:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

$body = @{
  username   = "admin@petroedge.ai"
  password   = "petroedge123"
  grant_type = "password"
}

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/auth/login" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body $body
```

If the direct login returns 401, the frontend is not the problem. The database user or development fallback credentials do not match.

4. FastAPI CORS must allow:

```python
allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
```
