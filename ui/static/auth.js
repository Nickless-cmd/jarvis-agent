const TOKEN_KEY = "jarvisUserToken";
const TOKEN_SESSION_KEY = "jarvisUserTokenSession";
const API_KEY = "devkey";
const LAST_PATH_KEY = "jarvisLastPath";

function getCookie(name) {
  const value = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`));
  if (!value) return null;
  return decodeURIComponent(value.split("=")[1] || "");
}

function setCookie(name, value, days = 365) {
  const maxAge = days * 24 * 60 * 60;
  document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=${maxAge}; Path=/; SameSite=Lax`;
}

function deleteCookie(name) {
  document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Lax`;
}

function getToken() {
  return (
    localStorage.getItem(TOKEN_KEY) ||
    sessionStorage.getItem(TOKEN_SESSION_KEY) ||
    getCookie("jarvis_token")
  );
}

function setToken(token, remember = true) {
  if (remember) {
    localStorage.setItem(TOKEN_KEY, token);
    sessionStorage.removeItem(TOKEN_SESSION_KEY);
  } else {
    sessionStorage.setItem(TOKEN_SESSION_KEY, token);
    localStorage.removeItem(TOKEN_KEY);
  }
}


// If running in browser, attach helpers to window for legacy/global use
if (typeof window !== 'undefined') {
  window.getToken = getToken;
  window.authHeaders = authHeaders;
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_SESSION_KEY);
  sessionStorage.removeItem("jarvisConsentSession");
  sessionStorage.removeItem("jarvisThemeSession");
  deleteCookie("jarvis_token");
  authStore.reset();
}

function setLastPath(path) {
  if (!path) return;
  localStorage.setItem(LAST_PATH_KEY, path);
}

function getLastPath() {
  return localStorage.getItem(LAST_PATH_KEY) || "";
}

function authHeaders(extra = {}) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${API_KEY}`,
  };
  if (getCookieConsent() === "accepted") {
    const uiLang = getCookie("jarvis_lang") || localStorage.getItem("jarvisLang");
    if (uiLang) headers["X-UI-Lang"] = uiLang;
    const tz = getCookie("jarvis_tz");
    if (tz) headers["X-UI-TZ"] = tz;
    const locale = getCookie("jarvis_locale");
    if (locale) headers["X-UI-Locale"] = locale;
    const city = getCookie("jarvis_city");
    if (city) headers["X-UI-City"] = city;
  }
  const token = getToken();
  if (token) {
    headers["X-User-Token"] = token;
  }
  return { ...headers, ...extra };
}


// requireAuth is now handled by authStore and app.js

function getCookieConsent() {
  return localStorage.getItem("jarvisCookieConsent") || getCookie("jarvis_consent");
}

function applyConsentCookies(lang) {
  if (getCookieConsent() !== "full") return;
  const value = lang || sessionStorage.getItem("jarvisLangSession") || localStorage.getItem("jarvisLang") || (navigator.language || "da");
  setCookie("jarvis_lang", value);
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (tz) setCookie("jarvis_tz", tz);
  } catch (err) {
    // ignore
  }
  const locale = navigator.language || "";
  if (locale) setCookie("jarvis_locale", locale);
  const city = localStorage.getItem("jarvisCity");
  if (city) setCookie("jarvis_city", city);
}

function initCookieBanner() {
  const banner = document.getElementById("cookieBanner");
  const acceptBtn = document.getElementById("cookieAccept");
  const minimalBtn = document.getElementById("cookieMinimal");
  if (!banner || !acceptBtn || !minimalBtn) return;
  const consent = getCookieConsent();
  if (consent === "full" || consent === "minimal") {
    banner.style.display = "none";
    return;
  }
  if (getToken() && sessionStorage.getItem("jarvisConsentSession")) {
    banner.style.display = "none";
    return;
  }
  banner.style.display = "flex";
  acceptBtn.addEventListener("click", () => {
    localStorage.setItem("jarvisCookieConsent", "full");
    setCookie("jarvis_consent", "full");
    sessionStorage.setItem("jarvisConsentSession", "1");
    applyConsentCookies();
    banner.style.display = "none";
  });
  minimalBtn.addEventListener("click", () => {
    localStorage.setItem("jarvisCookieConsent", "minimal");
    setCookie("jarvis_consent", "minimal");
    sessionStorage.setItem("jarvisConsentSession", "1");
    deleteCookie("jarvis_lang");
    deleteCookie("jarvis_tz");
    deleteCookie("jarvis_locale");
    deleteCookie("jarvis_city");
    banner.style.display = "none";
  });
}

try {
  if (typeof window !== "undefined") {
    const path = window.location.pathname + window.location.search + window.location.hash;
    if (getToken() && path && path !== "/login" && path !== "/admin-login") {
      setLastPath(path);
    }
  }
} catch (err) {
  // ignore
}
