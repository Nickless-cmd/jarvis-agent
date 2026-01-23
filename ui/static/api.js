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
  try {
    const res = await fetch(path, { ...options, headers });
    if (res.status === 401 || res.status === 403) {
      if (isAuthCriticalEndpoint(path)) {
        clearToken();
        window.location.href = "/login";
        return null;
      } else if (path.startsWith("/admin/")) {
        console.warn("Admin endpoint forbidden (expected for non-admin)");
        // Return response so caller can handle (e.g., hide admin panels)
      } else {
        // For other non-critical endpoints, return null
        return null;
      }
    }
    return res;
  } catch (err) {
    console.warn("apiFetch failed:", path, err);
    return null;
  }
}
