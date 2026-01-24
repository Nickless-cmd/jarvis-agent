function getStreamToggle() { return document.getElementById('streamToggle'); }
function initTheme() {
  // Stub: implement theme initialization if needed
}
function renderRightPanels(updatesLog, commandsList) {
  // Stub: implement right panel rendering if needed
  // This prevents ReferenceError and allows UI to function
}
function getResponseModeSelect() { return document.getElementById('responseModeSelect'); }
function getStatusInline() { return document.getElementById('statusInline'); }
function getStatusBadge() { return document.getElementById('statusBadge'); }
function getModeSelect() { return document.getElementById('modeSelect'); }
function getModelSelect() { return document.getElementById('modelSelect'); }
function getUploadBtn() { return document.getElementById('uploadBtn'); }
function getUploadSidebarBtn() { return document.getElementById('uploadSidebarBtn'); }
function getImageUploadBtn() { return document.getElementById('imageUploadBtn'); }
function getImageUploadInput() { return document.getElementById('imageUploadInput'); }
function getUploadInput() { return document.getElementById('uploadInput'); }
function getNewChatInline() { return document.getElementById('newChatInline'); }
function getToolsSummary() { return document.getElementById('toolsSummary'); }
function getGlobalSearch() { return document.getElementById('globalSearch'); }
function getGlobalSearchResults() { return document.getElementById('globalSearchResults'); }
function getQuotaBar() { return document.getElementById('quotaBar'); }
function getBrandTop() { return document.getElementById('brandTop'); }
function getBrandCore() { return document.getElementById('brandCore'); }
function getBrandShort() { return document.getElementById('brandShort'); }
function getChat() { return document.getElementById('chat'); }
function getChatStatus() { return document.getElementById('chatStatus'); }
function getNoteCreateBtn() { return document.getElementById('noteCreateBtn'); }
function toEl(idOrEl) { return typeof idOrEl === 'string' ? document.getElementById(idOrEl) : idOrEl; }
function showEl(idOrEl) { const el = toEl(idOrEl); if (!el) return; el.classList.remove('hidden'); }
function hideEl(idOrEl) { const el = toEl(idOrEl); if (!el) return; el.classList.add('hidden'); }
function isHidden(idOrEl) { const el = toEl(idOrEl); if (!el) return true; return el.classList.contains('hidden'); }
function startEventsStream() {
  // Stub: implement event stream for notifications if needed
}
// --- UI polish: empty state, composer, settings modal skeleton ---
function updateEmptyState() {
  const chat = document.getElementById('chat');
  const emptyState = document.getElementById('emptyState');
  if (!chat || !emptyState) return;
  // If chat has no children or only whitespace, show emptyState
  const hasMessages = [...chat.children].some(
    el => el.nodeType === 1 && el.textContent.trim()
  );
  emptyState.style.display = hasMessages ? 'none' : '';
}
document.addEventListener('DOMContentLoaded', updateEmptyState);

// Patch chat message rendering to call updateEmptyState after rendering
const origRenderChat = window.renderChatMessage;
window.renderChatMessage = function(...args) {
  const result = origRenderChat ? origRenderChat.apply(this, args) : undefined;
  updateEmptyState();
  return result;
};

// Settings modal open/close logic (skeleton)
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('settingsModal');
  const closeBtn = document.getElementById('closeSettings');
  if (closeBtn && modal) {
    closeBtn.onclick = () => { hideEl(modal); };
  }
  if (modal) {
    hideEl(modal);
    const hash = window.location.hash || "";
    if (hash.startsWith('#settings/')) {
      showEl(modal);
    }
  }
  // Optionally, add a button to open settings
  // document.getElementById('openSettingsBtn').onclick = () => { modal.style.display = ''; };
});
// --- Admin views: dashboard, users, sessions, logs, tickets, tools, config ---
function showAdminView(view) {
  const host = document.getElementById('adminViewHost') || document.querySelector('.chat-pane .main-column');
  if (!host) return;
  host.innerHTML = '';
  if (view === 'dashboard') {
    host.innerHTML = `<h2>Admin Dashboard</h2>
      <div class="admin-cards">
        <div class="admin-card">Users<br><span id="adminUsersCount">…</span></div>
        <div class="admin-card">Sessions<br><span id="adminSessionsCount">…</span></div>
        <div class="admin-card">Errors (24h)<br><span id="adminErrorsCount">…</span></div>
        <div class="admin-card">Tool calls<br><span id="adminToolsCount">…</span></div>
      </div>`;
    // Try to fetch counts, else show "coming soon"
    apiFetch('/admin/users').then(r => r && r.ok ? r.json() : null).then(d => {
      document.getElementById('adminUsersCount').textContent = d?.users?.length ?? 'coming soon';
    });
    apiFetch('/admin/sessions').then(r => r && r.ok ? r.json() : null).then(d => {
      document.getElementById('adminSessionsCount').textContent = d?.sessions?.length ?? 'coming soon';
    });
    document.getElementById('adminErrorsCount').textContent = 'coming soon';
    document.getElementById('adminToolsCount').textContent = 'coming soon';
    return;
  }
  if (view === 'users') {
    host.innerHTML = `<h2>Users</h2><div id="adminUsersTable">Indlæser…</div>`;
    apiFetch('/admin/users').then(r => r && r.ok ? r.json() : null).then(d => {
      const users = d?.users || [];
      const table = document.getElementById('adminUsersTable');
      if (!users.length) { table.textContent = 'Ingen brugere eller coming soon'; return; }
      table.innerHTML = `<table><tr><th>Brugernavn</th><th>Email</th><th>Admin</th></tr>${users.map(u => `<tr><td>${u.username}</td><td>${u.email||''}</td><td>${u.is_admin?'✔':''}</td></tr>`).join('')}</table>`;
    });
    return;
  }
  if (view === 'sessions') {
    host.innerHTML = `<h2>Sessions</h2><div id="adminSessionsTable">Indlæser…</div>`;
    apiFetch('/admin/sessions').then(r => r && r.ok ? r.json() : null).then(d => {
      const sessions = d?.sessions || [];
      const table = document.getElementById('adminSessionsTable');
      if (!sessions.length) { table.textContent = 'Ingen sessions eller coming soon'; return; }
      table.innerHTML = `<table><tr><th>ID</th><th>Navn</th><th>Oprettet</th></tr>${sessions.map(s => `<tr><td>${s.id}</td><td>${s.name||''}</td><td>${s.created_at||''}</td></tr>`).join('')}</table>`;
    });
    return;
  }
  if (view === 'logs') {
    host.innerHTML = `<h2>Logs</h2><div id="adminLogs">Indlæser…</div>`;
    apiFetch('/admin/logs').then(r => r && r.ok ? r.json() : null).then(d => {
      const files = d?.files || [];
      const logs = document.getElementById('adminLogs');
      if (!files.length) { logs.textContent = 'Ingen logs eller coming soon'; return; }
      logs.innerHTML = files.map(f => `<div><a href="#" onclick="loadLogFile('${f}')">${f}</a></div>`).join('');
    });
    return;
  }
  if (view === 'tickets') {
    host.innerHTML = `<h2>Tickets</h2><div id="adminTickets">Indlæser…</div>`;
    apiFetch('/admin/tickets').then(r => r && r.ok ? r.json() : null).then(d => {
      const tickets = d?.tickets || [];
      const el = document.getElementById('adminTickets');
      if (!tickets.length) { el.textContent = 'Ingen tickets eller coming soon'; return; }
      el.innerHTML = `<table><tr><th>ID</th><th>Titel</th><th>Status</th></tr>${tickets.map(t => `<tr><td>${t.id}</td><td>${t.title||''}</td><td>${t.status||''}</td></tr>`).join('')}</table>`;
    });
    return;
  }
  if (view === 'tools') {
    host.innerHTML = `<h2>Tools</h2><div>coming soon</div>`;
    return;
  }
  if (view === 'config') {
    host.innerHTML = `<h2>Config</h2><div>coming soon</div>`;
    return;
  }
  host.innerHTML = '<div>Ukendt admin view</div>';
}

// --- Admin nav and hash routing ---
function setupAdminNav() {
  const nav = document.querySelector('.admin-only .nav-list');
  if (!nav) return;
  nav.querySelectorAll('a').forEach(a => {
    a.onclick = (e) => {
      e.preventDefault();
      const hash = a.getAttribute('href').split('#admin/')[1];
      window.location.hash = '#admin/' + hash;
    };
  });
}


// --- Unified SPA router for all views ---
// Centralized auth state for UI session logic
const authState = {
  isLoggedIn: false,
  isAdmin: false,
  adminUnavailable: false, // Set to true if /admin/* returns 401
  token: null
};

// Centralized auth state from authStore
let isAdminUser = false;
let isLoggedIn = false;
let username = "";
let tokenPresent = false;

function handleHashChange() {
  const hash = window.location.hash;
  const main = document.querySelector('.chat-pane .main-column');
  if (!main) return;
  const settingsModal = document.getElementById('settingsModal');
  if (hash.startsWith('#settings/')) {
    showEl(settingsModal);
  } else {
    hideEl(settingsModal);
  }
  // Helper: 403 panel
  function render403() {
    main.innerHTML = '<div class="forbidden-panel"><h2>403 – Ingen adgang</h2><p>Du har ikke adgang til denne side.</p></div>';
  }
  // Admin views
  if (hash.startsWith('#admin/')) {
    if (!window.authStore?.isAdmin) {
      render403();
      hideAdminPanels();
      return;
    }
    showAdminPanels();
    showAdminView(hash.split('#admin/')[1] || 'dashboard');
    return;
  }
  // Docs view
  if (hash === '#docs') {
    main.innerHTML = '<div class="docs-panel"><h2>Dokumentation</h2><div id="docsContent">Indlæser…</div></div>';
    apiFetch('/docs').then(r => r && r.ok ? r.text() : 'Ingen dokumentation.').then(html => {
      document.getElementById('docsContent').innerHTML = html;
    });
    return;
  }
  // Tickets view
  if (hash === '#tickets' || hash === '#/tickets') {
    main.innerHTML = '<div class="tickets-panel"><h2>Tickets</h2><div id="ticketsContent">Indlæser…</div></div>';
    apiFetch('/tickets').then(r => r && r.ok ? r.text() : 'Ingen tickets.').then(html => {
      document.getElementById('ticketsContent').innerHTML = html;
    });
    return;
  }
  // Account view
  if (hash === '#account' || hash === '#/account') {
    main.innerHTML = '<div class="account-panel"><h2>Konto</h2><div id="accountContent">Indlæser…</div></div>';
    apiFetch('/account/profile').then(r => r && r.ok ? r.text() : 'Ingen konto-info.').then(html => {
      document.getElementById('accountContent').innerHTML = html;
    });
    return;
  }
  // Default: chat view
  setRightbarVisibility(isAdminUser && !authState.adminUnavailable);
  updateEmptyState();
  // Leave chat layout intact for default view
}

window.addEventListener('hashchange', handleHashChange);

function setupUnifiedUIEvents() {
  setupAdminNav();
  // Hide admin menu if not admin
  if (!window.authStore?.isAdmin) {
    document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
    const toggle = document.getElementById('rightbarToggle');
    if (toggle) toggle.style.display = 'none';
  }
  handleHashChange();
  // Modal: settings
  const modal = document.getElementById('settingsModal');
  const closeBtn = document.getElementById('closeSettings');
  if (closeBtn && modal) {
    closeBtn.onclick = () => { hideEl(modal); };
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { hideEl(modal); }
    });
  }
  // Settings modal open (if button exists)
  const openSettingsBtn = document.getElementById('openSettingsBtn');
  if (openSettingsBtn && modal) {
    openSettingsBtn.onclick = () => { openSettingsModal(); };
  }
}

document.addEventListener('DOMContentLoaded', setupUnifiedUIEvents);
window.addEventListener('authStateChanged', () => {
  if (!window.authStore?.isAdmin) {
    document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
    const toggle = document.getElementById('rightbarToggle');
    if (toggle) toggle.style.display = 'none';
  } else {
    document.querySelectorAll('.admin-only').forEach(el => el.style.display = '');
    const toggle = document.getElementById('rightbarToggle');
    if (toggle) toggle.style.display = '';
  }
  setRightbarVisibility(!!window.authStore?.isAdmin && !authState.adminUnavailable);
  handleHashChange();
});

