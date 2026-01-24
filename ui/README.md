# Jarvis React UI (Vite)

This UI is a ChatGPT‑style shell served under `/ui/`. It consumes the existing backend endpoints via Vite proxy in dev and relative requests in prod.

## Dev
```bash
cd ui
npm install
npm run dev   # http://127.0.0.1:5173/ui/
```

## Build
```bash
npm run build   # outputs to ../ui_dist (served by backend later)
```

## Auth flow
- On boot the UI calls `/account/profile` with `credentials: "include"`.
- If 200: the app renders; admin drawer is available when `is_admin` is true.
- If 401/403: browser is redirected to `/login` (backend page).

## Routes
- `/ui/` — chat view + composer
- `/ui/admin` — same view with admin drawer opened
- `/ui/settings` — opens settings modal, then returns to `/ui/`

## Notes
- Right admin drawer is hidden for non‑admins and toggleable for admins.
- Modals and popovers are closed by default; nothing auto‑opens on page load.
- Dark theme by default, no paid dependencies.
