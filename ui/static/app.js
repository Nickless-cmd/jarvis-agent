if (typeof requireAuth === "function") {
  requireAuth();
} else {
  window.location.href = "/login";
}

const chat = document.getElementById("chat");
const streamToggle = document.getElementById("streamToggle");
const chatStatus = document.getElementById("chatStatus");
const sessionStatus = document.getElementById("sessionStatus");
const modeSelect = document.getElementById("modeSelect");
const responseModeSelect = document.getElementById("responseModeSelect");
const modelSelect = document.getElementById("modelSelect");
const sessionList = document.getElementById("sessionList");
const sessionSearch = document.getElementById("sessionSearch");
const statusBadge = document.getElementById("statusBadge");
const statusInline = document.getElementById("chatStatusInline");
const footerText = document.getElementById("footerText");
const footerSupport = document.getElementById("footerSupport");
const footerContact = document.getElementById("footerContact");
const footerLicense = document.getElementById("footerLicense");
const LAST_SESSION_KEY = "jarvisLastSessionId";
const LAST_SESSION_COOKIE = "jarvis_last_session";
const toolsSummary = document.getElementById("toolsSummary");
const jarvisDot = document.getElementById("jarvisDot");
const quotaRequestBtn = document.getElementById("quotaRequestBtn");
const quotaNotice = document.getElementById("quotaNotice");
const streamChip = document.getElementById("streamChip");
const streamDot = document.getElementById("streamDot");
const personaChip = document.getElementById("personaChip");
const quotaFill = document.getElementById("quotaFill");
const quotaText = document.getElementById("quotaText");
const globalSearch = document.getElementById("globalSearch");
const globalSearchResults = document.getElementById("globalSearchResults");
const topBanner = document.getElementById("topBanner");
const bannerTrack = document.getElementById("bannerTrack");
let lastEventId = null;
const expiryNotice = document.getElementById("expiryNotice");
const uploadInput = document.getElementById("uploadInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadSidebarBtn = document.getElementById("uploadSidebarBtn");
const imageUploadBtn = document.getElementById("imageUploadBtn");
const imageUploadInput = document.getElementById("imageUploadInput");
const notesList = document.getElementById("notesList");
const filesList = document.getElementById("filesList");
const noteTitleInput = document.getElementById("noteTitleInput");
const noteContentInput = document.getElementById("noteContentInput");
const noteCreateBtn = document.getElementById("noteCreateBtn");
const quotaBar = document.getElementById("quotaBar");
const notesPanel = document.getElementById("notesPanel");
const filesPanel = document.getElementById("filesPanel");
const noteDueInput = document.getElementById("noteDueInput");
const noteRemindToggle = document.getElementById("noteRemindToggle");
const brandTop = document.getElementById("brandTop");
const brandCore = document.getElementById("brandCore");
const brandShort = document.getElementById("brandShort");
const newChatInline = document.getElementById("newChatInline");
const sessionPromptRow = document.getElementById("sessionPromptRow");
const sessionPromptInput = document.getElementById("sessionPromptInput");
const sessionPromptSave = document.getElementById("sessionPromptSave");
const sessionPromptClear = document.getElementById("sessionPromptClear");
const suggestions = document.getElementById("suggestions");
const noteToggleBtn = document.getElementById("noteToggleBtn");
const noteCreateWrap = document.getElementById("noteCreateWrap");
const greetingBanner = document.getElementById("greetingBanner");
const onlinePill = document.getElementById("onlinePill");
const modeLabel = document.getElementById("modeLabel");
const filesToggleBtn = document.getElementById("filesToggleBtn");
const filesListWrap = document.getElementById("filesListWrap");
const micBtn = document.getElementById("micBtn");
const langSelect = document.getElementById("langSelect");
const themeSelect = document.getElementById("themeSelect");
const chatPane = document.querySelector(".chat-pane");
const modeChip = document.getElementById("modeChip");
const modeChipLabel = document.getElementById("modeChipLabel");
const eventsList = document.getElementById("eventsList");

let currentSessionId = null;
let sessionsCache = [];
let lastSent = { text: "", ts: 0 };
let isAdminUser = false;
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
let lastEventId = null;

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
  if (langSelect?.value) return langSelect.value;
  return sessionStorage.getItem("jarvisLangSession") || localStorage.getItem("jarvisLang") || "da";
}