// Prevent double execution of app.js (e.g., if loaded twice)
if (window.__JARVIS_APP_INIT__) {
  console.warn("[jarvis] app.js already initialized, skipping duplicate load.");
} else {
  window.__JARVIS_APP_INIT__ = true;

// Defensive: ensure window.authStore exists
// var authStore = window.authStore || {}; // Removed to avoid redeclaration with const in authStore.js

// Global arrays for polling and streams
let pollingIntervals = [];
let openStreams = [];
let eventClient = null;
let adminPanelsLocked = false;
let adminUnavailable = false;
let authLostLatch = false;
let adminIntervals = [];
let bootstrappingAuth = false;
let verifyingSession = false;

// Session expiry banner logic


function showSessionExpiryBanner() {
  const banner = document.getElementById('sessionExpiryBanner');
  if (banner) {
    banner.classList.remove('hidden');
  }
}

function hideSessionExpiryBanner() {
  const banner = document.getElementById('sessionExpiryBanner');
  if (banner) {
    banner.classList.add('hidden');
  }
}
function hideAuthOverlays() {
  hideSessionExpiryBanner();
  const loggedOut = document.getElementById('loggedOutScreen');
  if (loggedOut) loggedOut.classList.add('hidden');
}
function hideAuthBanners() {
  hideSessionExpiryBanner();
  const loggedOut = document.getElementById('loggedOutScreen');
  if (loggedOut) loggedOut.classList.add('hidden');
}

async function verifySessionAndMaybeLogout(reasonUrl, statusCode) {
  if (verifyingSession) return { authenticated: !authLostLatch };
  verifyingSession = true;
  try {
    const res = await fetch("/account/profile", { method: "GET", headers: authHeaders(), credentials: "same-origin" });
    if (res.ok) {
      const profile = await res.json().catch(() => ({}));
      if (window.authStore && typeof window.authStore.updateFromProfile === 'function') {
        window.authStore.updateFromProfile(profile);
      }
      authLostLatch = false;
      hideAuthOverlays();
      showAppShell();
      document.body.classList.add('ui-ready');
      return { authenticated: true, profile };
    }
    clearToken();
    if (window.authStore && typeof window.authStore.reset === 'function') window.authStore.reset();
    showLoggedOutScreen();
    showSessionExpiryBanner();
    document.body.classList.remove('ui-ready');
    return { authenticated: false };
  } catch (err) {
    return { authenticated: false };
  } finally {
    verifyingSession = false;
  }
}
if (typeof window !== "undefined") {
  window.verifySessionAndMaybeLogout = verifySessionAndMaybeLogout;
}


function stopEventsStream() {
  // Safe no-op if not running
  if (window.eventClient && typeof window.eventClient.close === 'function') {
    window.eventClient.close();
    window.eventClient = null;
  }
}

function onAuthLost(reason) {
  if (bootstrappingAuth) {
    console.warn("[auth] onAuthLost suppressed during boot:", reason);
    return;
  }
  if (authLostLatch) return;
  authLostLatch = true;
  if (typeof stopEventsStream === 'function') stopEventsStream();
  if (typeof stopAllPolling === 'function') stopAllPolling();
  if (typeof closeAllStreams === 'function') closeAllStreams();
  showSessionExpiryBanner();
  console.warn("[auth] onAuthLost triggered: ", reason);
  // Optionally: set UI state to logged out, disable inputs, etc.
}

window.addEventListener('apiAuthError', (e) => {
  if (!window.location.pathname.startsWith('/admin')) {
    onAuthLost(e?.detail?.status || '401');
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('sessionExpiryConfirmBtn');
  if (btn) {
    btn.addEventListener('click', () => {
      hideSessionExpiryBanner();
      if (window.authStore) window.authStore.reset();
      window.location.href = "/login";
    });
  }
});

// Initial check (do not auto-redirect, just show banner if not authenticated)
// Initial check moved to ensureAuthState to avoid false positives during boot

// Listen for authStore changes to update UI (do not auto-redirect)
if (window.authStore && typeof window.authStore.onChange === 'function') {
  window.authStore.onChange(() => {
    if (!window.authStore.isAuthenticated) {
      onAuthLost('authStore');
      if (typeof stopEventsStream === 'function') stopEventsStream();
    } else {
      if (typeof startEventsStream === 'function') startEventsStream();
    }
  });
}


// Safe DOM access helpers
function qs(selector, context = document) { return context.querySelector(selector); }
function qsa(selector, context = document) { return Array.from(context.querySelectorAll(selector)); }
function gid(id) { return document.getElementById(id); }
function safeSetText(el, text) { if (el) el.textContent = text; }
function toggleHidden(el, hidden = null) { if (!el) return; if (hidden === null) { el.classList.toggle('hidden'); } else { el.classList.toggle('hidden', hidden); } }
function isNearBottom(container) { if (!container) return true; const threshold = 100; return container.scrollHeight - container.scrollTop - container.clientHeight < threshold; }

// --- Tool-chips and composer polish ---
document.addEventListener('DOMContentLoaded', () => {
  // Streaming chip toggle
  const streamChip = gid('streamChip');
  const streamToggle = gid('streamToggle');
  const streamDot = gid('streamDot');
  function updateStreamChip() {
    if (!streamToggle || !streamChip || !streamDot) return;
    const on = !!streamToggle.checked;
    streamChip.setAttribute('aria-pressed', on ? 'true' : 'false');
    streamChip.classList.toggle('active', on);
    streamDot.classList.toggle('on', on);
    streamDot.classList.toggle('off', !on);
  }
  if (streamChip && streamToggle) {
    streamChip.addEventListener('click', () => {
      streamToggle.checked = !streamToggle.checked;
      updateStreamChip();
    });
    updateStreamChip();
  }

  // Personality chip popover
  const personaChip = gid('personaChip');
  const personaPopover = gid('personaPopover');
  const personaInput = gid('personaInput');
  const personaSaveBtn = gid('personaSaveBtn');
  const personaCancelBtn = gid('personaCancelBtn');
  // LocalStorage key
  const PERSONA_KEY = 'jarvisPersona';
  function showPersonaPopover() {
    if (!personaPopover) return;
    personaPopover.classList.remove('hidden');
    personaInput.value = localStorage.getItem(PERSONA_KEY) || '';
    personaInput.focus();
  }
  function hidePersonaPopover() {
    if (!personaPopover) return;
    personaPopover.classList.add('hidden');
  }
  if (personaChip && personaPopover) {
    personaChip.addEventListener('click', showPersonaPopover);
    personaSaveBtn?.addEventListener('click', () => {
      localStorage.setItem(PERSONA_KEY, personaInput.value.trim());
      hidePersonaPopover();
    });
    personaCancelBtn?.addEventListener('click', hidePersonaPopover);
    personaInput?.addEventListener('keydown', (e) => { if (e.key === 'Escape') hidePersonaPopover(); });
    document.addEventListener('mousedown', (e) => {
      if (personaPopover && !personaPopover.contains(e.target) && e.target !== personaChip) hidePersonaPopover();
    });
  }

  // Status chip (informational)
  const statusChip = gid('statusChip');
  const statusChipText = gid('statusChipText');
  function updateStatusChip(text) {
    if (statusChipText) statusChipText.textContent = text || 'Jarvis klar';
  }
  // Optionally update on status changes
  window.setStatus = (function(orig) {
    return function(text) {
      orig && orig(text);
      updateStatusChip(text);
    };
  })(window.setStatus || function(){});

  // Composer autosize
  const prompt = gid('prompt');
  if (prompt) {
    prompt.addEventListener('input', () => {
      prompt.style.height = 'auto';
      prompt.style.height = Math.min(prompt.scrollHeight, 160) + 'px';
    });
    // Initial autosize
    prompt.style.height = 'auto';
    prompt.style.height = Math.min(prompt.scrollHeight, 160) + 'px';
  }
});

// --- Admin 401 gating ---
window.adminAvailable = true;
async function probeAdminEndpoints() {
  try {
    const res = await fetch('/admin/tickets?limit=1', { credentials: 'same-origin' });
    if (res.status === 401 || res.status === 403) {
      window.adminAvailable = false;
      document.querySelectorAll('.admin-only, #rightTicketsPanel, #statusPanelCard').forEach(el => el.style.display = 'none');
      if (window.adminPollingIntervals) window.adminPollingIntervals.forEach(clearInterval);
      window.adminPollingIntervals = [];
      return;
    }
    window.adminAvailable = true;
  } catch (e) {
    window.adminAvailable = false;
    document.querySelectorAll('.admin-only, #rightTicketsPanel, #statusPanelCard').forEach(el => el.style.display = 'none');
    if (window.adminPollingIntervals) window.adminPollingIntervals.forEach(clearInterval);
    window.adminPollingIntervals = [];
  }
}
document.addEventListener('DOMContentLoaded', probeAdminEndpoints);

function scrollChatToBottom() {
  const feed = getChatFeed();
  if (feed) {
    feed.scrollTop = feed.scrollHeight;
  }
}

// --- Sessions sidebar logic ---
function getSessionList() { return gid("sessionList"); }
function getSessionSearch() { return gid("sessionSearch"); }
// (removed duplicate declaration of sessionsCache and currentSessionId)
let sessionSearchValue = "";

function renderSessionList() {
  const list = getSessionList();
  if (!list) return;
  const search = getSessionSearch();
  sessionSearchValue = search ? search.value.trim().toLowerCase() : "";
  let filtered = sessionsCache;
  if (sessionSearchValue) {
    filtered = sessionsCache.filter(s => (s.name || "").toLowerCase().includes(sessionSearchValue) || (s.id || "").includes(sessionSearchValue));
  }
  if (!filtered.length) {
    list.innerHTML = '<div class="small">Ingen chats fundet</div>';
    return;
  }
  list.innerHTML = "";
  filtered.forEach(s => {
    const div = document.createElement("div");
    div.className = "session-row" + (s.id === currentSessionId ? " active" : "");
    div.textContent = s.name || s.id;
    div.title = s.name || s.id;
    div.tabIndex = 0;
    div.onclick = () => {
      currentSessionId = s.id;
      renderSessionList();
      loadSessionMessages(s.id);
    };
    list.appendChild(div);
  });
}

if (getSessionSearch()) {
  getSessionSearch().addEventListener("input", renderSessionList);
}
if (document.getElementById("newChatBtn")) {
  document.getElementById("newChatBtn").addEventListener("click", createSession);
}
if (document.getElementById("newChatInline")) {
  document.getElementById("newChatInline").addEventListener("click", createSession);
}
function getNewChatInline() { return gid("newChatInline"); }
function getSessionPromptRow() { return gid("sessionPromptRow"); }
function getSessionPromptInput() { return gid("sessionPromptInput"); }
function getSessionPromptSave() { return gid("sessionPromptSave"); }
function getSessionPromptClear() { return gid("sessionPromptClear"); }
function getSuggestions() { return gid("suggestions"); }
function getNoteToggleBtn() { return gid("noteToggleBtn"); }
function getNoteCreateWrap() { return gid("noteCreateWrap"); }
function getGreetingBanner() { return gid("greetingBanner"); }
function getOnlinePill() { return gid("onlinePill"); }
function getModeLabel() { return gid("modeLabel"); }
function getFilesToggleBtn() { return gid("filesToggleBtn"); }
function getFilesListWrap() { return gid("filesListWrap"); }
function getNotesList() { return gid("notesList"); }
function getNoteContentInput() { return gid("noteContentInput"); }
function getMicBtn() { return gid("micBtn"); }
function getLangSelect() { return gid("langSelect"); }
function getThemeSelect() { return gid("themeSelect"); }
function getChatPane() { return qs(".chat-pane"); }
function getModeChip() { return gid("modeChip"); }
function getModeChipLabel() { return gid("modeChipLabel"); }
function getEventsList() { return gid("eventsList"); }
function getNotificationsBtn() { return gid("notificationsBtn"); }
function getNotificationsBadge() { return gid("notificationsBadge"); }
function getNotificationsDropdown() { return gid("notificationsDropdown"); }
function getNotificationsList() { return gid("notificationsList"); }
function getNotificationsMarkAllRead() { return gid("notificationsMarkAllRead"); }
function getToolsBtn() { return gid("toolsBtn"); }
function getToolsDropdown() { return gid("toolsDropdown"); }
function getPromptInput() { return gid("prompt"); }
function getSendBtn() { return gid("sendBtn"); }
function getStatusRow() { return qs(".status-row"); }
function getChatFeed() { return qs(".main-column .chat-feed"); }
function getDocsBtn() { return gid("docsBtn"); }
function getTicketsBtn() { return gid("ticketsBtn"); }
function getCollapseBtn() { return gid("collapseBtn"); }
function getStreamChip() { return gid("streamChip"); }
function getStreamDot() { return gid("streamDot"); }
function getPersonaChip() { return gid("personaChip"); }

const LAST_SESSION_KEY = "jarvisLastSessionId";
const LAST_SESSION_COOKIE = "jarvis_last_session";

let currentSessionId = null;
let sessionsCache = [];
let lastSent = { text: "", ts: 0 };

function updateAuthStateFromStore() {
  if (!window.authStore) return;
  isAdminUser = !!window.authStore.isAdmin;
  isLoggedIn = !!window.authStore.isAuthenticated;
  username = window.authStore.username || "";
  tokenPresent = !!(window.getToken && window.getToken());
}

// Listen for auth state changes

function showLoggedOutScreen() {
  const root = document.getElementById("appRoot");
  const loggedOut = document.getElementById("loggedOutScreen");
  if (root) root.classList.add("hidden");
  if (loggedOut) loggedOut.classList.remove("hidden");
  if (typeof stopAllPolling === "function") stopAllPolling();
  if (typeof stopEventsStream === "function") stopEventsStream();
}

function showAppShell() {
  const root = document.getElementById("appRoot");
  const loggedOut = document.getElementById("loggedOutScreen");
  if (root) root.classList.remove("hidden");
  if (loggedOut) loggedOut.classList.add("hidden");
}

function setRightbarVisibility(show) {
  const layout = document.querySelector(".chat-layout");
  const right = document.querySelector(".rightbar");
  if (!layout || !right) return;
  if (show) {
    layout.classList.add("has-rightbar");
    right.classList.remove("hidden");
  } else {
    layout.classList.remove("has-rightbar");
    right.classList.add("hidden");
  }
}

function hideAdminPanels() {
  setRightbarVisibility(false);
  document.querySelectorAll('.admin-only, #rightTicketsPanel, #statusPanel').forEach(el => {
    el.classList.add('panel-disabled');
    if (el.id === 'rightTicketsPanel' || el.id === 'statusPanel') {
      el.innerHTML = `<div class="muted">${getUiLang() === "en" ? "Admin access required." : "Admin kræver adgang."}</div>`;
    }
  });
}

function showAdminPanels() {
  setRightbarVisibility(true);
  document.querySelectorAll('.admin-only, #rightTicketsPanel, #statusPanel').forEach(el => {
    el.classList.remove('panel-disabled');
  });
}

function openSettingsModal() {
  const modal = document.getElementById('settingsModal');
  if (modal) {
    showEl(modal);
  }
}

function stopAdminPolling() {
  // Stop any polling intervals related to admin endpoints
  if (window.adminPollingIntervals) {
    window.adminPollingIntervals.forEach(clearInterval);
    window.adminPollingIntervals = [];
  }
}

function startAdminPolling() {
  // Only start polling if admin
  if (!isAdminUser) return;
  if (!window.adminPollingIntervals) window.adminPollingIntervals = [];
  // Example: poll tickets/logs every 15s
  window.adminPollingIntervals.push(setInterval(loadRightTickets, 15000));
  window.adminPollingIntervals.push(setInterval(loadRightLogs, 15000));
}

function bindRightbarToggle() {
  const toggle = document.getElementById("rightbarToggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => {
    const right = document.querySelector(".rightbar");
    const isVisible = right && !right.classList.contains("hidden");
    setRightbarVisibility(!isVisible);
  });
}

// Initial state
updateAuthStateFromStore();
let tooltipEl = null;
let ticketsCache = [];
let searchSeq = 0;
let brandCoreLabel = "Jarvis";
let hasMessages = false;
let micActive = false;
let micRecognizer = null;
let micReady = false;
let currentUserName = "";
let autoSessionInFlight = false;
let maintenanceEnabled = false;
let maintenanceMessage = "";

// Global UI element references
let noteToggleBtn = null;
let noteCreateBtn = null;
let noteCreateWrap = null;
let filesToggleBtn = null;
let filesListWrap = null;
let filesList = null;
let notesList = null;
let eventsList = null;
let sessionPromptSave = null;
let sessionPromptInput = null;
let sessionPromptClear = null;
let noteContentInput = null;
let notificationsCache = [];
let notificationsLastId = null;
// lastEventId declared near event client section
const NOTIFY_ENABLED = false; // temporary: disable notifications without removing code
function initNotificationsUI() {
  const wrap = document.getElementById("notifWrap");
  const dropdown = getNotificationsDropdown();
  if (dropdown) dropdown.hidden = true;
  const enabled = NOTIFY_ENABLED !== false && PUBLIC_SETTINGS.notifications_enabled !== false;
  if (wrap) wrap.classList.toggle("hidden", !enabled);
}

function storeCurrentSession() {
  if (currentSessionId) {
    localStorage.setItem(LAST_SESSION_KEY, currentSessionId);
    const maxAge = 24 * 60 * 60;
    document.cookie = `${LAST_SESSION_COOKIE}=${encodeURIComponent(currentSessionId)}; Max-Age=${maxAge}; Path=/; SameSite=Lax`;
  }
}

function getLastSession() {
  const stored = localStorage.getItem(LAST_SESSION_KEY);
  if (stored) return stored;
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${LAST_SESSION_COOKIE}=`));
  if (!cookie) return "";
  return decodeURIComponent(cookie.split("=")[1] || "");
}

const SUGGESTIONS_POOL = [
  "Hjælp mig i gang med et CV",
  "Opsummer vores samtale kort",
  "Hvad kan du hjælpe mig med i dag?",
  "Vis mig de seneste nyheder om teknologi",
  "Lav en kort plan for min dag",
  "Beskriv vejret i Svendborg",
  "Giv mig 3 ideer til aftensmad",
];

const I18N = {
  da: {
    searchPlaceholder: "Søg i docs, tickets, chats...",
    newChat: "Start ny chat",
    newNote: "Ny note",
    showFiles: "Vis filer",
    noFiles: "Ingen filer endnu.",
    quota: "Kvota",
    today: "Chats i dag",
    earlier: "Tidligere chats",
    active: "Aktiv chat",
    tools: "Værktøjer:",
    modeChat: "Chat",
    modeDev: "Dev",
    statusReady: "Klar",
    statusReadyFull: "JARVIS er klar.",
    langDa: "🇩🇰 DK",
    langEn: "🇬🇧 EN",
    themeDark: "🌙 Mørk",
    themeLight: "☀ Lys",
    themeSystem: "💻 System",
    responseNormal: "📝 Normal",
    responseShort: "💬 Kort",
    responseDeep: "🔍 Dybt",
    ariaLanguage: "Sprog",
    ariaTheme: "Tema",
    ariaResponseMode: "Svar mode",
    statusThinking: "Tænker…",
    statusSearching: "Søger…",
    statusWriting: "Skriver…",
  },
  en: {
    searchPlaceholder: "Search docs, tickets, chats...",
    newChat: "Start new chat",
    newNote: "New note",
    showFiles: "Show files",
    noFiles: "No files yet.",
    quota: "Quota",
    today: "Today",
    earlier: "Earlier chats",
    active: "Active chat",
    tools: "Tools:",
    modeChat: "Chat",
    modeDev: "Dev",
    statusReady: "Ready",
    statusReadyFull: "JARVIS is ready.",
    langDa: "🇩🇰 DK",
    langEn: "🇬🇧 EN",
    themeDark: "🌙 Dark",
    themeLight: "☀ Light",
    themeSystem: "💻 System",
    responseNormal: "📝 Normal",
    responseShort: "💬 Short",
    responseDeep: "🔍 Deep",
    ariaLanguage: "Language",
    ariaTheme: "Theme",
    ariaResponseMode: "Response mode",
    statusThinking: "Thinking…",
    statusSearching: "Searching…",
    statusWriting: "Writing…",
  },
};

function getUiLang() {
  const langSelect = getLangSelect();
  if (langSelect?.value) return langSelect.value;
  return sessionStorage.getItem("jarvisLangSession") || localStorage.getItem("jarvisLang") || "da";
}

function applyUiLang(value) {
  const lang = value === "en" ? "en" : "da";
  sessionStorage.setItem("jarvisLangSession", lang);
  localStorage.removeItem("jarvisLang");
  document.documentElement.lang = lang;
  const dict = I18N[lang];
  const globalSearch = getGlobalSearch();
  if (globalSearch) globalSearch.placeholder = dict.searchPlaceholder;
  const sessionSearch = getSessionSearch();
  if (sessionSearch) {
    sessionSearch.placeholder = lang === "en" ? "Search chats..." : "Søg chats...";
  }
  const newChatInline = getNewChatInline();
  if (newChatInline) newChatInline.textContent = dict.newChat;
  noteToggleBtn = getNoteToggleBtn();
  if (noteToggleBtn) noteToggleBtn.textContent = dict.newNote;
  filesToggleBtn = getFilesToggleBtn();
  if (filesToggleBtn) filesToggleBtn.textContent = dict.showFiles;
  const quotaBar = getQuotaBar();
  if (quotaBar) {
    const label = quotaBar.querySelector(".quota-label span");
    if (label) label.textContent = dict.quota;
  }
  // Update status badge
  const statusBadge = getStatusBadge();
  if (statusBadge) statusBadge.textContent = dict.statusReady;
  // Update status line
  const statusInline = getStatusInline();
  if (statusInline) statusInline.textContent = dict.statusReadyFull;
  // Update select options
  const langSelect = getLangSelect();
  if (langSelect) {
    langSelect.value = lang;
    const daOption = langSelect.querySelector('option[value="da"]');
    const enOption = langSelect.querySelector('option[value="en"]');
    if (daOption) daOption.textContent = dict.langDa;
    if (enOption) enOption.textContent = dict.langEn;
    langSelect.setAttribute('aria-label', dict.ariaLanguage);
  }
  const themeSelect = getThemeSelect();
  if (themeSelect) {
    const darkOption = themeSelect.querySelector('option[value="dark"]');
    const lightOption = themeSelect.querySelector('option[value="light"]');
    const systemOption = themeSelect.querySelector('option[value="system"]');
    if (darkOption) darkOption.textContent = dict.themeDark;
    if (lightOption) lightOption.textContent = dict.themeLight;
    if (systemOption) systemOption.textContent = dict.themeSystem;
    themeSelect.setAttribute('aria-label', dict.ariaTheme);
  }
  const responseModeSelect = getResponseModeSelect();
  if (responseModeSelect) {
    const normalOption = responseModeSelect.querySelector('option[value="normal"]');
    const shortOption = responseModeSelect.querySelector('option[value="short"]');
    const deepOption = responseModeSelect.querySelector('option[value="deep"]');
    if (normalOption) normalOption.textContent = dict.responseNormal;
    if (shortOption) shortOption.textContent = dict.responseShort;
    if (deepOption) deepOption.textContent = dict.responseDeep;
    responseModeSelect.setAttribute('aria-label', dict.ariaResponseMode);
  }
  updateToolsSummary();
  updateModeChipLabel();
  updatePromptPlaceholder();
  updateGreeting(currentUserName);
  renderRightPanels(window.__updatesLog || "", window.__commandsList || []);
  if (getCookieConsent && getCookieConsent() === "accepted") {
    applyConsentCookies(lang);
  }
}

function applyUiTheme(value) {
  const want = value === "light" || value === "system" ? value : "dark";
  sessionStorage.setItem("jarvisThemeSession", want);
  if (want === "system") {
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const resolved = prefersDark ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.setAttribute("data-theme-mode", "system");
  } else {
    document.documentElement.setAttribute("data-theme", want);
    document.documentElement.setAttribute("data-theme-mode", "manual");
  }
  const themeSelect = getThemeSelect();
  if (themeSelect) themeSelect.value = want;
  // After theme is set, update admin panels if needed
  updateAdminPanelsAfterTheme();
}

async function updateAdminPanelsAfterTheme() {
  if (!authState.isAdmin || authState.adminUnavailable) return;
  const rightTicketsBody = document.getElementById("rightTicketsBody");
  const rightTicketsTitle = document.getElementById("rightTicketsTitle");
  const rightTicketsPanel = document.getElementById("rightTicketsPanel");
  if (!rightTicketsBody || !rightTicketsPanel) return;
  const data = await safeJson("/admin/tickets", { method: "GET" }, {});
  if (data && data.adminDenied) {
    setAdminUnavailable();
    return;
  }
  let all = [];
  if (data) {
    all = data.tickets || [];
  }
  const activeCount = all.filter((t) => t.status !== "closed" && t.status !== "fixed").length;
  if (rightTicketsTitle) {
    rightTicketsTitle.textContent =
      getUiLang() === "en" ? `Tickets (${activeCount} active)` : `Tickets (${activeCount} aktive)`;
  }
  const list = all.slice(0, 5);
  if (!list.length) {
    rightTicketsBody.innerHTML = `<div class="muted">${getUiLang() === "en" ? "No tickets." : "Ingen tickets."}</div>`;
    return;
  }
  const statusLabel = (s) => (s || "").toLowerCase();
  const items = list.map((t) => {
    const status = statusLabel(t.status);
    const priority = (t.priority || "").toLowerCase();
    const statusCls = status === "open" ? "status-green" : status === "pending" ? "status-yellow" : "status-red";
    const prioCls = priority === "kritisk" ? "status-red" : priority === "moderat" ? "status-yellow" : "status-green";
    return `<li><a class="ticket-link" href="/admin#tickets">#${t.id} ${t.title}</a><span class="ticket-status ${statusCls}">${t.status}</span><span class="ticket-priority ${prioCls}">${priority || "ukendt"}</span></li>`;
  }).join("");
  rightTicketsBody.innerHTML = `<ul class="ticket-list">${items}</ul>`;
  // Optionally update logs/statusPanel as well
  const statusPanel = document.getElementById("statusPanel");
  const logsData = await safeJson("/admin/logs", { method: "GET" }, {});
  if (logsData && logsData.adminDenied) {
    setAdminUnavailable();
    return;
  }
  if (!logsData) return;
  const files = logsData.files || [];
  if (!files.length) {
    if (statusPanel) statusPanel.innerHTML = `<div class="muted">${getUiLang() === "en" ? "No logs yet." : "Ingen logs endnu."}</div>`;
    return;
  }
  const latest = files[0]?.name;
  if (!latest) return;
  const payload = await safeJson(`/admin/logs/${latest}`, { method: "GET" }, {});
  const content = (payload.content || "").trim();
  const lines = content.split("\n").slice(-12).join("\n");
  if (statusPanel) statusPanel.innerHTML = `<pre>${lines || (getUiLang() === "en" ? "No logs yet." : "Ingen logs endnu.")}</pre>`;
}

