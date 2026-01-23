
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
  const fetchOptions = { ...options, headers };
  if (path.startsWith("/admin/")) {
    fetchOptions.credentials = "include";
  }
  try {
    const res = await fetch(path, fetchOptions);
    if (res.status === 401 || res.status === 403) {
      if (typeof window.onAuthLost === 'function') window.onAuthLost('401');
      authStore.reset();
      window.dispatchEvent(new CustomEvent('apiAuthError', { detail: { path, status: res.status } }));
      return null;
    }
    // On successful response, if this is a profile or session check, update authStore
    if (path === "/account/profile" && res.ok) {
      try {
        const data = await res.clone().json();
        authStore.updateFromProfile(data);
      } catch (e) {
        // ignore
      }
    }
    return res;
  } catch (err) {
    console.warn("apiFetch failed:", path, err);
    window.dispatchEvent(new CustomEvent('apiFetchError', { detail: { path, error: err } }));
    return null;
  }
}