function applyUiLang(value) {
  const lang = value === "en" ? "en" : "da";
  sessionStorage.setItem("jarvisLangSession", lang);
  localStorage.removeItem("jarvisLang");
  document.documentElement.lang = lang;
  if (langSelect) langSelect.value = lang;
  const dict = I18N[lang];
  if (globalSearch) globalSearch.placeholder = dict.searchPlaceholder;
  if (sessionSearch) {
    sessionSearch.placeholder = lang === "en" ? "Search chats..." : "Søg chats...";
  }
  if (newChatInline) newChatInline.textContent = dict.newChat;
  if (noteToggleBtn) noteToggleBtn.textContent = dict.newNote;
  if (filesToggleBtn) filesToggleBtn.textContent = dict.showFiles;
  if (quotaBar) {
    const label = quotaBar.querySelector(".quota-label span");
    if (label) label.textContent = dict.quota;
  }
  // Update status badge
  if (statusBadge) statusBadge.textContent = dict.statusReady;
  // Update status line
  if (statusInline) statusInline.textContent = dict.statusReadyFull;
  // Update select options
  if (langSelect) {
    const daOption = langSelect.querySelector('option[value="da"]');
    const enOption = langSelect.querySelector('option[value="en"]');
    if (daOption) daOption.textContent = dict.langDa;
    if (enOption) enOption.textContent = dict.langEn;
    langSelect.setAttribute('aria-label', dict.ariaLanguage);
  }
  if (themeSelect) {
    const darkOption = themeSelect.querySelector('option[value="dark"]');
    const lightOption = themeSelect.querySelector('option[value="light"]');
    const systemOption = themeSelect.querySelector('option[value="system"]');
    if (darkOption) darkOption.textContent = dict.themeDark;
    if (lightOption) lightOption.textContent = dict.themeLight;
    if (systemOption) systemOption.textContent = dict.themeSystem;
    themeSelect.setAttribute('aria-label', dict.ariaTheme);
  }
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
  if (themeSelect) themeSelect.value = want;
}

function initTheme() {
  const saved = sessionStorage.getItem("jarvisThemeSession");
  const theme = saved === "light" || saved === "system" ? saved : "system";
  applyUiTheme(theme);
  if (theme === "system" && window.matchMedia) {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", () => {
      if ((sessionStorage.getItem("jarvisThemeSession") || "system") === "system") {
        applyUiTheme("system");
      }
    });
  }
}

function renderRightPanels(updatesLog = "", commands = []) {
  const updatesPanel = document.getElementById("updatesPanel");
  const updatesClock = document.getElementById("updatesClock");
  const rightbarCity = document.getElementById("rightbarCity");
  const commandsPanel = document.getElementById("commandsPanel");
  const statusPanel = document.getElementById("statusPanel");
  const rightNotesBody = document.getElementById("rightNotesBody");
  const lang = getUiLang();
  if (updatesClock) {
    const now = new Date();
    const locale = lang === "en" ? "en-GB" : "da-DK";
    const time = now.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    const date = now.toLocaleDateString(locale, { day: "2-digit", month: "2-digit", year: "numeric" });
    updatesClock.textContent = lang === "en" ? `⏱ ${time} • ${date}` : `⏱ ${time} • ${date}`;
  }
  if (rightbarCity) {
    const city = localStorage.getItem("jarvisCity") || "";
    const label = lang === "en" ? "City" : "By";
    rightbarCity.textContent = `- ${label}: ${city || "—"}`;
  }
  if (updatesPanel) {
    const lines = (updatesLog || "")
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l);
    if (!lines.length) {
      updatesPanel.innerHTML = `<div class="muted">${lang === "en" ? "No updates yet." : "Ingen opdateringer endnu."}</div>`;
    } else {
      const items = lines.slice(0, 6).map((l) => `<li>${l}</li>`).join("");
      updatesPanel.innerHTML = `<ul>${items}</ul>`;
    }
  }
  if (commandsPanel) {
    const items = commands && commands.length
      ? commands
      : lang === "en"
        ? [
            "/summary — Summarize chat",
            "/cv example — CV structure",
            "/cv jarvis — JARVIS CV",
            "/banner — Admin banner",
          ]
        : [
            "/summary — Opsummer chat",
            "/cv eksempel — CV‑struktur",
            "/cv jarvis — JARVIS‑CV",
            "/banner — Admin‑banner",
          ];
    commandsPanel.innerHTML = `<ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul>`;
  }
  if (statusPanel) {
    statusPanel.dataset.placeholder = "1";
  }
  if (rightNotesBody) {
    rightNotesBody.dataset.placeholder = "1";
  }
}