async function loadRightTickets() {
  const rightTicketsBody = document.getElementById("rightTicketsBody");
  const rightTicketsTitle = document.getElementById("rightTicketsTitle");
  const rightTicketsPanel = document.getElementById("rightTicketsPanel");
  const noAdminMsg = `<div class="muted">${getUiLang() === "en" ? "Admin access required." : "Admin kræver adgang."}</div>`;
  if (!isAdminUser || adminPanelsLocked || adminUnavailable) {
    if (rightTicketsPanel) rightTicketsPanel.classList.add("panel-disabled");
    if (rightTicketsBody) rightTicketsBody.innerHTML = noAdminMsg;
    return;
  }
  if (!rightTicketsBody || !rightTicketsPanel) return;
  const data = await safeJson("/admin/tickets", { method: "GET" }, {});
  if (data && data.adminDenied) {
    adminPanelsLocked = true;
    adminUnavailable = true;
    stopAdminPolling();
    hideAdminPanels();
    rightTicketsPanel.classList.add("panel-disabled");
    rightTicketsBody.innerHTML = noAdminMsg;
    return;
  }
  let all = [];
  if (data) {
    all = data.tickets || [];
  }
  const activeCount = all.filter((t) => t.status !== "closed" && t.status !== "fixed").length;
  if (rightTicketsTitle) {
    rightTicketsTitle.textContent =
      getUiLang() === "en" ? `Tickets (${activeCount} active)` : `Tickets (${activeCount} aktive)`;
  }
  const list = all.slice(0, 5);
  if (!list.length) {
    rightTicketsBody.innerHTML = `<div class="muted">${getUiLang() === "en" ? "No tickets." : "Ingen tickets."}</div>`;
    return;
  }
  const statusLabel = (s) => (s || "").toLowerCase();
  const items = list.map((t) => {
    const status = statusLabel(t.status);
    const priority = (t.priority || "").toLowerCase();
    const statusCls = status === "open" ? "status-green" : status === "pending" ? "status-yellow" : "status-red";
    const prioCls = priority === "kritisk" ? "status-red" : priority === "moderat" ? "status-yellow" : "status-green";
    return `<li><a class="ticket-link" href="/admin#tickets">#${t.id} ${t.title}</a><span class="ticket-status ${statusCls}">${t.status}</span><span class="ticket-priority ${prioCls}">${priority || "ukendt"}</span></li>`;
  }).join("");
  rightTicketsBody.innerHTML = `<ul class="ticket-list">${items}</ul>`;
}

async function loadRightPanels() {
  try {
    const res = await fetch('/settings/public');
    if (!res.ok) return;
    const data = await res.json();
    window.PUBLIC_SETTINGS = data;
    window.__updatesLog = (data.updates_log || data.updates_auto || []).join('\n');
    window.__commandsList = data.commands || [];
    // Handle banner
    if (topBanner) {
      if (data.banner && data.banner.trim()) {
        bannerTrack.textContent = data.banner.trim();
        topBanner.classList.remove('hidden');
      } else {
        topBanner.classList.add('hidden');
      }
    }
  } catch (err) {
    // ignore
  }
}

async function loadRightNotes() {
  const notesList = getNotesList();
  if (!notesList) return;
  const data = await safeJson("/notes", { method: "GET" }, {});
  if (!data || !data.notes) {
    notesList.innerHTML = `<div class="muted">${getUiLang() === "en" ? "No notes." : "Ingen noter."}</div>`;
    return;
  }
  const items = data.notes.map((n) => `<li>${n.title || n.content?.substring(0, 50) || "Untitled"}</li>`).join("");
  notesList.innerHTML = `<ul class="notes-list">${items}</ul>`;
}

async function loadRightLogs() {
  const statusPanel = document.getElementById("statusPanel");
  const noAdminMsg = `<div class="muted">${getUiLang() === "en" ? "Admin access required." : "Admin kræver adgang."}</div>`;
  if (!isAdminUser || adminPanelsLocked || adminUnavailable) {
    if (statusPanel) statusPanel.classList.add("panel-disabled");
    if (statusPanel) statusPanel.innerHTML = noAdminMsg;
    return;
  }
  const data = await safeJson("/admin/logs", { method: "GET" }, {});
  if (data && data.adminDenied) {
    adminPanelsLocked = true;
    adminUnavailable = true;
    stopAdminPolling();
    hideAdminPanels();
    if (statusPanel) statusPanel.classList.add("panel-disabled");
    if (statusPanel) statusPanel.innerHTML = noAdminMsg;
    return;
  }
  if (!data) return;
  const files = data.files || [];
  if (!files.length) {
    if (statusPanel) statusPanel.innerHTML = `<div class="muted">${getUiLang() === "en" ? "No logs yet." : "Ingen logs endnu."}</div>`;
    return;
  }
  const latest = files[0]?.name;
  if (!latest) return;
  const payload = await safeJson(`/admin/logs/${latest}`, { method: "GET" }, {});
  const content = (payload.content || "").trim();
  const lines = content.split("\n").slice(-12).join("\n");
  if (statusPanel) statusPanel.innerHTML = `<pre>${lines || (getUiLang() === "en" ? "No logs yet." : "Ingen logs endnu.")}</pre>`;
}

function updatePromptPlaceholder() {
  const input = getPromptInput();
  if (!input) return;
  const lang = getUiLang();
  const label = brandCoreLabel || "Jarvis";
  input.placeholder = lang === "en" ? `Write to ${label}...` : `Skriv til ${label}...`;
  sessionPromptInput = getSessionPromptInput();
  if (sessionPromptInput) {
    sessionPromptInput.placeholder =
      lang === "en"
        ? `Session style for ${label}...`
        : `Session‑personlighed for ${label}...`;
  }
}

function updateModeChipLabel() {
  // Mode UI removed.
}

async function checkMaintenance() {
  const res = await fetch("/settings/public");
  if (!res.ok) return;
  const data = await res.json();
  maintenanceEnabled = !!data.maintenance_enabled;
  maintenanceMessage = data.maintenance_message || "";
  updateBanner(data.banner_messages || "", data.banner_enabled !== false);
  if (maintenanceEnabled && !isAdminUser) {
    window.location.href = "/maintenance";
    return;
  }
  if (maintenanceEnabled && isAdminUser) {
    const chatStatusInline = getStatusInline();
    if (chatStatusInline) {
      chatStatusInline.textContent = maintenanceMessage || "Vedligeholdelse aktiv.";
    }
    const chatStatus = getChatStatus();
    if (chatStatus) {
      chatStatus.textContent = maintenanceMessage || "Vedligeholdelse aktiv.";
    }
    const promptInput = getPromptInput();
    if (promptInput) promptInput.disabled = true;
    const sendBtn = getSendBtn();
    if (sendBtn) sendBtn.disabled = true;
  } else {
    const promptInput = getPromptInput();
    if (promptInput) promptInput.disabled = false;
    const sendBtn = getSendBtn();
    if (sendBtn) sendBtn.disabled = false;
  }
}

function updateBanner(text, enabled = true) {
  if (!topBanner || !bannerTrack) return;
  const msg = (text || "").trim();
  if (!enabled || !msg) {
    topBanner.classList.add("hidden");
    bannerTrack.textContent = "";
    return;
  }
  topBanner.classList.remove("hidden");
  bannerTrack.textContent = msg;
}

