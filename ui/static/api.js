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
      const verifier = typeof window.verifySessionAndMaybeLogout === 'function' ? window.verifySessionAndMaybeLogout : null;
      const result = verifier ? await verifier(path, res.status) : { authenticated: false };
      const stillAuthed = result && result.authenticated;
      if (isAdminEndpoint(path)) {
        // Admin endpoints may fail without killing session
        if (stillAuthed) {
          return { ok: false, status: res.status, adminDenied: true };
        }
        return { ok: false, status: res.status };
      }
      // Non-admin endpoints: only trigger logout if verifier says not authenticated
      if (!stillAuthed) {
        window.dispatchEvent(new CustomEvent('apiAuthError', { detail: { path, status: res.status } }));
      }
      return { ok: false, status: res.status };
    }
    return res;
  } catch (err) {
    console.warn("apiFetch failed:", path, err);
    window.dispatchEvent(new CustomEvent('apiFetchError', { detail: { path, error: err } }));
    return null;
  }
}