async function loadRightPanels() {
  const res = await fetch("/settings/public");
  if (!res.ok) return;
  const data = await res.json();
  const list = (data.updates_log || "").trim() ? data.updates_log : (data.updates_auto || []).join("\n");
  window.__updatesLog = list || "";
  window.__commandsList = data.commands || [];
  renderRightPanels(window.__updatesLog, window.__commandsList);
  const rightNotesPanel = document.getElementById("rightNotesPanel");
  const rightTicketsPanel = document.getElementById("rightTicketsPanel");
  if (isAdminUser) {
    if (rightNotesPanel) rightNotesPanel.classList.add("hidden");
    if (rightTicketsPanel) rightTicketsPanel.classList.remove("hidden");
  } else {
    if (rightTicketsPanel) rightTicketsPanel.classList.add("hidden");
    if (rightNotesPanel) rightNotesPanel.classList.remove("hidden");
  }
}

async function loadRightNotes() {
  if (isAdminUser) return;
  const res = await apiFetch("/notes", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const rightNotesBody = document.getElementById("rightNotesBody");
  if (!rightNotesBody) return;
  const lang = getUiLang();
  const items = data.items || [];
  if (!items.length) {
    rightNotesBody.innerHTML = `<div class="muted">${lang === "en" ? "No notes yet." : "Ingen noter endnu."}</div>`;
    return;
  }
  const list = items.slice(0, 5).map((n) => {
    const title = n.title || n.content || "";
    const label = title.length > 80 ? `${title.slice(0, 77)}...` : title;
    return `<li>${label}</li>`;
  }).join("");
  rightNotesBody.innerHTML = `<ul>${list}</ul>`;
}

async function loadRightTickets() {
  if (!isAdminUser) return;
  const rightTicketsBody = document.getElementById("rightTicketsBody");
  const rightTicketsTitle = document.getElementById("rightTicketsTitle");
  const rightTicketsPanel = document.getElementById("rightTicketsPanel");
  if (!rightTicketsBody || !rightTicketsPanel) return;
  const res = await apiFetch("/admin/tickets", { method: "GET" });
  if (!res || !res.ok) {
    rightTicketsBody.innerHTML = `<div class="muted">${getUiLang() === "en" ? "No ticket data." : "Ingen ticket-data."}</div>`;
    return;
  }
  const data = await res.json();
  const all = data.tickets || [];
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

async function loadRightLogs() {
  if (!isAdminUser) return;
  const res = await apiFetch("/admin/logs", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const files = data.files || [];
  const statusPanel = document.getElementById("statusPanel");
  if (!statusPanel) return;
  const lang = getUiLang();
  if (!files.length) {
    statusPanel.innerHTML = `<div class="muted">${lang === "en" ? "No logs yet." : "Ingen logs endnu."}</div>`;
    return;
  }
  const latest = files[0]?.name;
  if (!latest) return;
  const resLog = await apiFetch(`/admin/logs/${latest}`, { method: "GET" });
  if (!resLog) return;
  const payload = await resLog.json();
  const content = (payload.content || "").trim();
  const lines = content.split("\n").slice(-12).join("\n");
  statusPanel.innerHTML = `<pre>${lines || (lang === "en" ? "No logs yet." : "Ingen logs endnu.")}</pre>`;
}

function updatePromptPlaceholder() {
  const input = document.getElementById("prompt");
  if (!input) return;
  const lang = getUiLang();
  const label = brandCoreLabel || "Jarvis";
  input.placeholder = lang === "en" ? `Write to ${label}...` : `Skriv til ${label}...`;
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
    if (chatStatusInline) {
      chatStatusInline.textContent = maintenanceMessage || "Vedligeholdelse aktiv.";
    }
    if (chatStatus) {
      chatStatus.textContent = maintenanceMessage || "Vedligeholdelse aktiv.";
    }
    if (promptInput) promptInput.disabled = true;
    const sendBtn = document.getElementById("sendBtn");
    if (sendBtn) sendBtn.disabled = true;
  } else {
    if (promptInput) promptInput.disabled = false;
    const sendBtn = document.getElementById("sendBtn");
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
    await pollEvents();
  } catch (err) {
    console.error("Failed to dismiss event:", err);
  }
}

async function pollEvents() {
  if (!getToken()) return;
  const url = "/v1/events" + (lastEventId ? `?since_id=${lastEventId}` : "");
  const res = await apiFetch(url, { method: "GET" });
  if (!res) return;
  try {
    const data = await res.json();
    appendEventBanners(data.events || []);
  } catch (err) {
    console.error("Failed to read events:", err);
  }
}

function startEventPolling() {
  pollEvents();
  setInterval(pollEvents, 8000);
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
  statusBadge.textContent = translatedText;
  if (translatedText === dict.statusReady) {
    statusInline.textContent = dict.statusReadyFull;
    return;
  }
  statusInline.textContent = translatedText.replace(/^JARVIS\b/i, brandCoreLabel);
  const lastAssistant = [...document.querySelectorAll(".message.assistant")].pop();
  if (lastAssistant) {
    const statusEl = lastAssistant.querySelector(".msg-status");
    if (statusEl) {
      statusEl.textContent = `— ${translatedText.replace(/^JARVIS\s*/i, "")}`;
    }
  }
}

function updateGreeting(name) {
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
  addMessage("assistant", `Fil uploadet: ${info.original_name || "fil"} (id ${info.id}).`);
  if (url) {
    addFileCard({ title: info.original_name || "Fil", label: "Download fil", url });
  }
  loadFiles();
}

async function loadNotes() {
  if (!notesList) return;
  const res = await apiFetch("/notes", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const items = data.notes || [];
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
  const res = await apiFetch("/files", { method: "GET" });
  if (!res) return;
  const data = await res.json();
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
  if (!chat) return;
  const statusRow = document.querySelector(".status-row");
  if (!hasSession) {
    chat.innerHTML = "";
    hasMessages = false;
    chat.style.display = "none";
    if (statusRow) statusRow.style.display = "flex";
    if (greetingBanner) greetingBanner.style.display = "block";
    if (chatPane) chatPane.classList.add("no-session");
    if (sessionPromptRow) sessionPromptRow.classList.add("hidden");
    renderSuggestions();
    updateToolsSummary();
    return;
  }
  chat.style.display = "flex";
  if (statusRow) statusRow.style.display = "flex";
  if (chatPane) chatPane.classList.remove("no-session");
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

function renderMessageBody(body, text) {
  body.innerHTML = "";
  const lines = (text || "").split(/\r?\n/);
  let listEl = null;
  const flushList = () => {
    listEl = null;
  };
  const isListLine = (value) => /^(\d+\.\s+|[-•]\s+)/.test(value);
  const anchorMatch = (value) =>
    value.match(/<a\b[^>]*href=['"]([^'"]+)['"][^>]*>([^<]+)<\/a>/i);
  const decodeAnchors = (value) => {
    if (!value.includes("&lt;a")) return value;
    return value
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, "\"")
      .replace(/&#39;/g, "'")
      .replace(/&amp;/g, "&");
  };
  const markdownLink = (value) =>
    value.match(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/);
  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      const spacer = document.createElement("div");
      spacer.className = "msg-spacer";
      body.appendChild(spacer);
      return;
    }
    if (isListLine(trimmed)) {
      if (!listEl) {
        listEl = document.createElement("ul");
        listEl.className = "msg-list";
        body.appendChild(listEl);
      }
      const item = document.createElement("li");
      item.textContent = trimmed.replace(/^(\d+\.\s+|[-•]\s+)/, "");
      listEl.appendChild(item);
      return;
    }
    flushList();
    if (trimmed.endsWith(":") && trimmed.length <= 60) {
      const section = document.createElement("div");
      section.className = "msg-section";
      section.textContent = trimmed;
      body.appendChild(section);
      return;
    }
    const row = document.createElement("div");
    row.className = "msg-line";
    const decoded = decodeAnchors(line);
    const match = anchorMatch(decoded);
    const mdMatch = markdownLink(decoded);
    if (match) {
      const [full, href, label] = match;
      const before = decoded.split(full)[0];
      const after = decoded.split(full)[1] || "";
      if (before) row.appendChild(document.createTextNode(before));
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = label;
      row.appendChild(link);
      if (after) row.appendChild(document.createTextNode(after));
    } else if (mdMatch) {
      const [full, label, href] = mdMatch;
      const before = decoded.split(full)[0];
      const after = decoded.split(full)[1] || "";
      if (before) row.appendChild(document.createTextNode(before));
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = label;
      row.appendChild(link);
      if (after) row.appendChild(document.createTextNode(after));
    } else {
      row.textContent = line;
    }
    body.appendChild(row);
  });
}

function addMessage(role, text, when) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const header = document.createElement("div");
  header.className = "msg-header";
  const name = document.createElement("span");
  name.textContent = role === "user" ? "Dig" : "Jarvis";
  const time = document.createElement("span");
  time.textContent = nowTime(when);
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
  renderMessageBody(body, text);

  wrapper.appendChild(header);
  wrapper.appendChild(body);
  chat.appendChild(wrapper);
  if (greetingBanner) greetingBanner.style.display = "none";
  hasMessages = true;
  chat.scrollTop = chat.scrollHeight;
  return wrapper;
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
  sessionsCache = data.sessions || [];
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
  const items = sessionsCache.filter((s) => (s.name || s.id).toLowerCase().includes(filter));
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
  const top = rect.top + window.scrollY - 34;
  const left = rect.left + window.scrollX + 6;
  tip.style.top = `${Math.max(10, top)}px`;
  tip.style.left = `${Math.max(10, left)}px`;
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
  chat.innerHTML = "";
  currentSessionId = id;
  storeCurrentSession();
  await loadSessionPrompt();
  updateActiveSessionLabel();
  const res = await apiFetch(`/share/${id}`, { method: "GET" });
  if (!res) return;
  const data = await res.json();
  (data.messages || []).forEach((m) => {
    const role = m.role === "user" ? "user" : "assistant";
    addMessage(role, m.content, m.created_at);
  });
  hasMessages = (data.messages || []).length > 0;
  if (greetingBanner) greetingBanner.style.display = hasMessages ? "none" : "block";
  chat.scrollTop = chat.scrollHeight;
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
  const offset = 14;
  tooltipEl.style.top = `${e.clientY + offset}px`;
  tooltipEl.style.left = `${e.clientX + offset}px`;
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
  modelSelect.innerHTML = "";
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
    modelSelect.appendChild(opt);
  });
  const saved = localStorage.getItem("jarvisModel");
  if (saved) {
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
  const res = await fetch("/settings/brand");
  if (!res.ok) return;
  const data = await res.json();
  const topLabel = (data.top_label || "Jarvis").trim();
  const coreLabel = (data.core_label || "Jarvis").trim();
  brandCoreLabel = coreLabel || "Jarvis";
  if (brandTop) brandTop.textContent = topLabel || "Jarvis";
  if (brandCore) brandCore.textContent = brandCoreLabel;
  if (brandShort) brandShort.textContent = brandCoreLabel.charAt(0).toUpperCase() || "J";
  setStatus(statusBadge.textContent || "Klar");
  updatePromptPlaceholder();
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
    toolsSummary.appendChild(chip);
  });
}

