# KORA Frontend

React + TypeScript + Vite. Architecture, milestones and progress: [`docs/implementation/FRONTEND_ROADMAP.md`](docs/implementation/FRONTEND_ROADMAP.md) and [`docs/implementation/frontend_PROJECT_STATE.md`](docs/implementation/frontend_PROJECT_STATE.md).

Run all commands from `frontend/`.

```bash
npm install
npm run dev        # http://localhost:5173 — proxies /api to the backend
npm run check      # lint + typecheck + tests + production build (must pass before a milestone is done)
npm test           # vitest only
```

## Backend

The backend has no CORS and uses `Secure` cookies, so the app talks to `/api/v1/...` **same-origin**. In dev, Vite proxies `/api` to `http://127.0.0.1:8000` (override with `KORA_API_URL`). Start the backend from `backend/` (`uv run uvicorn kora_api.main:app --reload`), then open the app on **`http://localhost:5173`** (use `localhost`, not a LAN IP, so the browser accepts `Secure` cookies over HTTP).

## Layout

`src/app` (providers, router, shell) · `src/features/<feature>` (api + UI per feature) · `src/shared` (http client, i18n, ui, brand assets). Import with the `@/` alias.