function appendEventBanners(events) {
  if (!eventsList) return;
  if (!events || !events.length) return;
  eventsList.classList.remove("hidden");
  events.forEach((event) => {
    const pill = document.createElement("div");
    pill.className = "event-pill";

    const body = document.createElement("div");
    body.className = "event-body";
    body.textContent = (event.body || event.message || "").slice(0, 800);

    if (event.meta && event.meta.refs && event.meta.refs.length) {
      const refsDiv = document.createElement("div");
      refsDiv.className = "event-refs";
      event.meta.refs.forEach((ref) => {
        const span = document.createElement("span");
        span.className = "event-ref";
        span.textContent = `${ref.path}:${ref.start_line}-${ref.end_line}`;
        span.title = "Click to copy";
        span.style.cursor = "pointer";
        span.style.marginRight = "8px";
        span.addEventListener("click", () => {
          navigator.clipboard.writeText(`${ref.path}:${ref.start_line}-${ref.end_line}`).then(() => {
            span.textContent = "Copied!";
            setTimeout(() => span.textContent = `${ref.path}:${ref.start_line}-${ref.end_line}`, 1000);
          }).catch(() => {
            // Fallback if clipboard not available
            span.textContent = "Copy failed";
            setTimeout(() => span.textContent = `${ref.path}:${ref.start_line}-${ref.end_line}`, 1000);
          });
        });
        refsDiv.appendChild(span);
      });
      pill.appendChild(refsDiv);
    }

    const meta = document.createElement("div");
    meta.className = "event-meta";
    meta.textContent = event.created_utc ? formatPublished(event.created_utc) : "";

    const dismissBtn = document.createElement("button");
    dismissBtn.type = "button";
    dismissBtn.setAttribute("aria-label", "Dismiss event");
    dismissBtn.textContent = "×";
    dismissBtn.addEventListener("click", () => dismissEvent(event.id));

    pill.appendChild(body);
    pill.appendChild(meta);
    pill.appendChild(dismissBtn);
    eventsList.appendChild(pill);
  });
  if (events.length > 0) {
    lastEventId = events[events.length - 1].id;
  }
}

async function dismissEvent(eventId) {
  try {
    await apiFetch(`/v1/events/${eventId}/dismiss`, { method: "POST" });
  } catch (err) {
    console.error("Failed to dismiss event:", err);
  }
}

function normalizeText(value) {
  return (value || "").toLowerCase();
}

function showSearchResults(items) {
  if (!globalSearchResults) return;
  globalSearchResults.innerHTML = "";
  if (!items.length) {
    globalSearchResults.classList.remove("open");
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "search-item";
    row.innerHTML = `
      <div>${item.title}</div>
      <div class="search-meta">${item.meta}</div>
    `;
    row.addEventListener("click", () => {
      globalSearchResults.classList.remove("open");
      if (item.onClick) {
        item.onClick();
      } else if (item.url) {
        window.location.href = item.url;
      }
    });
    globalSearchResults.appendChild(row);
  });
  globalSearchResults.classList.add("open");
}

async function loadTicketsCache() {
  if (ticketsCache.length) return;
  const res = await apiFetch("/api/tickets", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  ticketsCache = data.tickets || [];
}

async function handleGlobalSearch(value) {
  const query = normalizeText(value).trim();
  if (!query) {
    showSearchResults([]);
    return;
  }
  const seq = ++searchSeq;
  const items = [];
  const docs = [{ title: "Dokumentation", meta: "Docs", url: "/docs", keywords: ["doc", "dokument", "hjaelp"] }];
  docs.forEach((doc) => {
    const match = [doc.title, ...(doc.keywords || [])].some((k) => normalizeText(k).includes(query));
    if (match) items.push({ title: doc.title, meta: doc.meta, url: doc.url });
  });
  await loadTicketsCache();
  ticketsCache
    .filter((t) => normalizeText(t.title).includes(query))
    .slice(0, 5)
    .forEach((t) => items.push({ title: t.title, meta: `Ticket • ${t.status}`, url: "/tickets" }));
  sessionsCache
    .filter((s) => normalizeText(s.name || s.id).includes(query))
    .slice(0, 5)
    .forEach((s) =>
      items.push({
        title: s.name || s.id,
        meta: "Chat",
        onClick: () => {
          currentSessionId = s.id;
          renderSessionList();
          loadSessionMessages(s.id);
        },
      })
    );
  if (query.length >= 2) {
    const res = await apiFetch(`/search?q=${encodeURIComponent(query)}`, { method: "GET" });
    if (res && seq === searchSeq) {
      const data = await res.json();
      const matches = data.results || [];
      matches.slice(0, 5).forEach((m) => {
        if (m.type === "note") {
          items.push({
            title: m.note_title,
            meta: `Note • ${m.snippet || ""}`,
            onClick: () => {
              const input = document.getElementById("prompt");
              if (input) {
                input.value = `analyser note ${m.note_id}`;
                input.focus();
              }
            },
          });
          return;
        }
        if (m.type === "file") {
          items.push({
            title: m.file_name,
            meta: "Fil • klik for analyse",
            onClick: () => {
              const input = document.getElementById("prompt");
              if (input) {
                input.value = `analyser fil ${m.file_id}`;
                input.focus();
              }
            },
          });
          return;
        }
        items.push({
          title: m.session_name,
          meta: `Chat • ${m.snippet || "match"}`,
          onClick: () => {
            currentSessionId = m.session_id;
            renderSessionList();
            loadSessionMessages(m.session_id);
          },
        });
      });
    }
  }
  showSearchResults(items);
}

async function loadExpiryNotice() {
  if (!expiryNotice) return;
  const res = await apiFetch("/notifications", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const warnings = data.warnings || [];
  expiryNotice.textContent = warnings.length ? warnings.join(" ") : "";
}

function closeSessionMenus(except = null) {
  document.querySelectorAll(".session-menu.open").forEach((menu) => {
    if (menu !== except) {
      menu.classList.remove("open");
    }
  });
}

let statusTimeout = null;
let lastStatusTime = 0;
const MIN_STATUS_DURATION = 300; // ms

function setStatus(text) {
  const now = Date.now();
  const timeSinceLast = now - lastStatusTime;
  if (statusTimeout) {
    clearTimeout(statusTimeout);
    statusTimeout = null;
  }
  if (timeSinceLast < MIN_STATUS_DURATION) {
    const delay = MIN_STATUS_DURATION - timeSinceLast;
    statusTimeout = setTimeout(() => setStatusImmediate(text), delay);
    return;
  }
  setStatusImmediate(text);
}

function setStatusImmediate(text) {
  lastStatusTime = Date.now();
  const dict = I18N[getUiLang()] || I18N.da;
  let translatedText = text;
  if (text === "Klar") {
    translatedText = dict.statusReady;
  } else if (text === "JARVIS er klar.") {
    translatedText = dict.statusReadyFull;
  } else if (text === "Tænker…") {
    translatedText = dict.statusThinking;
  } else if (text === "Søger…") {
    translatedText = dict.statusSearching;
  } else if (text === "Skriver…") {
    translatedText = dict.statusWriting;
  }
  const statusBadge = getStatusBadge();
  if (statusBadge) statusBadge.textContent = translatedText;
  const statusInline = getStatusInline();
  const nameLabel = brandCoreLabel || "Jarvis";
  if (statusInline) {
    const line =
      translatedText === dict.statusReady || translatedText === dict.statusReadyFull
        ? `${nameLabel} — ${dict.statusReady}`
        : `${nameLabel} — ${translatedText}`;
    statusInline.textContent = line;
  }
  const lastAssistant = [...document.querySelectorAll(".msg-assistant")].pop();
  if (lastAssistant) {
    const statusEl = lastAssistant.querySelector(".msg-status");
    if (statusEl) {
      statusEl.textContent = `${nameLabel} — ${translatedText}`;
    }
  }
}

function updateGreeting(name) {
  const greetingBanner = gid("greetingBanner");
  if (!greetingBanner) return;
  currentUserName = name || "";
  const hour = new Date().getHours();
  const lang = getUiLang();
  let greeting = lang === "en" ? "Hello" : "Hej";
  if (hour < 5) greeting = lang === "en" ? "Good evening" : "Godaften";
  else if (hour < 10) greeting = lang === "en" ? "Good morning" : "Godmorgen";
  else if (hour < 12) greeting = lang === "en" ? "Good day" : "Goddag";
  else if (hour < 17) greeting = lang === "en" ? "Good afternoon" : "God eftermiddag";
  else if (hour < 22) greeting = lang === "en" ? "Good evening" : "Godaften";
  const who = name ? `, ${name}` : "";
  const tailsDa = [
    "— til tjeneste. Hvad skal vi tage fat på i dag?",
    "— til rådighed. Hvad vil De have hjælp til?",
    "— klar til næste opgave. Hvad skal vi begynde med?",
    "— lad os få styr på dagens næste træk. Hvad ønsker De?",
  ];
  const tailsEn = [
    "— at your service. What are we tackling today?",
    "— ready when you are. Where shall we begin?",
    "— on standby. What would you like me to handle?",
    "— let’s keep things tidy. What’s first on the list?",
  ];
  const pool = lang === "en" ? tailsEn : tailsDa;
  const tail = pool[Math.floor(Math.random() * pool.length)];
  greetingBanner.textContent = `${greeting}${who} ${tail}`;
}

async function uploadFile(file) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const headers = authHeaders();
  delete headers["Content-Type"];
  const res = await fetch("/files/upload", {
    method: "POST",
    headers,
    body: form,
  });
  if (res.status === 401 || res.status === 403) {
    clearToken();
    window.location.href = "/login";
    return;
  }
  const data = await res.json();
  if (!res.ok) {
    sessionStatus.textContent = data.detail || "Kunne ikke uploade fil.";
    return;
  }
  const info = data.file || {};
  const url = data.url;
  renderChatMessage({ role: "assistant", content: `Fil uploadet: ${info.original_name || "fil"} (id ${info.id}).` });
  if (url) {
    addFileCard({ title: info.original_name || "Fil", label: "Download fil", url });
  }
  loadFiles();
}

async function loadNotes() {
  if (!notesList) return;
  const data = await safeJson("/notes", {}, { method: "GET" });
  const items = (data && data.notes) || [];
  notesList.innerHTML = "";
  if (!items.length) {
    if (notesPanel) notesPanel.style.display = "none";
    return;
  }
  if (notesPanel) notesPanel.style.display = "block";
  items.slice(0, 6).forEach((n) => {
    const row = document.createElement("div");
    row.className = "mini-item";
    row.innerHTML = `
      <div class="mini-title">${n.title || "Note"}</div>
      <div class="small">Udløber: ${n.expires_at ? formatPublished(n.expires_at) : "ukendt"}</div>
      <div class="mini-actions">
        <button data-action="analyze" data-id="${n.id}">Analyser</button>
        <button data-action="keep" data-id="${n.id}">Behold</button>
        <button data-action="delete" data-id="${n.id}">Slet</button>
      </div>
    `;
    notesList.appendChild(row);
  });
}

async function createNoteQuick() {
  const content = (noteContentInput?.value || "").trim();
  const title = (noteTitleInput?.value || "").trim();
  if (!content) return;
  let dueAt = null;
  if (noteDueInput && noteDueInput.value) {
    const dt = new Date(noteDueInput.value);
    if (!isNaN(dt.getTime())) {
      dueAt = dt.toISOString();
    }
  }
  const remindEnabled = !!(noteRemindToggle && noteRemindToggle.checked);
  const res = await apiFetch("/notes", {
    method: "POST",
    body: JSON.stringify({ content, title: title || null, due_at: dueAt, remind_enabled: remindEnabled }),
  });
  if (!res) return;
  noteContentInput.value = "";
  if (noteTitleInput) noteTitleInput.value = "";
  if (noteDueInput) noteDueInput.value = "";
  if (noteRemindToggle) noteRemindToggle.checked = false;
  loadNotes();
}

async function loadFiles() {
  if (!filesList) return;
  const data = await safeJson("/files", { method: "GET" }, {});
  if (!data) return;
  const items = data.files || [];
  filesList.innerHTML = "";
  if (!items.length) {
    if (filesPanel) filesPanel.style.display = "block";
    const dict = I18N[getUiLang()];
    filesList.innerHTML = `<div class="mini-empty">${dict.noFiles}</div>`;
    return;
  }
  if (filesPanel) filesPanel.style.display = "block";
  items.slice(0, 5).forEach((f) => {
    const row = document.createElement("div");
    row.className = "mini-item";
    row.innerHTML = `
      <div class="mini-title">${f.original_name || "Fil"}</div>
      <div class="small">Udløber: ${f.expires_at ? formatPublished(f.expires_at) : "ukendt"}</div>
      <div class="mini-actions">
        <button data-action="delete" data-id="${f.id}">Slet</button>
      </div>
    `;
    filesList.appendChild(row);
  });
}

function updateChatVisibility(hasSession) {
  const chat = getChat();
  if (!chat) return;
  const statusRow = getStatusRow();
  if (!hasSession) {
    chat.innerHTML = "";
    hasMessages = false;
    chat.style.display = "none";
    if (statusRow) statusRow.style.display = "flex";
    const greetingBanner = getGreetingBanner();
    if (greetingBanner) greetingBanner.style.display = "block";
    const chatPane = getChatPane();
    if (chatPane) chatPane.classList.add("no-session");
    const sessionPromptRow = getSessionPromptRow();
    if (sessionPromptRow) sessionPromptRow.classList.add("hidden");
    renderSuggestions();
    updateToolsSummary();
    return;
  }
  chat.style.display = "flex";
  if (statusRow) statusRow.style.display = "flex";
  const chatPane = getChatPane();
  if (chatPane) chatPane.classList.remove("no-session");
  const suggestions = getSuggestions();
  if (suggestions) suggestions.classList.add("hidden");
}

function renderSuggestions() {
  if (!suggestions) return;
  const pool = [...SUGGESTIONS_POOL];
  const picks = [];
  while (pool.length && picks.length < 4) {
    const idx = Math.floor(Math.random() * pool.length);
    picks.push(pool.splice(idx, 1)[0]);
  }
  suggestions.innerHTML = "";
  picks.forEach((text) => {
    const btn = document.createElement("button");
    btn.className = "suggestion-btn";
    btn.textContent = text;
    btn.addEventListener("click", async () => {
      if (!currentSessionId) {
        await createSession();
      }
      const input = document.getElementById("prompt");
      if (input) {
        input.value = text;
        input.focus();
      }
    });
    suggestions.appendChild(btn);
  });
  suggestions.classList.remove("hidden");
}

function nowTime(value) {
  if (value) {
    const date = new Date(value);
    if (!isNaN(date.getTime())) {
      return date.toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit" });
    }
  }
  return new Date().toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit" });
}

function renderMessageBody(text, options = {}) {
  const fragment = document.createDocumentFragment();
  
  let useMarkdown = options.markdown && typeof marked !== 'undefined';
  if (useMarkdown) {
    try {
      // Use marked.js for full markdown rendering
      const html = marked.parse(text);
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      while (tempDiv.firstChild) {
        fragment.appendChild(tempDiv.firstChild);
      }
    } catch (err) {
      console.warn('Markdown parsing failed, falling back to plain text', err);
      useMarkdown = false;
    }
  }
  if (!useMarkdown) {
    // Improved plain text rendering with paragraph breaks
    const paragraphs = text.split(/\n\n+/);
    paragraphs.forEach(para => {
      if (para.trim()) {
        const p = document.createElement('p');
        p.innerHTML = para.trim().replace(/\n/g, '<br>');
        fragment.appendChild(p);
      }
    });
  }
  
  // Add copy buttons to code blocks
  const codeBlocks = fragment.querySelectorAll('pre code');
  codeBlocks.forEach(codeBlock => {
    const pre = codeBlock.parentElement;
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.title = 'Copy to clipboard';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(codeBlock.textContent).then(() => {
        copyBtn.textContent = 'Copied';
        setTimeout(() => copyBtn.textContent = 'Copy', 2000);
      });
    };
    pre.style.position = 'relative';
    copyBtn.style.position = 'absolute';
    copyBtn.style.top = '5px';
    copyBtn.style.right = '5px';
    copyBtn.style.background = 'rgba(0,0,0,0.7)';
    copyBtn.style.color = 'white';
    copyBtn.style.border = 'none';
    copyBtn.style.borderRadius = '3px';
    copyBtn.style.cursor = 'pointer';
    copyBtn.style.fontSize = '12px';
    pre.appendChild(copyBtn);
  });
  
  return fragment;
}