function updateToolDots() {
  return;
}

function updateStreamChip() {
  if (!streamDot) return;
  const on = streamToggle && streamToggle.checked;
  streamDot.classList.remove("on", "off");
  streamDot.classList.add(on ? "on" : "off");
}

function showQuotaNotice(text) {
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

async function loadStatus() {
  if (!jarvisDot) return;
  try {
    const res = await fetch("/status");
    if (!res.ok) {
      setOnlineStatus(false);
      return;
    }
    const data = await res.json().catch(() => ({}));
    setOnlineStatus(data.online !== false);
  } catch (err) {
    setOnlineStatus(false);
  }
}

function setOnlineStatus(isOnline) {
  if (jarvisDot) {
    if (isOnline) jarvisDot.classList.add("online");
    else jarvisDot.classList.remove("online");
  }
  if (onlinePill) {
    if (isOnline) {
      onlinePill.classList.add("online");
      onlinePill.classList.remove("offline");
      onlinePill.textContent = "Online";
    } else {
      onlinePill.classList.add("offline");
      onlinePill.classList.remove("online");
      onlinePill.textContent = "Offline";
    }
  }
}

async function loadProfile() {
  const res = await apiFetch("/account/profile", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  isAdminUser = !!data.is_admin;
  if (data.city) {
    localStorage.setItem("jarvisCity", data.city);
  }
  updateGreeting((data.full_name || data.username || "").split(" ")[0]);
  if (modeLabel) modeLabel.style.display = "none";
  if (modeSelect) {
    modeSelect.style.display = "none";
    modeSelect.disabled = true;
  }
  if (micBtn) {
    micBtn.style.display = isAdminUser ? "inline-flex" : "none";
  }
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
    micBtn.classList.remove("active");
    setStatus("Klar");
  };

  micBtn.addEventListener("click", () => {
    if (!isAdminUser || !micRecognizer) return;
    if (micActive) {
      micRecognizer.stop();
      return;
    }
    micActive = true;
    micBtn.classList.add("active");
    setStatus("JARVIS lytter...");
    micRecognizer.start();
  });
  micReady = true;
}

async function sendMessage(textOverride = null) {
  const input = document.getElementById("prompt");
  const text = (textOverride ?? input.value).trim();
  if (!text) return;
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
  addMessage("user", text);

  const sessionId = currentSessionId;
  const payload = {
    model: modelSelect.value || "local",
    stream: streamToggle.checked,
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
    const assistantMsg = addMessage("assistant", content, data.server_time);
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

  const assistantMsg = addMessage("assistant", "", null);
  let pendingNews = null;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";
  let hadDelta = false;
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
        const body = assistantMsg.querySelector(".msg-body");
        if (body) {
          renderMessageBody(body, body.textContent || "");
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
          const body = assistantMsg.querySelector(".msg-body");
          body.textContent += delta;
          chat.scrollTop = chat.scrollHeight;
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
if (modeSelect) {
  modeSelect.addEventListener("change", () => {
    localStorage.setItem("jarvisMode", modeSelect.value);
    updateModeChipLabel();
  });
}
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

sessionSearch.addEventListener("input", renderSessionList);

document.getElementById("newChatBtn").addEventListener("click", createSession);
if (newChatInline) {
  newChatInline.addEventListener("click", createSession);
}
document.getElementById("sendBtn").addEventListener("click", () => sendMessage());
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
  window.location.href = "/login";
});
document.getElementById("accountBtn").addEventListener("click", () => {
  window.location.href = "/account";
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

if (noteCreateBtn) {
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

const promptInput = document.getElementById("prompt");
if (promptInput) {
  const resizePrompt = () => {
    promptInput.style.height = "auto";
    const max = 160;
    const next = Math.min(promptInput.scrollHeight, max);
    promptInput.style.height = `${next}px`;
  };
  promptInput.addEventListener("input", resizePrompt);
  promptInput.addEventListener("input", () => {
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
  resizePrompt();
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

if (streamChip) {
  streamChip.addEventListener("click", () => {
    if (!streamToggle) return;
    streamToggle.checked = !streamToggle.checked;
    updateStreamChip();
  });
}
if (personaChip) {
  personaChip.addEventListener("click", () => {
    if (!sessionPromptRow) return;
    sessionPromptRow.classList.toggle("hidden");
  });
}

if (modeChip) {
  modeChip.classList.add("hidden");
  modeChip.style.display = "none";
}

// admin/logout handled via rail buttons

if (modeSelect) {
  modeSelect.style.display = "none";
  modeSelect.disabled = true;
}
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

loadSessions();
loadModel();
loadFooter();
loadBrand();
loadProfile();
loadQuotaBar();
loadExpiryNotice();
loadNotes();
loadFiles();
loadStatus();
loadRightPanels();
loadRightNotes();
loadRightLogs();
startEventPolling();
setInterval(loadStatus, 30000);
setInterval(loadFiles, 15000);
setInterval(loadRightPanels, 60000);
setInterval(loadRightNotes, 60000);
setInterval(loadRightLogs, 60000);
setInterval(loadRightTickets, 15000);
setInterval(() => renderRightPanels(window.__updatesLog || "", window.__commandsList || []), 1000);
setStatus("Klar");
updateToolDots();
updateStreamChip();
updateToolsSummary();
if (typeof initCookieBanner === "function") {
  initCookieBanner();
}
