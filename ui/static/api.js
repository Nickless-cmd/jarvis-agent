function isAdminEndpoint(path) {
  return path.startsWith("/admin/");
}

function isAuthRequiredEndpoint(path) {
  return (
    path.startsWith("/v1/") ||
    path.startsWith("/files") ||
    path.startsWith("/account/")
  );
}

// If running in browser, attach authStore to window for legacy/global use
if (typeof window !== 'undefined') {
  window.authStore = window.authStore || undefined;
}

function safeAuthHeaders(extra = {}) {
  try {
    if (typeof authHeaders === "function") {
      return authHeaders(extra);
    }
  } catch (err) {
    // fall through
  }
  const token = localStorage.getItem("jarvisUserToken") || sessionStorage.getItem("jarvisUserTokenSession");
  const base = {
    "Content-Type": "application/json",
    "Authorization": "Bearer devkey",
  };
  if (token) {
    base["X-User-Token"] = token;
  }
  return { ...base, ...extra };
}


function isAuthCriticalEndpoint(path) {
  return path.startsWith("/v1/") && !path.startsWith("/v1/status") && !path.startsWith("/v1/settings/public");
}


async function apiFetch(path, options = {}) {
  const headersObj = safeAuthHeaders(options.headers || {});
  const headers = new Headers(headersObj);
  if (!headers.has("Authorization")) {
    headers.set("Authorization", "Bearer devkey");
  }
  const fetchOptions = { ...options, headers, credentials: "same-origin" };
  try {
    const res = await fetch(path, fetchOptions);
    if (res.status === 401 || res.status === 403) {
      // --- 401/403 handling ---
      if (isAdminEndpoint(path)) {
        // Never trigger logout for admin endpoints; just return adminDenied
        // UI will hide admin panels and stop polling, but session remains active
        return { ok: false, status: res.status, adminDenied: true };
      }
      if (path === "/auth/me") {
        // Only /auth/me 401 triggers full logout/session expiry
        console.warn("[auth] apiFetch: /auth/me returned ", res.status, "- triggering logout");
        if (typeof window.onAuthLost === 'function') window.onAuthLost('401');
        window.dispatchEvent(new CustomEvent('apiAuthError', { detail: { path, status: res.status } }));
        return null;
      }
      // For other non-admin endpoints, show banner but do not reload or clear cookies
      window.dispatchEvent(new CustomEvent('apiAuthError', { detail: { path, status: res.status } }));
      return { ok: false, status: res.status };
    }
    return res;
  } catch (err) {
    console.warn("apiFetch failed:", path, err);
    window.dispatchEvent(new CustomEvent('apiFetchError', { detail: { path, error: err } }));
    return null;
  }
}