function createMessageElement(role, content, meta = {}) {
  const wrapper = document.createElement("div");
  let className = 'msg';
  if (role === 'user') className += ' msg-user';
  else if (role === 'assistant') className += ' msg-assistant';
  else className += ' msg-system';
  wrapper.className = className;

  const header = document.createElement("div");
  header.className = "msg-header";
  const name = document.createElement("span");
  name.className = "msg-author";
  name.textContent = role === "user" ? "Dig" : "Jarvis";
  const time = document.createElement("span");
  time.className = "msg-time";
  time.textContent = meta.when ? nowTime(meta.when) : nowTime();
  if (role === "assistant") {
    const status = document.createElement("span");
    status.className = "msg-status";
    status.textContent = "";
    header.appendChild(status);
  }
  header.appendChild(name);
  header.appendChild(time);

  const body = document.createElement("div");
  body.className = "msg-body";
  const bodyContent = renderMessageBody(content, { markdown: role === 'assistant' });
  body.appendChild(bodyContent);

  wrapper.appendChild(header);
  wrapper.appendChild(body);
  // Removed tooltip for chat messages
  
  return wrapper;
}

function renderChatMessage(msg) {
  const element = createMessageElement(msg.role, msg.content, { when: msg.when });
  const chat = getChat();
  if (chat) chat.appendChild(element);
  const greetingBanner = getGreetingBanner();
  if (greetingBanner) greetingBanner.style.display = "none";
  hasMessages = true;
  scrollChatToBottom();
  return element;
}

function addWeatherCard(payload) {
  const card = document.createElement("div");
  card.className = "card";
  const title = document.createElement("div");
  title.className = "card-title";
  const scope = payload.scope === "tomorrow" ? "i morgen" : payload.scope === "multi" ? "5 dage" : "i dag";
  title.textContent = `${payload.location} — ${scope}`;
  const body = document.createElement("div");
  body.textContent = payload.rendered_text;
  card.appendChild(title);
  card.appendChild(body);
  chat.appendChild(card);
  scrollChatToBottom();
}

function formatPublished(value) {
  if (!value) return "ukendt tidspunkt";
  try {
    const date = new Date(value);
    return new Intl.DateTimeFormat("da-DK", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Europe/Copenhagen",
    }).format(date);
  } catch (err) {
    return "ukendt tidspunkt";
  }
}

function addNewsCards(payload) {
  if (payload.query !== undefined) {
    const header = document.createElement("div");
    header.className = "card";
    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = payload.query ? `Nyheder om ${payload.query}` : "Nyheder";
    header.appendChild(title);
    chat.appendChild(header);
  }
  (payload.items || []).forEach((item) => {
    const card = document.createElement("div");
    card.className = "card";
    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = item.title || "Nyhed";
    const meta = document.createElement("div");
    meta.className = "small";
    const when = formatPublished(item.published_at);
    meta.textContent = `${item.source || "rss"} • ${when}`;
    const snippet = document.createElement("div");
    snippet.textContent = item.snippet || "";
    const link = document.createElement("a");
    link.href = item.url || "#";
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Læs mere";
    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(snippet);
    card.appendChild(link);
    chat.appendChild(card);
  });
}

function appendNewsList(messageEl, payload) {
  if (!messageEl || !payload || !Array.isArray(payload.items)) return;
  const list = document.createElement("div");
  list.className = "news-list";
  payload.items.slice(0, 5).forEach((item, idx) => {
    const row = document.createElement("div");
    row.className = "news-row";
    const title = document.createElement("span");
    title.className = "news-title";
    title.textContent = `${idx + 1}. ${item.title || "Nyhed"}`;
    const sourceText = item.source && item.source !== "web" ? item.source : "";
    let linkLabel = sourceText;
    if (!linkLabel && item.url) {
      try {
        linkLabel = new URL(item.url).hostname.replace("www.", "");
      } catch (err) {
        linkLabel = "medie";
      }
    }
    if (!linkLabel) linkLabel = "medie";
    const link = document.createElement("a");
    link.href = item.url || "#";
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = linkLabel;
    const when = document.createElement("span");
    when.className = "news-date";
    when.textContent = formatPublished(item.published_at);
    row.appendChild(title);
    row.appendChild(document.createTextNode(" — "));
    row.appendChild(link);
    row.appendChild(document.createTextNode(" — "));
    row.appendChild(when);
    list.appendChild(row);
  });
  const body = messageEl.querySelector(".msg-body");
  if (body) {
    body.appendChild(list);
  }
  scrollChatToBottom();
}

function addArticleCard(payload) {
  const card = document.createElement("div");
  card.className = "card";
  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = payload.title || "Artikel";
  const link = document.createElement("a");
  link.href = payload.url || "#";
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "Læs original";
  card.appendChild(title);
  card.appendChild(link);
  chat.appendChild(card);
}

function addFileCard(payload) {
  const card = document.createElement("div");
  card.className = "card";
  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = payload.title || "Fil";
  const link = document.createElement("a");
  link.href = payload.url || "#";
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = payload.label || "Download";
  card.appendChild(title);
  card.appendChild(link);
  chat.appendChild(card);
}

function addImagePreviewCard(payload) {
  const card = document.createElement("div");
  card.className = "card";
  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = payload.title || "Preview";
  const img = document.createElement("img");
  img.className = "image-preview";
  img.src = payload.url || "";
  img.alt = payload.title || "Preview";
  card.appendChild(title);
  card.appendChild(img);
  chat.appendChild(card);
}

async function loadSessions() {
  const res = await apiFetch("/sessions", { method: "GET" });
  if (!res) return;
  setOnlineStatus(true);
  const data = await res.json();
  // Deduplicate sessions by id to prevent duplicates
  const seen = new Set();
  sessionsCache = (data.sessions || []).filter(s => {
    if (seen.has(s.id)) return false;
    seen.add(s.id);
    return true;
  });
  renderSessionList();
  const stored = getLastSession();
  if (!currentSessionId && stored && sessionsCache.find((s) => s.id === stored)) {
    currentSessionId = stored;
    await loadSessionMessages(stored);
  }
  updateChatVisibility(!!currentSessionId);
}

async function loadSessionPrompt() {
  if (!sessionPromptInput) return;
  if (!currentSessionId) return;
  const res = await apiFetch(`/sessions/${currentSessionId}/prompt`, { method: "GET" });
  if (!res) return;
  const data = await res.json();
  sessionPromptInput.value = (data.prompt || "").trim();
}

async function saveSessionPrompt(value) {
  if (!currentSessionId) return;
  await apiFetch(`/sessions/${currentSessionId}/prompt`, {
    method: "PATCH",
    body: JSON.stringify({ prompt: value || "" }),
  });
}

function renderSessionList() {
  const filter = (sessionSearch.value || "").toLowerCase();
  sessionList.innerHTML = "";
  const items = sessionsCache.filter((s) => (s.name || s.id).toLowerCase().includes(filter) && s.id !== currentSessionId);
  const today = new Date();
  const todayKey = today.toDateString();
  const yesterdayKey = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1).toDateString();
  const groups = { today: [], yesterday: [], older: [] };
  const dict = I18N[getUiLang()];
  items.forEach((s) => {
    if (s.id === currentSessionId) return;
    const created = s.created_at ? new Date(s.created_at) : null;
    const key = created && !isNaN(created) ? created.toDateString() : "older";
    if (key === todayKey) groups.today.push(s);
    else if (key === yesterdayKey) groups.yesterday.push(s);
    else groups.older.push(s);
  });
  const appendGroup = (label, list) => {
    if (!list.length) return;
    const title = document.createElement("div");
    title.className = "session-group-title";
    title.textContent = label;
    sessionList.appendChild(title);
    list.forEach((s) => {
      const item = document.createElement("div");
      item.className = `session-item ${s.id === currentSessionId ? "active" : ""}`;
      if (s.created_at) {
        const nameText = (s.name || s.id || "").trim();
        const lastActive = s.last_message_at || s.created_at;
        const label = [
          "Navn:",
          nameText || "Chat",
          "Startet:",
          formatPublished(s.created_at),
          "Senest aktiv:",
          formatPublished(lastActive),
        ].join("\n");
        item.dataset.tooltip = label;
      }
      const initial = document.createElement("div");
      initial.className = "session-initial";
      const label = (s.name || s.id || "").trim();
      initial.textContent = label ? label[0].toUpperCase() : "•";
      const name = document.createElement("div");
      name.className = "session-name";
      name.textContent = s.name || s.id.slice(0, 8);
      const menu = document.createElement("div");
      menu.className = "session-menu";
      menu.innerHTML = `
        <button class="session-menu-btn" aria-label="Menu">…</button>
        <div class="session-menu-panel">
          <button data-action="rename" data-id="${s.id}">Omdøb</button>
          <button data-action="share" data-id="${s.id}">Del</button>
          <button data-action="delete" data-id="${s.id}">Slet</button>
        </div>
      `;
      item.appendChild(initial);
      item.appendChild(name);
      item.appendChild(menu);
      item.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        currentSessionId = s.id;
        storeCurrentSession();
        renderSessionList();
        updateChatVisibility(true);
        loadSessionMessages(s.id);
      });
      sessionList.appendChild(item);
    });
  };
  if (currentSessionId) {
    const current = sessionsCache.find((s) => s.id === currentSessionId);
    if (current) {
      appendGroup(dict.active, [current]);
    }
  }
  appendGroup(dict.today, groups.today);
  appendGroup(dict.earlier, groups.yesterday);
  appendGroup(dict.earlier, groups.older);
  updateActiveSessionLabel();
}

function updateActiveSessionLabel() {
  if (!sessionStatus) return;
  if (!currentSessionId) return;
  const current = sessionsCache.find((s) => s.id === currentSessionId);
  const label = current?.name || currentSessionId.slice(0, 8);
  const dict = I18N[getUiLang()] || I18N.da;
  sessionStatus.textContent = `${dict.active}: ${label}`;
}

function ensureTooltip() {
  if (tooltipEl) return tooltipEl;
  tooltipEl = document.createElement("div");
  tooltipEl.className = "session-tooltip";
  tooltipEl.style.display = "none";
  document.body.appendChild(tooltipEl);
  return tooltipEl;
}

function showTooltip(target) {
  const text = target.dataset.tooltip;
  if (!text) return;
  const tip = ensureTooltip();
  tip.textContent = text;
  tip.style.display = "block";
  const rect = target.getBoundingClientRect();
  const tipRect = tip.getBoundingClientRect();
  let top = rect.top + window.scrollY - tipRect.height - 10; // Above the target
  let left = rect.left + window.scrollX + 6;
  
  // If tooltip would go above viewport or too close to footer, show it below
  const footer = document.querySelector('.app-footer');
  const footerTop = footer ? footer.getBoundingClientRect().top + window.scrollY : window.innerHeight + window.scrollY;
  
  if (top < 10 || (top + tipRect.height) > (footerTop - 20)) {
    top = rect.bottom + window.scrollY + 10;
  }
  
  // Keep tooltip within viewport bounds
  top = Math.max(10, Math.min(top, window.innerHeight + window.scrollY - tipRect.height - 10));
  left = Math.max(10, Math.min(left, window.innerWidth + window.scrollX - tipRect.width - 10));
  
  tip.style.top = `${top}px`;
  tip.style.left = `${left}px`;
}

function hideTooltip() {
  if (tooltipEl) tooltipEl.style.display = "none";
}

async function createSession() {
  const res = await apiFetch("/sessions", {
    method: "POST",
    body: JSON.stringify({ name: "Ny chat" }),
  });
  if (!res) return;
  const data = await res.json();
  if (res.ok) {
    currentSessionId = data.session_id;
    storeCurrentSession();
    await loadSessions();
    await loadSessionPrompt();
    sessionStatus.textContent = "Ny chat oprettet.";
    chat.innerHTML = "";
    hasMessages = false;
    updateChatVisibility(true);
    if (greetingBanner) greetingBanner.style.display = "block";
    updateActiveSessionLabel();
    return data.session_id;
  } else {
    sessionStatus.textContent = data.detail || "Kunne ikke oprette session";
  }
}

