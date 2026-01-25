# Authentication API

## Login

**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "username": "string",
  "password": "string",
  "captcha_token": "string (optional)",
  "captcha_answer": "string (optional)"
}
```

**Response (200 OK):**
```json
{
  "token": "string (uuid4)",
  "expires_at": "string (ISO 8601)"
}
```

**Side effects:**
- Sets `jarvis_token` cookie (HttpOnly, 24h TTL)
- Logs login session with IP address and user agent
- Logs: `LOGIN success user=... is_admin=...`

**Errors:**
- `400`: Invalid captcha
- `401`: Invalid credentials
- `403`: User is disabled

---

## Logout

**Endpoint:** `POST /auth/logout` (NEW)

**Authentication:** Required (Bearer token or Cookie)

**Request:**
```json
{}
```

**Response (200 OK):**
```json
{
  "ok": true
}
```

**Side effects:**
- Invalidates user's token in database (sets token and token_expires_at to NULL)
- Deletes `jarvis_token` cookie
- Logs: `LOGOUT success token=...`

**Errors:**
- `400`: Could not logout (e.g., API bearer token)
- `401`: Not authenticated

**Notes:**
- API bearer tokens (`devkey`, `BEARER_TOKEN` env var) cannot be logged out
- Works with both cookie-based and header-based authentication
- After logout, token is permanently invalid

---

## Admin Login

**Endpoint:** `POST /auth/admin/login`

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200 OK):**
```json
{
  "token": "string (uuid4)",
  "expires_at": "string (ISO 8601)"
}
```

**Errors:**
- `401`: Invalid credentials
- `403`: User is disabled OR not an admin

---

## Client Implementation

### React AuthContext

The UI's `AuthContext.tsx` provides:

```typescript
const { login, logout, profile, loading } = useAuth()

// Login
try {
  await login(username, password)
  // User is now logged in, token is in cookie
} catch (error) {
  if (error.status === 401) {
    // Invalid credentials
  }
}

// Logout
await logout()
// Token is cleared, user redirected to login
```

### Fetch Implementation

```typescript
// Login
const response = await fetch('http://api.local/auth/login', {
  method: 'POST',
  credentials: 'include', // Send cookies
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
})

// Logout
const response = await fetch('http://api.local/auth/logout', {
  method: 'POST',
  credentials: 'include', // Send token cookie
  headers: { 'Authorization': 'Bearer ' + token } // Or from cookie
})
```

---

## Session Management

- **TTL:** 24 hours (configurable via `SESSION_TTL_HOURS` env var)
- **Idle Timeout:** 60 minutes (configurable via `SESSION_IDLE_MINUTES` env var)
- **Automatic Refresh:** Token expiration extended on each request
- **Idle Logout:** Non-admin users logged out after 60 minutes of inactivity

## Env Variables

- `SESSION_TTL_HOURS=24` - Session lifetime
- `SESSION_IDLE_MINUTES=60` - Idle timeout
- `JARVIS_COOKIE_SECURE=0` - Use secure cookie (1 for HTTPS)
- `JARVIS_COOKIE_SAMESITE=lax` - SameSite cookie policy
- `BEARER_TOKEN` - API bearer token (cannot logout)
- `API_BEARER_TOKEN` - Alternate API bearer token (cannot logout)
