---
description: "Use when working on React components, pages, or the API service layer in frontend/."
applyTo: "frontend/**"
---

# Frontend — React 19 + Vite

## Structure

- `frontend/src/pages/` — page components (Library, PaperDetail, Dashboard, Collections, Research, Discover, History, Import, Settings, Trash)
- `frontend/src/components/` — shared components (Layout, ImportModal, CommandPalette, Toast)
- `frontend/src/services/api.js` — **all API calls go here** (centralized fetch layer)

## Patterns

- Functional React with hooks — no class components
- All API calls via `frontend/src/services/api.js` — never inline fetch in components
- Recharts for data visualization
- Lucide React for icons

## Vite Proxy

`/api` requests are proxied to the API backend. The target is configurable:
- Local bare-metal: `http://localhost:8003` (default)
- Docker Compose: set `VITE_API_URL=http://api:8003` in the frontend container env

## Hot Reload

Frontend uses Vite HMR — changes appear immediately at http://localhost:5173 without restart.

## After Dependency Changes

```bash
# In Docker Compose the frontend container runs npm install on start.
# For bare-metal dev:
cd frontend && npm install
```