async function renameSession(id) {
  const name = prompt("Nyt navn?");
  if (!name) return;
  const res = await apiFetch(`/sessions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
  if (!res) return;
  await loadSessions();
}

async function deleteSession(id) {
  if (!confirm("Slet denne chat?")) return;
  const res = await apiFetch(`/sessions/${id}`, { method: "DELETE" });
  if (!res) return;
  if (id === currentSessionId) {
    currentSessionId = null;
    localStorage.removeItem(LAST_SESSION_KEY);
    chat.innerHTML = "";
    hasMessages = false;
    updateChatVisibility(false);
  }
  await loadSessions();
}

async function loadSessionMessages(id) {
  const chat = getChat();
  if (chat) chat.innerHTML = "";
  currentSessionId = id;
  storeCurrentSession();
  await loadSessionPrompt();
  updateActiveSessionLabel();
  const res = await apiFetch(`/share/${id}`, { method: "GET" });
  if (!res) return;
  const data = await res.json();
  (data.messages || []).forEach((m) => {
    const role = m.role === "user" ? "user" : "assistant";
    renderChatMessage({ role, content: m.content, when: m.created_at });
  });
  hasMessages = (data.messages || []).length > 0;
  const greetingBanner = getGreetingBanner();
  if (greetingBanner) greetingBanner.style.display = hasMessages ? "none" : "block";
  scrollChatToBottom();
}

async function shareSession(id) {
  const url = `${window.location.origin}/share/${id}`;
  try {
    await navigator.clipboard.writeText(url);
    sessionStatus.textContent = "Share-link kopieret.";
  } catch (err) {
    sessionStatus.textContent = url;
  }
}


sessionList.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  if (btn.classList.contains("session-menu-btn")) {
    const menu = btn.closest(".session-menu");
    closeSessionMenus(menu);
    menu.classList.toggle("open");
    return;
  }
  const id = btn.dataset.id;
  const action = btn.dataset.action;
  if (action === "rename") renameSession(id);
  if (action === "delete") deleteSession(id);
  if (action === "share") shareSession(id);
  closeSessionMenus();
});

sessionList.addEventListener("mouseover", (e) => {
  const item = e.target.closest(".session-item");
  if (!item) return;
  showTooltip(item);
});

sessionList.addEventListener("mousemove", (e) => {
  if (!tooltipEl || tooltipEl.style.display === "none") return;
  const tipRect = tooltipEl.getBoundingClientRect();
  let top = e.clientY + window.scrollY - tipRect.height - 10; // Above cursor
  let left = e.clientX + window.scrollX + 14;
  
  // If tooltip would go above viewport or too close to footer, show it below
  const footer = document.querySelector('.app-footer');
  const footerTop = footer ? footer.getBoundingClientRect().top + window.scrollY : window.innerHeight + window.scrollY;
  
  if (top < 10 || (top + tipRect.height) > (footerTop - 20)) {
    top = e.clientY + window.scrollY + 20;
  }
  
  // Keep tooltip within viewport bounds
  top = Math.max(10, Math.min(top, window.innerHeight + window.scrollY - tipRect.height - 10));
  left = Math.max(10, Math.min(left, window.innerWidth + window.scrollX - tipRect.width - 10));
  
  tooltipEl.style.top = `${top}px`;
  tooltipEl.style.left = `${left}px`;
});

if (sessionList) {
  sessionList.addEventListener("mouseout", (e) => {
    const item = e.target.closest(".session-item");
    if (!item) return;
    hideTooltip();
  });
}

async function loadModel() {
  const res = await apiFetch("/models", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const modelSelect = getModelSelect();
  if (modelSelect) modelSelect.innerHTML = "";
  const models = data.models && data.models.length ? [...data.models] : [];
  try {
    const confRes = await apiFetch("/config", { method: "GET" });
    if (confRes) {
      const conf = await confRes.json();
      if (conf.model && !models.includes(conf.model)) {
        models.unshift(conf.model);
      }
    }
  } catch (err) {
    // ignore
  }
  if (!models.length) {
    models.push(data.model || "local");
  }
  models.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    if (modelSelect) modelSelect.appendChild(opt);
  });
  const saved = localStorage.getItem("jarvisModel");
  if (saved && modelSelect) {
    modelSelect.value = saved;
  }
}

async function loadFooter() {
  const res = await apiFetch("/settings/footer", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  if (footerText) footerText.textContent = data.text || "Jarvis v.1 @ 2026";
  if (footerSupport) footerSupport.href = data.support_url || "#";
  if (footerContact) footerContact.href = data.contact_url || "#";
  if (footerLicense) {
    footerLicense.textContent = data.license_text || "Open‑source licens";
    footerLicense.href = data.license_url || "#";
  }
}

async function loadBrand() {
  try {
    const res = await fetch("/settings/brand");
    if (!res.ok) return;
    const data = await res.json();
    const topLabel = (data.top || "Jarvis").trim();
    const coreLabel = (data.name || "Jarvis").trim();
    brandCoreLabel = coreLabel || "Jarvis";
    safeSetText(getBrandTop(), topLabel || "Jarvis");
    safeSetText(getBrandCore(), brandCoreLabel);
    safeSetText(getBrandShort(), brandCoreLabel.charAt(0).toUpperCase() || "J");
    const statusBadge = getStatusBadge();
    if (statusBadge) {
      setStatus(statusBadge.textContent || "Klar");
    } else {
      setStatus("Klar");
    }
    updatePromptPlaceholder();
  } catch (err) {
    console.warn("loadBrand failed", err);
    // Set defaults even if fetch fails
    brandCoreLabel = "Jarvis";
    safeSetText(getBrandTop(), "Jarvis");
    safeSetText(getBrandCore(), "Jarvis");
    safeSetText(getBrandShort(), "J");
    setStatus("Klar");
    updatePromptPlaceholder();
  }
}

function updateToolsSummary() {
  if (!toolsSummary) return;
  const tools = [
    { id: "toolNews", label: "Nyheder" },
    { id: "toolWeather", label: "Vejr" },
    { id: "toolSearch", label: "Web" },
    { id: "toolCurrency", label: "Valuta" },
    { id: "toolImage", label: "Billede" },
  ];
  if (isAdminUser) {
    tools.push(
      { id: "toolSystem", label: "System" },
      { id: "toolPing", label: "Ping" },
      { id: "toolProcess", label: "Processer" }
    );
  }
  toolsSummary.innerHTML = "";
  const label = document.createElement("span");
  label.textContent = I18N[getUiLang()].tools;
  toolsSummary.appendChild(label);
  tools.forEach((tool) => {
    const checkbox = document.getElementById(tool.id);
    const on = checkbox ? checkbox.checked : false;
    const chip = document.createElement("span");
    chip.className = `chip ${on ? "on" : "off"}`;
    chip.textContent = tool.label;
    chip.dataset.tool = tool.id;
    chip.addEventListener("click", () => {
      if (checkbox) {
        checkbox.checked = !checkbox.checked;
        updateToolsSummary();
      }
    });
    toolsSummary.appendChild(chip);
  });
}

function updateToolDots() {
  return;
}

async function safeApiFetch(url, opts = {}) {
  try {
    return await apiFetch(url, opts);
  } catch (err) {
    console.warn("safeApiFetch failed:", url, err);
    return null;
  }
}

async function safeApiFetchJson(url, opts = {}, fallback = {}) {
  const res = await safeApiFetch(url, opts);
  if (!res) return fallback;
  if (res.adminDenied) return { adminDenied: true };
  try {
    return await res.json();
  } catch (err) {
    console.warn("safeApiFetchJson failed:", url, err);
    return fallback;
  }
}

// New safeJson helper using existing apiFetch
async function safeJson(url, fallback = null, opts = {}) {
  try {
    const res = await apiFetch(url, opts);
    if (!res) return fallback;
    if (res.adminDenied) return { adminDenied: true };
    if (typeof res.json === "function") {
      return await res.json();
    }
    return res;
  } catch (e) {
    console.warn("fetch failed", url, e);
    return fallback;
  }
}

async function safeFetchJson(url, opts = {}, fallback = {}) {
  try {
    const res = await fetch(url, opts);
    if (!res || !res.ok) return fallback;
    return await res.json();
  } catch (err) {
    console.warn("safeFetchJson failed:", url, err);
    return fallback;
  }
}

// Safe wrapper for UI init steps — ensures one failing async task doesn't abort startup
async function safe(fn, label) {
  try {
    if (typeof fn === "function") await fn();
  } catch (err) {
    console.warn("UI init failed:", label, err);
  }
}

// Lightweight alias to load settings/public data (keeps previous behaviour)
async function loadSettings() {
  if (typeof loadRightPanels === "function") {
    await loadRightPanels();
  } else {
    try {
      const res = await fetch('/settings/public');
      if (!res.ok) return;
      const data = await res.json();
      window.PUBLIC_SETTINGS = data;
      window.__updatesLog = (data.updates_log || data.updates_auto || []).join('\n');
      window.__commandsList = data.commands || [];
      // Handle banner
      if (topBanner) {
        if (data.banner && data.banner.trim()) {
          bannerTrack.textContent = data.banner.trim();
          topBanner.classList.remove('hidden');
        } else {
          topBanner.classList.add('hidden');
        }
      }
    } catch (err) {
      // ignore
    }
  }
}

function updateStreamChip() {
  const streamDot = getStreamDot();
  if (!streamDot) return;
  const streamToggle = getStreamToggle();
  const on = streamToggle && streamToggle.checked;
  streamDot.classList.remove("on", "off");
  streamDot.classList.add(on ? "on" : "off");
}

function showQuotaNotice(text) {
  const quotaNotice = getQuotaNotice();
  if (!quotaNotice || !text) return;
  const pctMatch = text.match(/(\d+)%/);
  if (pctMatch) {
    quotaNotice.textContent = `⚠ Kvota ${pctMatch[1]}%`;
  } else if (/opbrugt/i.test(text)) {
    quotaNotice.textContent = "⚠ Kvota 0%";
  } else {
    quotaNotice.textContent = "⚠ Kvota";
  }
  quotaNotice.classList.add("show");
}

async function loadQuotaBar() {
  if (!quotaFill || !quotaText) return;
  const res = await apiFetch("/account/quota", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const total = Number(data.total_mb || 0);
  const used = Number(data.used_mb || 0);
  if (isAdminUser || total === 0) {
    quotaText.textContent = "Ubegraenset";
    quotaFill.style.width = "100%";
    return;
  }
  const pct = total > 0 ? Math.min(100, Math.max(0, (used / total) * 100)) : 0;
  quotaText.textContent = `${used} / ${total} MB`;
  quotaFill.style.width = `${pct}%`;
}

function setOnlineStatus(isOnline) {
  // Support three-state: true (online), false (offline), null (unknown)
  const lang = typeof getUiLang === "function" ? getUiLang() : "da";
  if (jarvisDot) {
    jarvisDot.classList.remove("online", "offline", "unknown");
    if (isOnline === true) jarvisDot.classList.add("online");
    else if (isOnline === false) jarvisDot.classList.add("offline");
    else jarvisDot.classList.add("unknown");
  }
  if (onlinePill) {
    onlinePill.classList.remove("online", "offline", "unknown");
    if (isOnline === true) {
      onlinePill.classList.add("online");
      onlinePill.textContent = "Online";
    } else if (isOnline === false) {
      onlinePill.classList.add("offline");
      onlinePill.textContent = "Offline";
    } else {
      onlinePill.classList.add("unknown");
      onlinePill.textContent = lang === "en" ? "Unknown" : "Ukendt";
    }
  }
}

async function loadProfile() {
  const res = await apiFetch("/account/profile", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  // Only update via authStore
  if (window.authStore) {
    window.authStore.setAuthState({
      isAuthenticated: true,
      isAdmin: !!data.is_admin,
      lastAuthCheckAt: Date.now(),
    });
  }
  if (data.city) {
    localStorage.setItem("jarvisCity", data.city);
  }
  updateGreeting((data.full_name || data.username || "").split(" ")[0]);
  const modeLabel = getModeLabel();
  if (modeLabel) modeLabel.style.display = "none";
  const modeSelect = getModeSelect();
  if (modeSelect) {
    modeSelect.style.display = "none";
    modeSelect.disabled = true;
  }
  const micBtn = getMicBtn();
  if (micBtn) {
    micBtn.style.display = isAdminUser ? "inline-flex" : "none";
  }
  const modeChip = getModeChip();
  if (modeChip) {
    modeChip.classList.add("hidden");
    modeChip.style.display = "none";
  }
  setupMic();
  checkMaintenance();
  loadRightLogs();
  loadRightNotes();
  loadRightTickets();
  document.querySelectorAll(".admin-only").forEach((el) => {
    if (!isAdminUser) {
      el.classList.add("disabled");
      const input = el.querySelector("input");
      if (input) {
        input.checked = false;
        input.disabled = true;
      }
    } else {
      el.classList.remove("disabled");
      const input = el.querySelector("input");
      if (input) input.disabled = false;
    }
  });
  updateToolsSummary();
  updateToolDots();
  loadQuotaBar();
  if (quotaBar) quotaBar.style.display = isAdminUser ? "none" : "block";
  if (quotaRequestBtn) quotaRequestBtn.style.display = isAdminUser ? "none" : "block";
}

function setupMic() {
  const micBtn = getMicBtn();
  if (!micBtn) return;
  if (!isAdminUser) return;
  if (micReady) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.disabled = true;
    micBtn.title = "Talegenkendelse er ikke understottet i denne browser.";
    return;
  }
  micRecognizer = new SpeechRecognition();
  micRecognizer.lang = "da-DK";
  micRecognizer.interimResults = false;
  micRecognizer.maxAlternatives = 1;

  micRecognizer.onresult = (event) => {
    const transcript = event?.results?.[0]?.[0]?.transcript || "";
    if (transcript.trim()) {
      sendMessage(transcript);
    }
  };
  micRecognizer.onerror = (event) => {
    setStatus(`Tale-fejl: ${event?.error || "ukendt"}`);
  };
  micRecognizer.onend = () => {
    micActive = false;
    const micBtn = getMicBtn();
    if (micBtn) micBtn.classList.remove("active");
    setStatus("Klar");
  };

  micBtn.addEventListener("click", () => {
    if (!isAdminUser || !micRecognizer) return;
    if (micActive) {
      micRecognizer.stop();
      return;
    }
    micActive = true;
    const micBtn = getMicBtn();
    if (micBtn) micBtn.classList.add("active");
    setStatus("JARVIS lytter...");
    micRecognizer.start();
  });
  micReady = true;
}

async function sendMessage(textOverride = null) {
  const input = getPromptInput();
  if (!input) return;
  const text = (textOverride ?? input.value).trim();
  if (!text) return;
  const quotaNotice = getQuotaNotice();
  if (quotaNotice) quotaNotice.classList.remove("show");
  const now = Date.now();
  if (text === lastSent.text && now - lastSent.ts < 2000) {
    return;
  }
  lastSent = { text, ts: now };
  if (sendMessage.inFlight) return;
  sendMessage.inFlight = true;
  if (!currentSessionId) {
    await createSession();
  }
  input.value = "";
  setStatus("JARVIS tænker...");
  renderChatMessage({ role: "user", content: text });

  const sessionId = currentSessionId;
  const modelSelect = getModelSelect();
  const streamToggle = getStreamToggle();
  const payload = {
    model: (modelSelect && modelSelect.value) || "local",
    stream: (streamToggle && streamToggle.checked) || false,
    messages: [{ role: "user", content: text }],
  };
  payload.ui_lang = getUiLang();
  const toolsAllowed = [];
  toolsAllowed.push("time");
  if (document.getElementById("toolNews")?.checked) toolsAllowed.push("news");
  if (document.getElementById("toolWeather")?.checked) toolsAllowed.push("weather");
  if (document.getElementById("toolSearch")?.checked) toolsAllowed.push("search");
  if (document.getElementById("toolCurrency")?.checked) toolsAllowed.push("currency");
  if (document.getElementById("toolImage")?.checked) toolsAllowed.push("image");
  if (isAdminUser && document.getElementById("toolSystem")?.checked) toolsAllowed.push("system");
  if (isAdminUser && document.getElementById("toolPing")?.checked) toolsAllowed.push("ping");
  if (isAdminUser && document.getElementById("toolProcess")?.checked) toolsAllowed.push("process");
  payload.tools_allowed = toolsAllowed;

  if (!payload.stream) {
    const res = await apiFetch("/v1/chat/completions", {
      method: "POST",
      headers: { "X-Session-Id": sessionId || "" },
      body: JSON.stringify(payload),
    });
    if (!res) return;
    const data = await res.json();
    if (data?.data?.type === "mixed") {
      if (data?.data?.weather && data?.rendered_text) {
        addWeatherCard({
          location: data.data.weather.location,
          scope: data.data.weather.scope,
          rendered_text: data.rendered_text,
        });
      }
      if (data?.data?.news?.type === "news") {
        addNewsCards(data.data.news);
      }
    }
    if (data?.data?.type === "weather" && data?.rendered_text) {
      addWeatherCard({ location: data.data.location, scope: data.data.scope, rendered_text: data.rendered_text });
    }
    if (data?.data?.type === "news") {
      addNewsCards(data.data);
    }
    if (data?.data?.type === "article") {
      addArticleCard(data.data);
    }
    if (data?.data?.type === "file") {
      addFileCard(data.data);
    }
    if (data?.data?.type === "image_preview") {
      addImagePreviewCard(data.data);
    }
    const content = data.choices?.[0]?.message?.content || "";
    if (data?.meta?.quota_warning) {
      showQuotaNotice(data.meta.quota_warning);
    }
    if (!content.trim()) {
      setStatus("JARVIS svarer tomt — prøv igen.");
    }
    const assistantMsg = renderChatMessage({ role: "assistant", content, when: data.server_time });
    if (data?.data?.type === "news") {
      appendNewsList(assistantMsg, data.data);
    }
    if (data?.data?.type === "mixed" && data?.data?.news?.type === "news") {
      appendNewsList(assistantMsg, data.data.news);
    }
    setStatus("Klar");
    if (currentSessionId) {
      loadSessionMessages(currentSessionId);
    }
    loadQuotaBar();
    loadExpiryNotice();
    sendMessage.inFlight = false;
    return;
  }

  const res = await apiFetch("/v1/chat/completions", {
    method: "POST",
    headers: { "X-Session-Id": sessionId || "" },
    body: JSON.stringify(payload),
  });
  if (!res) return;

  const assistantMsg = renderChatMessage({ role: "assistant", content: "" });
  let pendingNews = null;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";
  let hadDelta = false;
  const body = assistantMsg.querySelector(".msg-body");
  let streamingText = "";
  
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.replace("event:", "").trim();
        continue;
      }
      if (!line.startsWith("data:")) continue;
      const dataLine = line.replace("data:", "").trim();
      if (dataLine === "[DONE]") {
        chatStatus.textContent = "";
        setStatus("Klar");
        // Finalize with markdown rendering
        if (body) {
          body.innerHTML = "";
          const bodyContent = renderMessageBody(streamingText, { markdown: true });
          body.appendChild(bodyContent);
        }
        if (pendingNews) {
          appendNewsList(assistantMsg, pendingNews);
        }
        if (currentSessionId) {
          loadSessionMessages(currentSessionId);
        }
        loadQuotaBar();
        loadExpiryNotice();
        sendMessage.inFlight = false;
        return;
      }
      if (currentEvent === "status") {
        try {
          const st = JSON.parse(dataLine);
          const dict = I18N[getUiLang()] || I18N.da;
          if (st.state === "using_tool") {
            const tool = st.tool || "";
            const map = {
              news: dict.statusSearching,
              weather: dict.statusSearching,
              search: dict.statusSearching,
              currency: dict.statusSearching,
              system: dict.statusSearching,
              ping: dict.statusSearching,
              process: dict.statusSearching,
              image: dict.statusSearching,
            };
            setStatus(map[tool] || dict.statusSearching);
            if (chatStatus) chatStatus.textContent = "";
          } else if (st.state === "writing") {
            setStatus(dict.statusWriting);
            if (chatStatus) chatStatus.textContent = "▊";
          } else if (st.state === "thinking") {
            setStatus(dict.statusThinking);
            if (chatStatus) chatStatus.textContent = "";
          } else if (st.state === "idle") {
            setStatus(dict.statusReady);
            if (chatStatus) chatStatus.textContent = "";
          }
        } catch (err) {
          setStatus("JARVIS arbejder...");
          if (chatStatus) chatStatus.textContent = "";
        }
        continue;
      }
      if (currentEvent === "meta") {
        try {
          const meta = JSON.parse(dataLine);
          if (meta.meta?.quota_warning) {
            showQuotaNotice(meta.meta.quota_warning);
          }
          if (meta.data?.type === "mixed") {
            if (meta.data.weather && meta.rendered_text) {
              addWeatherCard({
                location: meta.data.weather.location,
                scope: meta.data.weather.scope,
                rendered_text: meta.rendered_text,
              });
            }
            if (meta.data.news?.type === "news") {
              addNewsCards(meta.data.news);
              pendingNews = meta.data.news;
            }
          }
          if (meta.data?.type === "news") {
            addNewsCards(meta.data);
            pendingNews = meta.data;
          }
          if (meta.data?.type === "weather" && meta.rendered_text) {
            addWeatherCard({ location: meta.data.location, scope: meta.data.scope, rendered_text: meta.rendered_text });
          }
          if (meta.data?.type === "file") {
            addFileCard(meta.data);
          }
          if (meta.data?.type === "image_preview") {
            addImagePreviewCard(meta.data);
          }
          if (meta.data?.type === "article") {
            addArticleCard(meta.data);
          }
        } catch (err) {
          // ignore
        }
        continue;
      }
      // Reset event context if a normal chunk arrives without event header.
      if (dataLine.startsWith("{") && dataLine.includes("\"choices\"")) {
        currentEvent = "message";
      }
      try {
        const chunk = JSON.parse(dataLine);
        const delta = chunk.choices?.[0]?.delta?.content || "";
        if (delta) {
          streamingText += delta;
          // Update display with plain text during streaming
          body.textContent = streamingText;
          scrollChatToBottom();
          hadDelta = true;
        }
      } catch (err) {
        chatStatus.textContent = "Streaming-fejl";
      }
    }
  }
  if (!hadDelta) {
    setStatus("JARVIS svarer tomt — prøv igen.");
  }
  sendMessage.inFlight = false;
}

if (sessionPromptRow) {
  sessionPromptRow.classList.add("hidden");
}
const modeSelect = getModeSelect();
if (modeSelect) {
  modeSelect.addEventListener("change", () => {
    localStorage.setItem("jarvisMode", modeSelect.value);
    updateModeChipLabel();
  });
}
const modelSelect = getModelSelect();
if (modelSelect) {
  modelSelect.addEventListener("change", () => {
    localStorage.setItem("jarvisModel", modelSelect.value);
  });
}
if (responseModeSelect) {
  responseModeSelect.addEventListener("change", () => {
    const mode = responseModeSelect.value;
    localStorage.setItem("jarvisResponseMode", mode);
    let prompt = "";
    if (mode === "short") prompt = "svar kort";
    else if (mode === "deep") prompt = "uddyb";
    else if (mode === "normal") prompt = "normal svar";
    if (prompt) {
      sendMessage(prompt);
    }
  });
  // Load saved mode
  const savedMode = localStorage.getItem("jarvisResponseMode") || "normal";
  responseModeSelect.value = savedMode;
}

// --- Status polling: robust check of /status endpoint to update online badge ---
async function loadStatus() {
  try {
    const res = await fetch('/status', { credentials: 'include' });
    if (!res.ok) throw new Error('status fetch failed');
    const data = await res.json();
    const online = data?.online === true || data?.ok === true;
    if (onlinePill) {
      onlinePill.textContent = online ? 'Online' : 'Offline';
      onlinePill.classList.remove('online', 'offline');
      onlinePill.classList.add(online ? 'online' : 'offline');
    }
    if (jarvisDot) {
      jarvisDot.classList.remove('online', 'offline');
      jarvisDot.classList.add(online ? 'online' : 'offline');
    }
    window.__jarvis_status_failures = 0;
  } catch (err) {
    window.__jarvis_status_failures = (window.__jarvis_status_failures || 0) + 1;
    if (window.__jarvis_status_failures > 3) {
      if (onlinePill) {
        onlinePill.textContent = 'Offline';
        onlinePill.classList.remove('online');
        onlinePill.classList.add('offline');
      }
      if (jarvisDot) {
        jarvisDot.classList.remove('online');
        jarvisDot.classList.add('offline');
      }
    }
  }
}

try {
  loadStatus();
  setInterval(loadStatus, 10000);
} catch (e) {
  console.warn('Status polling failed to start', e);
}

sessionSearch.addEventListener("input", renderSessionList);

// Populate developer info box with runtime details from /v1/info
async function loadDevInfo() {
  const el = document.getElementById('devInfo');
  if (!el) return;
  try {
    const res = await fetch('/v1/info');
    if (!res.ok) throw new Error('Failed');
    const info = await res.json();
    const text = `build:${info.build_id} · app:${info.app_html_exists ? 'ok' : 'missing'} · root:${info.project_root}`;
    el.textContent = text;
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
  } catch (err) {
    // keep hidden on failure
    el.classList.add('hidden');
  }
}

try { loadDevInfo(); } catch (e) { /* ignore */ }
// Toggle behavior for dev info box: expand/collapse and populate full details
try {
  const toggle = document.getElementById('devInfoToggle');
  const box = document.getElementById('devInfo');
  const compact = document.getElementById('devInfoCompact');
  const full = document.getElementById('devInfoFull');
  function renderFull(info) {
    if (!full) return;
    const lines = [];
    lines.push(`build_id: ${info.build_id}`);
    lines.push(`server_file: ${info.server_file}`);
    lines.push(`project_root: ${info.project_root}`);
    lines.push(`app_html_exists: ${info.app_html_exists}`);
    full.textContent = lines.join('\n');
  }
  if (toggle && box) {
    toggle.addEventListener('click', async (e) => {
      e.preventDefault();
      const expanded = box.classList.toggle('expanded');
      toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      if (expanded) {
        // ensure we have latest info
        try {
          const res = await fetch('/v1/info');
          if (res.ok) {
            const info = await res.json();
            renderFull(info);
            compact.textContent = `build:${info.build_id} · app:${info.app_html_exists? 'ok':'missing'} · root:${info.project_root}`;
          }
        } catch (err) {
          // ignore
        }
        full.classList.remove('hidden');
        full.setAttribute('aria-hidden', 'false');
      } else {
        full.classList.add('hidden');
        full.setAttribute('aria-hidden', 'true');
      }
    });
  }
} catch (err) {
  // ignore
}

const uploadBtn = getUploadBtn();
const uploadSidebarBtn = getUploadSidebarBtn();
const imageUploadBtn = getImageUploadBtn();
const imageUploadInput = getImageUploadInput();
const newChatInline = getNewChatInline();
const toolsSummary = getToolsSummary();
const globalSearch = getGlobalSearch();
const globalSearchResults = getGlobalSearchResults();

document.getElementById("newChatBtn").addEventListener("click", createSession);
if (newChatInline) {
  newChatInline.addEventListener("click", createSession);
}
document.getElementById("sendBtn").addEventListener("click", () => sendMessage());
const uploadInput = getUploadInput();
if (uploadBtn && uploadInput) {
  uploadBtn.addEventListener("click", () => uploadInput.click());
}
if (uploadSidebarBtn && uploadInput) {
  uploadSidebarBtn.addEventListener("click", () => uploadInput.click());
}
if (imageUploadBtn && imageUploadInput) {
  imageUploadBtn.addEventListener("click", () => imageUploadInput.click());
}
if (uploadInput) {
  uploadInput.addEventListener("change", (e) => {
    const files = [...(e.target.files || [])];
    files.forEach(uploadFile);
    uploadInput.value = "";
  });
}
if (imageUploadInput) {
  imageUploadInput.addEventListener("change", (e) => {
    const files = [...(e.target.files || [])];
    files.forEach(uploadFile);
    imageUploadInput.value = "";
  });
}
document.getElementById("searchBtn").addEventListener("click", () => {
  sessionSearch.focus();
  sessionSearch.select();
  renderSessionList();
});
document.getElementById("adminBtn").addEventListener("click", () => {
  window.location.href = "/admin";
});
document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  stopEventsStream();
  window.location.href = "/login";
});
const docsBtn = document.getElementById("docsBtn");
if (docsBtn) {
  docsBtn.addEventListener("click", () => {
    window.location.href = "/docs";
  });
}
const ticketsBtn = document.getElementById("ticketsBtn");
if (ticketsBtn) {
  ticketsBtn.addEventListener("click", () => {
    window.location.href = "/tickets";
  });
}
const accountBtn = document.getElementById("accountBtn");
if (accountBtn) {
  accountBtn.addEventListener("click", (e) => {
    e.preventDefault();
    openSettingsModal();
  });
}
if (quotaRequestBtn) {
  quotaRequestBtn.addEventListener("click", async () => {
    const quotaRes = await apiFetch("/account/quota", { method: "GET" });
    if (!quotaRes) return;
    const quota = await quotaRes.json();
    const message = `Jeg anmoder om mere plads. Brugt: ${quota.used_mb} MB af ${quota.total_mb} MB.`;
    const payload = { title: "Quota anmodning", message, priority: "moderat" };
    const res = await apiFetch("/api/tickets", { method: "POST", body: JSON.stringify(payload) });
    if (!res) return;
    const data = await res.json();
    sessionStatus.textContent = res.ok ? "Anmodning sendt til admin." : data.detail || "Kunne ikke sende anmodning.";
  });
}

document.addEventListener("click", (e) => {
  if (!e.target.closest(".session-menu")) {
    closeSessionMenus();
  }
});
const collapseBtn = document.getElementById("collapseBtn");
if (collapseBtn) {
  const saved = localStorage.getItem("jarvisSidebar");
  if (saved === "collapsed") {
    document.body.classList.add("sidebar-collapsed");
  }
  collapseBtn.addEventListener("click", () => {
    document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem(
      "jarvisSidebar",
      document.body.classList.contains("sidebar-collapsed") ? "collapsed" : "open"
    );
  });
}

document.getElementById("prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Composer textarea autosize
const promptTextarea = getPromptInput();
if (promptTextarea) {
  // Auto-resize textarea
  function autoResizeTextarea() {
    if (!promptTextarea) return;
    promptTextarea.style.height = 'auto';
    promptTextarea.style.height = Math.min(promptTextarea.scrollHeight, 200) + 'px';
  }

  promptTextarea.addEventListener('input', autoResizeTextarea);
  promptTextarea.addEventListener('focus', autoResizeTextarea);
  promptTextarea.addEventListener('blur', () => {
    if (!promptTextarea.value.trim()) {
      promptTextarea.style.height = '20px';
    }
  });

  // Initial resize
  autoResizeTextarea();
}

if (typeof noteCreateBtn !== "undefined" && noteCreateBtn) {
  noteCreateBtn.addEventListener("click", createNoteQuick);
}
if (noteToggleBtn && noteCreateWrap) {
  noteToggleBtn.addEventListener("click", () => {
    noteCreateWrap.classList.toggle("hidden");
  });
}
if (filesToggleBtn && filesListWrap) {
  filesToggleBtn.addEventListener("click", () => {
    filesListWrap.classList.toggle("hidden");
  });
}
if (sessionPromptSave && sessionPromptInput) {
  sessionPromptSave.addEventListener("click", async () => {
    await saveSessionPrompt(sessionPromptInput.value.trim());
    sessionStatus.textContent = "Session‑personlighed gemt.";
  });
}
if (sessionPromptClear && sessionPromptInput) {
  sessionPromptClear.addEventListener("click", async () => {
    sessionPromptInput.value = "";
    await saveSessionPrompt("");
    sessionStatus.textContent = "Session‑personlighed nulstillet.";
  });
}
if (noteContentInput) {
  noteContentInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      createNoteQuick();
    }
  });
}

if (notesList) {
  notesList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const id = btn.dataset.id;
    const action = btn.dataset.action;
    if (action === "analyze") {
      const input = document.getElementById("prompt");
      if (input) {
        input.value = `analyser note ${id}`;
        input.focus();
      }
    }
    if (action === "keep") {
      await apiFetch(`/notes/${id}/keep`, { method: "POST" });
      loadNotes();
    }
    if (action === "delete") {
      await apiFetch(`/notes/${id}`, { method: "DELETE" });
      loadNotes();
    }
  });
}

if (filesList) {
  filesList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const id = btn.dataset.id;
    const action = btn.dataset.action;
    if (action === "delete") {
      await apiFetch(`/files/${id}`, { method: "DELETE" });
      loadFiles();
    }
  });
}

const chatPane = getChatPane();
if (chatPane && uploadInput) {
  chatPane.addEventListener("dragover", (e) => {
    e.preventDefault();
    chatPane.classList.add("drop-active");
  });
  chatPane.addEventListener("dragleave", () => chatPane.classList.remove("drop-active"));
  chatPane.addEventListener("drop", (e) => {
    e.preventDefault();
    chatPane.classList.remove("drop-active");
    const files = [...(e.dataTransfer?.files || [])];
    files.forEach(uploadFile);
  });
}

if (globalSearch) {
  let searchTimer = null;
  globalSearch.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const value = e.target.value || "";
    searchTimer = setTimeout(() => handleGlobalSearch(value), 150);
  });
}

document.addEventListener("click", (e) => {
  if (!globalSearchResults || !globalSearch) return;
  if (e.target === globalSearch || globalSearchResults.contains(e.target)) return;
  globalSearchResults.classList.remove("open");
});

const promptInput = getPromptInput();
if (promptInput) {
  const adjustHeight = () => {
    promptInput.style.height = "auto";
    const scrollHeight = promptInput.scrollHeight;
    const newHeight = Math.min(Math.max(scrollHeight, 20), 200); // Min 20px, max 200px
    promptInput.style.height = `${newHeight}px`;
  };
  
  promptInput.addEventListener("input", adjustHeight);
  
  // Also adjust on focus/blur to handle empty state
  promptInput.addEventListener("focus", adjustHeight);
  promptInput.addEventListener("blur", () => {
    if (!promptInput.value.trim()) {
      promptInput.style.height = "20px";
    }
  });
  
  promptInput.addEventListener("input", () => {
    const greetingBanner = getGreetingBanner();
    if (!greetingBanner) return;
    if (promptInput.value.trim().length > 0) {
      greetingBanner.style.display = "none";
      if (!currentSessionId && !autoSessionInFlight) {
        autoSessionInFlight = true;
        createSession().finally(() => {
          autoSessionInFlight = false;
        });
      }
    } else if (!hasMessages) {
      greetingBanner.style.display = "block";
    }
  });
}

if (toolsSummary) {
  toolsSummary.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const id = chip.dataset.tool;
    const checkbox = id ? document.getElementById(id) : null;
    if (!checkbox || checkbox.disabled) return;
    checkbox.checked = !checkbox.checked;
    updateToolsSummary();
  });
}

const streamChip = getStreamChip();
if (streamChip) {
  streamChip.addEventListener("click", () => {
    const streamToggle = getStreamToggle();
    if (!streamToggle) return;
    streamToggle.checked = !streamToggle.checked;
    updateStreamChip();
  });
}
const personaChip = getPersonaChip();
if (personaChip) {
  personaChip.addEventListener("click", () => {
    const sessionPromptRow = getSessionPromptRow();
    if (!sessionPromptRow) return;
    sessionPromptRow.classList.toggle("hidden");
  });
}

const modeChip = getModeChip();
if (modeChip) {
  modeChip.classList.add("hidden");
  modeChip.style.display = "none";
}

// admin/logout handled via rail buttons

const modeSelect2 = getModeSelect();
if (modeSelect2) {
  modeSelect2.style.display = "none";
  modeSelect2.disabled = true;
}
const langSelect = getLangSelect();
if (langSelect) {
  const savedLang = sessionStorage.getItem("jarvisLangSession") || localStorage.getItem("jarvisLang");
  const browserLang = (navigator.language || "").toLowerCase();
  const autoLang = browserLang.startsWith("da") ? "da" : "en";
  applyUiLang(savedLang || autoLang);
  langSelect.addEventListener("change", (e) => applyUiLang(e.target.value));
}
if (themeSelect) {
  initTheme();
  themeSelect.addEventListener("change", (e) => applyUiTheme(e.target.value));
} else {
  initTheme();
}

const notificationsBtn = getNotificationsBtn();
if (notificationsBtn) {
  notificationsBtn.addEventListener("click", showNotificationsDropdown);
}
const notificationsDropdown = getNotificationsDropdown();
if (notificationsDropdown) {
  hideEl(notificationsDropdown);
}
const notificationsMarkAllRead = getNotificationsMarkAllRead();
if (notificationsMarkAllRead) {
  notificationsMarkAllRead.addEventListener("click", markAllNotificationsRead);
}

// Tools dropdown/button
const toolsBtn = getToolsBtn();
let toolsDropdown = null;
function ensureToolsDropdown() {
  toolsDropdown = toolsDropdown || getToolsDropdown();
  if (toolsDropdown) hideEl(toolsDropdown);
  return toolsDropdown;
}
ensureToolsDropdown();

// Click outside to close notifications dropdown
document.addEventListener("click", (e) => {
  const dropdown = getNotificationsDropdown();
  const btn = getNotificationsBtn();
  if (!dropdown || !btn) return;
  if (!dropdown.contains(e.target) && !btn.contains(e.target)) {
    hideEl(dropdown);
  }
});

if (toolsBtn) {
  toolsBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const dropdown = ensureToolsDropdown();
    if (!dropdown) return;
    dropdown.classList.toggle("hidden");
  });
}

document.addEventListener("click", (e) => {
  if (!notificationsDropdown || !notificationsBtn) return;
  if (e.target === notificationsBtn || notificationsDropdown.contains(e.target)) return;
  hideEl(notificationsDropdown);
});

document.addEventListener("click", (e) => {
  const dropdown = ensureToolsDropdown();
  if (!dropdown || !toolsBtn) return;
  if (e.target === toolsBtn || dropdown.contains(e.target)) return;
  dropdown.classList.add("hidden");
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const notificationsDropdown = getNotificationsDropdown();
    if (notificationsDropdown && !isHidden(notificationsDropdown)) {
      hideEl(notificationsDropdown);
    }
    const toolsDropdown = getToolsDropdown();
    if (toolsDropdown && !toolsDropdown.classList.contains("hidden")) {
      toolsDropdown.classList.add("hidden");
    }
    // Close persona popover
    const personaPopover = document.querySelector('.persona-popover');
    if (personaPopover) {
      personaPopover.classList.remove('show');
    }
  }
});

// Stream chip functionality
function updateStreamChip() {
  const streamChip = getStreamChip();
  const streamToggle = getStreamToggle();
  if (!streamChip || !streamToggle) return;

  const isEnabled = streamToggle.checked;
  streamChip.classList.toggle('streaming-enabled', isEnabled);
  streamChip.classList.toggle('streaming-disabled', !isEnabled);
}

const streamToggle = getStreamToggle();
if (streamToggle) {
  streamToggle.addEventListener('change', updateStreamChip);
  // Initial update
  updateStreamChip();
}

// Add click handler for stream chip
const streamChipElement = getStreamChip();
if (streamChipElement) {
  streamChipElement.addEventListener('click', () => {
    const streamToggle = getStreamToggle();
    if (streamToggle) {
      streamToggle.checked = !streamToggle.checked;
      updateStreamChip();
    }
  });
}

// Persona popover functionality
let personaPopover = null;

function createPersonaPopover() {
  if (personaPopover) return personaPopover;

  personaPopover = document.createElement('div');
  personaPopover.className = 'persona-popover';
  personaPopover.innerHTML = `
    <div style="margin-bottom: 8px; font-weight: 500;">Tilpas personlighed</div>
    <textarea placeholder="Beskriv JARVIS' personlighed for denne session..."></textarea>
    <div class="persona-actions">
      <button class="cancel">Annuller</button>
      <button class="primary save">Gem</button>
    </div>
  `;

  const textarea = personaPopover.querySelector('textarea');
  const cancelBtn = personaPopover.querySelector('.cancel');
  const saveBtn = personaPopover.querySelector('.save');

  // Load saved persona
  const savedPersona = localStorage.getItem('jarvisPersona') || '';
  textarea.value = savedPersona;

  cancelBtn.addEventListener('click', () => {
    personaPopover.classList.remove('show');
  });

  saveBtn.addEventListener('click', () => {
    const persona = textarea.value.trim();
    localStorage.setItem('jarvisPersona', persona);
    personaPopover.classList.remove('show');
    // Could send to backend here if needed
  });

  document.body.appendChild(personaPopover);
  return personaPopover;
}

const personaChipElement = getPersonaChip();
if (personaChipElement) {
  personaChipElement.addEventListener('click', (e) => {
    e.stopPropagation();
    const popover = createPersonaPopover();
    
    // Position the popover above the chip
    const chipRect = personaChipElement.getBoundingClientRect();
    popover.style.left = (chipRect.left + chipRect.width / 2) + 'px';
    popover.style.top = (chipRect.top - 10) + 'px';
    popover.style.transform = 'translateX(-50%) translateY(-100%)';
    
    popover.classList.toggle('show');
  });
}

// Close popover when clicking outside
document.addEventListener('click', (e) => {
  if (personaPopover && !personaChipElement?.contains(e.target) && !personaPopover.contains(e.target)) {
    personaPopover.classList.remove('show');
  }
});

async function loadNotifications() {
  if (!getToken()) return;
  const url = "/v1/notifications" + (notificationsLastId ? `?since_id=${notificationsLastId}` : "");
  const data = await safeJson(url, null, { method: "GET" });
  if (!data) return;
  const notifications = data.notifications || [];
  notificationsCache = [...notificationsCache, ...notifications];
  if (notifications.length > 0) {
    notificationsLastId = notifications[notifications.length - 1].id;
  }
  updateNotificationsBadge();
  renderNotificationsDropdown();
}

async function updateNotificationsBadge() {
  const data = await safeJson("/v1/notifications/unread_count", null, { method: "GET" });
  if (!data) return;
  const unreadCount = data.count || 0;
  if (notificationsBadge) {
    notificationsBadge.textContent = unreadCount > 0 ? unreadCount : "";
    notificationsBadge.style.display = unreadCount > 0 ? "inline" : "none";
  }
}

function renderNotificationsDropdown() {
  if (!notificationsList) return;
  notificationsList.innerHTML = "";
  if (notificationsCache.length === 0) {
    notificationsList.innerHTML = '<div class="notifications-empty">Ingen notifikationer</div>';
    return;
  }
  notificationsCache.slice(-10).reverse().forEach(notification => {
    const item = document.createElement("div");
    item.className = `notifications-item ${notification.read ? "" : "unread"}`;
    item.innerHTML = `
      <div class="notifications-title">${notification.title}</div>
      <div class="notifications-body">${notification.body}</div>
      <div class="notifications-time">${new Date(notification.created_at).toLocaleString()}</div>
    `;
    item.addEventListener("click", () => markNotificationRead(notification.id));
    notificationsList.appendChild(item);
  });
}

async function markNotificationRead(notificationId) {
  try {
    await apiFetch(`/v1/notifications/${notificationId}/read`, { method: "POST" });
    const notification = notificationsCache.find(n => n.id === notificationId);
    if (notification) {
      notification.read = true;
    }
    updateNotificationsBadge();
    renderNotificationsDropdown();
  } catch (err) {
    console.error("Failed to mark notification as read:", err);
  }
}

async function markAllNotificationsRead() {
  try {
    await apiFetch(`/v1/notifications/mark_all_read`, { method: "POST" });
    notificationsCache.forEach(n => n.read = true);
    updateNotificationsBadge();
    renderNotificationsDropdown();
  } catch (err) {
    console.error("Failed to mark all notifications as read:", err);
  }
}

function showNotificationsDropdown() {
  const dropdown = getNotificationsDropdown();
  if (!dropdown) return;

  if (isHidden(dropdown)) {
    showEl(dropdown);
    loadNotifications();
    clampDropdown();
  } else {
    hideEl(dropdown);
  }
}

function clampDropdown() {
  const dropdown = getNotificationsDropdown();
  if (!dropdown || isHidden(dropdown)) return;
  const r = dropdown.getBoundingClientRect();
  if (r.right > innerWidth - 8) {
    dropdown.style.transform = `translateX(${-(r.right - (innerWidth - 8))}px)`;
  }
}

// Only one startNotificationPolling and registerStream should exist
function startNotificationPolling() {
  loadNotifications();
  const id1 = setInterval(loadNotifications, 12000);
  const id2 = setInterval(updateNotificationsBadge, 10000);
  pollingIntervals.push(id1, id2);
}

function registerStream(stream) {
  openStreams.push(stream);
  return stream;
}

// Initialize UI in a safe, deterministic order. Any single failure will be logged
// but will not abort the rest of the startup.
async function initUI() {
  // await applyPublicSettings(); // Stub: implement if needed
  await safe(loadBrand, "loadBrand");
  await safe(loadSettings, "loadSettings");
  initNotificationsUI();
  await safe(loadQuotaBar, "loadQuotaBar");
  await safe(loadSessions, "loadSessions");
  await safe(loadStatus, "loadStatus");
  
  // Initialize global UI element references
  noteCreateBtn = getNoteCreateBtn();
  noteCreateWrap = gid("noteCreateWrap");
  filesListWrap = gid("filesListWrap");
  filesList = getFilesListWrap();
  notesList = getNotesList();
  eventsList = getEventsList();
  sessionPromptSave = getSessionPromptSave();
  sessionPromptClear = getSessionPromptClear();
  noteContentInput = getNoteContentInput();
  bindRightbarToggle();
  
  // Non-critical but useful steps
  await safe(loadModel, "loadModel");
  await safe(loadFooter, "loadFooter");
  await safe(loadProfile, "loadProfile");
  await safe(loadExpiryNotice, "loadExpiryNotice");
  await safe(loadNotes, "loadNotes");
  await safe(loadFiles, "loadFiles");
  await safe(loadRightNotes, "loadRightNotes");
  await safe(loadRightLogs, "loadRightLogs");
  
  // Start polling and background tasks — wrapped to avoid throw-through
  try {
    if (PUBLIC_SETTINGS.notifications_enabled !== false) {
      startEventsStream();
      startNotificationPolling();
    }
  } catch (err) {
    console.warn("events/notifications stream failed", err);
  }
  
  // periodic refreshers
  pollingIntervals.push(setInterval(loadStatus, 30000));
  pollingIntervals.push(setInterval(loadFiles, 15000));
  pollingIntervals.push(setInterval(loadRightPanels, 60000));
  pollingIntervals.push(setInterval(loadRightNotes, 60000));
  pollingIntervals.push(setInterval(loadRightLogs, 60000));
  adminIntervals.push(setInterval(loadRightTickets, 15000));
  adminIntervals.push(setInterval(loadRightLogs, 60000));
  setInterval(() => renderRightPanels(window.__updatesLog || "", window.__commandsList || []), 1000);
  
  // Final UI touches
  try { setStatus("Klar"); } catch (err) {}
  try { updateToolDots(); } catch (err) {}
  try { updateStreamChip(); } catch (err) {}
  if (typeof initCookieBanner === "function") {
    try { initCookieBanner(); } catch (err) { console.warn("initCookieBanner failed", err); }
  }
  setRightbarVisibility(isAdminUser && !authState.adminUnavailable);
  
  // Mark UI as ready (used by CSS to reveal non-essential UI parts)
  document.body.classList.add("ui-ready");
  // Removed tooltip support for chat messages
  
  console.log("UI ready");
}
  


// --- Robust auth/session state: always check /account/profile on load ---
async function ensureAuthState() {
  bootstrappingAuth = true;
  try {
    const res = await apiFetch("/account/profile", { method: "GET" });
    if (res && res.ok) {
      const profile = await res.json();
      if (window.authStore && typeof window.authStore.updateFromProfile === 'function') {
        window.authStore.updateFromProfile(profile);
      }
      authLostLatch = false;
      hideAuthOverlays();
      // Show/hide admin UI
      document.querySelectorAll('.admin-only').forEach(el => {
        el.classList.toggle('hidden', !profile.is_admin);
      });
      // Show main UI
      showAppShell();
      document.body.classList.add('ui-ready');
      setRightbarVisibility(!!profile.is_admin && !authState.adminUnavailable);
      if (window.location.hash === "#admin/login") {
        window.location.hash = "";
      }
    } else {
      try {
        const body = await res.clone().text().catch(() => "<no-body>");
        console.warn("[auth] profile fetch failed", res.status, body);
      } catch (err) {}
      if (window.authStore && typeof window.authStore.reset === 'function') {
        window.authStore.reset();
      }
      showLoggedOutScreen();
      document.body.classList.remove('ui-ready');
    }
  } catch (err) {
    if (window.authStore && typeof window.authStore.reset === 'function') {
      window.authStore.reset();
    }
    showLoggedOutScreen();
    document.body.classList.remove('ui-ready');
  } finally {
    bootstrappingAuth = false;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  // Force-close optional modals/dropdowns on initial load
  ["settingsModal", "notificationsDropdown", "personaPopover", "toolsDropdown"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === "notificationsDropdown") {
      el.hidden = true;
    }
    el.classList.add("hidden");
    el.style.display = id === "settingsModal" ? "none" : "";
  });
  // If hash targets settings, defer opening until after auth success
  const loginBtn = document.getElementById("loggedOutLoginBtn");
  if (loginBtn) {
    loginBtn.addEventListener("click", () => { window.location.href = "/login"; });
  }
  await ensureAuthState();
  // If not authenticated, stop here
  if (!window.authStore?.isAuthenticated) return;
  if (window.location.hash.startsWith("#settings/")) {
    openSettingsModal();
  }
  await initUI();
});
window.addEventListener("beforeunload", () => {
  if (typeof stopEventsStream === 'function') stopEventsStream();
});
}
