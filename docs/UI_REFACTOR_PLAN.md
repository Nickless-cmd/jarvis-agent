# UI/App Shell Plan (Phase 1)

Inventory (current files under `ui/`):
- Entry points: `app.html` (main chat), `admin.html` (admin), `login.html`, `admin_login.html`, `maintenance.html`, `account.html`, `tickets.html`, legacy `index.html`, `docs.html`, `registere.html`.
- JS: `ui/static/app.js` (main UI), `admin.js` (admin UI), `api.js` (fetch wrapper), `auth.js`/`authStore.js` (auth state), `app-fix.css`, `app.css`, `styles.css`, `marked.min.js`.
- Observed duplication: multiple status/polling helpers, legacy `index.html` not used for /app, parallel login/admin-login pages, and duplicated polling in app.js that can be unified.

Target structure (no-build, vanilla):
- `ui/index.html` as single shell that routes to chat/admin via hash/router.
- JS: `ui/static/app.js` (shell + chat views), `ui/static/admin.js` (admin view), `ui/static/api.js` (fetch/auth), optional `ui/static/views/*.js` for separation.
- CSS: `ui/static/app.css` as primary; keep `app-fix.css` only if needed, otherwise fold into main.
- Hash-router: `#/chat`, `#/admin`, `#/login`, with role-gating (admin view visible only if `authStore.isAdmin`).

Phase-1 cleanup (done in this repo update):
- Documented plan and constraints; no behavioral changes to avoid regressions.
- Added this plan to make future refactors explicit without code churn.

Remaining technical debt (not fixed yet):
- Duplicate polling/event code in `app.js`.
- Legacy HTML files (`index.html`, `docs.html`, `registere.html`) still present.
- Mixed CSS across `app.css`, `app-fix.css`, `styles.css`.
- Admin and main UI still separated; no router yet.
- Notifications are disabled in code; wiring remains for future work.
