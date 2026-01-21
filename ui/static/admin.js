requireAuth();

async function ensureAdmin() {
  const res = await apiFetch("/account/profile", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  if (!data.is_admin) {
    clearToken();
    window.location.href = "/admin-login";
  }
}

const usersContainer = document.getElementById("users");
const sessionsContainer = document.getElementById("sessions");
const onlineUsersContainer = document.getElementById("onlineUsers");
const footerStatus = document.getElementById("footerStatus");
const createUserStatus = document.getElementById("createUserStatus");
const userSearchInput = document.getElementById("userSearch");
const sessionSearchInput = document.getElementById("sessionSearchAdmin");
const collapseBtn = document.getElementById("collapseBtn");
const navItems = document.querySelectorAll(".admin-nav-item");
const envStatus = document.getElementById("envStatus");
const envEditor = document.getElementById("envEditor");
const adminStatusDot = document.getElementById("adminStatusDot");
const adminStatusText = document.getElementById("adminStatusText");
const statusBadge = document.getElementById("statusBadge");
const footerText = document.getElementById("footerText");
const footerSupport = document.getElementById("footerSupport");
const footerContact = document.getElementById("footerContact");
const footerLicense = document.getElementById("footerLicense");
const adminSearchAll = document.getElementById("adminSearchAll");
const adminSearchResults = document.getElementById("adminSearchResults");
const logFiles = document.getElementById("logFiles");
const logContent = document.getElementById("logContent");
const refreshLogsBtn = document.getElementById("refreshLogsBtn");
const detailStatus = document.getElementById("detailStatus");
const ticketsAdminList = document.getElementById("ticketsAdminList");
const ticketAdminDetail = document.getElementById("ticketAdminDetail");
const ticketAdminTitle = document.getElementById("ticketAdminTitle");
const ticketAdminMeta = document.getElementById("ticketAdminMeta");
const ticketAdminStatus = document.getElementById("ticketAdminStatus");
const ticketAdminPriority = document.getElementById("ticketAdminPriority");
const ticketAdminSave = document.getElementById("ticketAdminSave");
const ticketAdminReply = document.getElementById("ticketAdminReply");
const ticketAdminReplyBtn = document.getElementById("ticketAdminReplyBtn");
const ticketAdminMessages = document.getElementById("ticketAdminMessages");
const modelSelectAdmin = document.getElementById("modelSelectAdmin");
const saveModelBtn = document.getElementById("saveModelBtn");
let currentTicketId = null;
let currentPanel = "panel-users";
let usersCache = [];
let defaultQuotaMb = 100;

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2400);
}

function showPanel(panelId) {
  currentPanel = panelId;
  navItems.forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".admin-grid .card").forEach((panel) => {
    panel.style.display =
      panel.id === panelId ||
      (panelId === "panel-users" && (panel.id === "panel-users" || panel.id === "panel-online-users"))
        ? "flex"
        : "none";
  });
}

function setEnvValue(content, key, value) {
  const lines = content.split("\n");
  let found = false;
  const updated = lines.map((line) => {
    if (line.trim().startsWith("#") || !line.includes("=")) return line;
    const [k] = line.split("=", 1);
    if (k.trim() === key) {
      found = true;
      return `${key}=${value}`;
    }
    return line;
  });
  if (!found) updated.push(`${key}=${value}`);
  return updated.join("\n").replace(/\n{3,}/g, "\n\n");
}

async function loadModelsAdmin() {
  if (!modelSelectAdmin) return;
  const [modelsRes, configRes] = await Promise.all([
    apiFetch("/models", { method: "GET" }),
    apiFetch("/config", { method: "GET" }),
  ]);
  if (!modelsRes || !configRes) return;
  const modelsData = await modelsRes.json();
  const configData = await configRes.json();
  const models = modelsData.models || [];
  modelSelectAdmin.innerHTML = "";
  models.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    modelSelectAdmin.appendChild(opt);
  });
  if (configData.model) {
    modelSelectAdmin.value = configData.model;
  }
}

async function saveModelSetting() {
  if (!modelSelectAdmin) return;
  const model = modelSelectAdmin.value;
  let content = envEditor?.value || "";
  if (!content) {
    const res = await apiFetch("/admin/env", { method: "GET" });
    if (!res) return;
    const data = await res.json();
    content = data.content || "";
  }
  const next = setEnvValue(content, "OLLAMA_MODEL", model);
  const res = await apiFetch("/admin/env", { method: "PATCH", body: JSON.stringify({ content: next }) });
  if (envStatus) {
    envStatus.textContent = res && res.ok ? "Model opdateret i .env." : "Kunne ikke opdatere model.";
  }
  if (res && res.ok) {
    if (envEditor) envEditor.value = next;
    showToast("Model opdateret.");
  }
}

function openUserDetail(user) {
  showPanel("panel-user-detail");
  document.getElementById("detailId").value = user.id || "";
  document.getElementById("detailUsername").value = user.username || "";
  document.getElementById("detailEmail").value = user.email || "";
  document.getElementById("detailFullName").value = user.full_name || "";
  document.getElementById("detailCity").value = user.city || "";
  document.getElementById("detailLastName").value = user.last_name || "";
  document.getElementById("detailPhone").value = user.phone || "";
  document.getElementById("detailNote").value = user.note || "";
  document.getElementById("detailCreated").value = user.created_at || "";
  document.getElementById("detailLastSeen").value = user.last_seen || "";
  document.getElementById("detailQuotaLimit").value = user.monthly_limit_mb ?? defaultQuotaMb;
  document.getElementById("detailQuotaCredits").value = user.credits_mb ?? "";
  document.getElementById("detailHash").value = (user.password_hash || "").slice(0, 30) + "...";
  document.getElementById("detailNewPassword").value = "";
  if (detailStatus) detailStatus.textContent = "";
}

function formatDate(value) {
  if (!value) return "ukendt";
  const date = new Date(value);
  if (isNaN(date.getTime())) return "ukendt";
  return date.toLocaleString("da-DK", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" });
}

async function loadLogs() {
  if (!logFiles) return;
  const res = await apiFetch("/admin/logs", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const files = data.files || [];
  logFiles.innerHTML = "";
  if (!files.length) {
    logFiles.innerHTML = "<div class=\"small\">Ingen logs.</div>";
    return;
  }
  files.forEach((f) => {
    const row = document.createElement("div");
    row.className = "mini-item";
    row.innerHTML = `
      <div class="mini-title">${f.name}</div>
      <div class="small">${formatDate(f.modified_at)} • ${(f.size / 1024).toFixed(1)} KB</div>
      <div class="mini-actions">
        <button data-action="view" data-name="${f.name}">Vis</button>
        <button data-action="delete" data-name="${f.name}">Slet</button>
      </div>
    `;
    logFiles.appendChild(row);
  });
}

async function loadLogContent(name) {
  if (!logContent) return;
  const res = await apiFetch(`/admin/logs/${encodeURIComponent(name)}`, { method: "GET" });
  if (!res) return;
  const data = await res.json();
  logContent.value = data.content || "";
}

function renderUsers(users) {
  usersContainer.innerHTML = "";
  users.forEach((u) => {
    const row = document.createElement("div");
    row.className = "session-item";
    row.innerHTML = `
      <div class="session-name">
        <div>${u.username} <span class="small">#${u.id}</span></div>
        <div class="small">${u.email || "ingen email"} • ${u.full_name || "ingen navn"}</div>
        <div class="small">${u.city || "ingen by"} • ${u.phone || "ingen telefon"}</div>
        <div class="small">${u.note || "ingen note"}</div>
        <div class="small">Oprettet: ${formatDate(u.created_at)} • Sidst set: ${formatDate(u.last_seen)}</div>
        <div class="small">hash: ${(u.password_hash || "").slice(0, 10)}…</div>
      </div>
      <div class="session-menu">
        <button class="session-menu-btn" aria-label="Menu">…</button>
        <div class="session-menu-panel">
          <button data-action="toggle" data-user="${u.username}" data-disabled="${u.is_disabled}">${u.is_disabled ? "Enable" : "Disable"}</button>
          <button data-action="edit" data-user="${u.username}">Rediger</button>
          <button data-action="reset-password" data-user="${u.username}">Nyt password</button>
          <button data-action="delete" data-user="${u.username}">Delete</button>
        </div>
      </div>
    `;
    usersContainer.appendChild(row);
    row.addEventListener("click", (e) => {
      if (e.target.closest(".session-menu")) return;
      openUserDetail(u);
    });
  });
}

function renderOnlineUsers(users) {
  onlineUsersContainer.innerHTML = "";
  if (!users.length) {
    onlineUsersContainer.innerHTML = "<div class=\"small\">Ingen online lige nu.</div>";
    return;
  }
  users.forEach((u) => {
    const row = document.createElement("div");
    row.className = "session-item";
    row.dataset.username = u.username;
    row.innerHTML = `
      <div class="session-name">
        <div><span class="online-dot"></span>${u.username}</div>
        <div class="small">${u.email || ""} • ${formatDate(u.last_seen)}</div>
      </div>
    `;
    onlineUsersContainer.appendChild(row);
    row.addEventListener("click", () => {
      const found = usersCache.find((user) => user.username === u.username);
      if (found) openUserDetail(found);
    });
  });
}

async function renameChatsForAll() {
  if (footerStatus) footerStatus.textContent = "Opdaterer chat-navne...";
  const res = await apiFetch("/admin/sessions/rename-empty", { method: "POST" });
  const data = res ? await res.json().catch(() => ({})) : {};
  if (footerStatus) {
    if (res && res.ok) {
      footerStatus.textContent = `Opdaterede ${data.updated ?? 0} chat-navne.`;
      showToast(`Opdaterede ${data.updated ?? 0} chat-navne.`);
    } else {
      footerStatus.textContent = data.detail || "Kunne ikke opdatere chat-navne.";
      showToast(data.detail || "Kunne ikke opdatere chat-navne.");
    }
  }
}

async function loadTicketsAdmin() {
  const res = await apiFetch("/admin/tickets", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  if (!ticketsAdminList) return;
  ticketsAdminList.innerHTML = "";
  (data.tickets || []).forEach((t) => {
    const row = document.createElement("div");
    row.className = "session-item";
    row.innerHTML = `
      <div class="session-name">
        #${t.id} ${t.title}
        <div class="small">${t.username} • ${t.status} • ${t.priority}</div>
      </div>
    `;
    row.addEventListener("click", () => openTicketAdmin(t.id));
    ticketsAdminList.appendChild(row);
  });
  if (!(data.tickets || []).length) {
    ticketsAdminList.innerHTML = "<div class=\"small\">Ingen tickets.</div>";
  }
}

async function openTicketAdmin(id) {
  const res = await apiFetch(`/admin/tickets/${id}`, { method: "GET" });
  if (!res) return;
  const data = await res.json();
  const t = data.ticket;
  currentTicketId = id;
  if (ticketAdminDetail) ticketAdminDetail.style.display = "block";
  if (ticketAdminTitle) ticketAdminTitle.textContent = `#${t.id} — ${t.title}`;
  if (ticketAdminMeta) ticketAdminMeta.textContent = `${t.username} • ${t.status} • ${t.priority}`;
  if (ticketAdminStatus) ticketAdminStatus.value = t.status;
  if (ticketAdminPriority) ticketAdminPriority.value = t.priority;
  if (ticketAdminMessages) {
    ticketAdminMessages.innerHTML = "";
    (t.messages || []).forEach((m) => {
      const row = document.createElement("div");
      row.className = "small";
      row.textContent = `[${m.role}] ${m.content}`;
      ticketAdminMessages.appendChild(row);
    });
  }
}

async function saveTicketAdmin() {
  if (!currentTicketId) return;
  const payload = {
    status: ticketAdminStatus?.value,
    priority: ticketAdminPriority?.value,
  };
  await apiFetch(`/admin/tickets/${currentTicketId}`, { method: "PATCH", body: JSON.stringify(payload) });
  loadTicketsAdmin();
}

async function replyTicketAdmin() {
  if (!currentTicketId) return;
  const message = ticketAdminReply?.value?.trim();
  if (!message) return;
  await apiFetch(`/admin/tickets/${currentTicketId}/reply`, { method: "POST", body: JSON.stringify({ message }) });
  if (ticketAdminReply) ticketAdminReply.value = "";
  openTicketAdmin(currentTicketId);
}

async function loadUsers() {
  const res = await apiFetch("/admin/users", { method: "GET" });
  if (!res) return;
  if (res.status === 403) {
    window.location.href = "/app";
    return;
  }
  const data = await res.json();
  const users = (data.users || []).sort((a, b) => (b.id || 0) - (a.id || 0));
  usersCache = users;
  const filter = (userSearchInput?.value || "").trim().toLowerCase();
  const base = users.slice(0, 5);
  const filtered = filter ? base.filter((u) => u.username.toLowerCase().includes(filter)) : base;
  renderUsers(filtered);
  if (!filtered.length) {
    usersContainer.innerHTML = "<div class=\"small\">Ingen brugere at vise.</div>";
  }
}

async function loadOnlineUsers() {
  const res = await apiFetch("/admin/online-users", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  renderOnlineUsers(data.users || []);
}

async function loadFooterSettings() {
  const res = await apiFetch("/admin/settings", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  document.getElementById("footerTextInput").value = data.footer_text || "";
  document.getElementById("footerSupportInput").value = data.footer_support_url || "";
  document.getElementById("footerContactInput").value = data.footer_contact_url || "";
  const licenseTextInput = document.getElementById("footerLicenseTextInput");
  const licenseUrlInput = document.getElementById("footerLicenseUrlInput");
  if (licenseTextInput) licenseTextInput.value = data.footer_license_text || "";
  if (licenseUrlInput) licenseUrlInput.value = data.footer_license_url || "";
  document.getElementById("registerEnabledInput").checked = !!data.register_enabled;
  document.getElementById("captchaEnabledInput").checked = !!data.captcha_enabled;
  const googleToggle = document.getElementById("googleAuthEnabledInput");
  if (googleToggle) googleToggle.checked = !!data.google_auth_enabled;
  const maintenanceToggle = document.getElementById("maintenanceEnabledInput");
  if (maintenanceToggle) maintenanceToggle.checked = !!data.maintenance_enabled;
  const maintenanceMessage = document.getElementById("maintenanceMessageInput");
  if (maintenanceMessage) maintenanceMessage.value = data.maintenance_message || "";
  document.getElementById("systemPromptInput").value = data.system_prompt || "";
  const updatesLogInput = document.getElementById("updatesLogInput");
  if (updatesLogInput) updatesLogInput.value = data.updates_log || "";
  const quotaDefaultInput = document.getElementById("quotaDefaultInput");
  if (quotaDefaultInput) quotaDefaultInput.value = data.quota_default_mb ?? "";
  defaultQuotaMb = data.quota_default_mb ?? 100;
  const brandTopInput = document.getElementById("brandTopInput");
  if (brandTopInput) brandTopInput.value = data.brand_top_label || "";
  const brandCoreInput = document.getElementById("brandCoreInput");
  if (brandCoreInput) brandCoreInput.value = data.brand_core_label || "";
  const bannerEnabledInput = document.getElementById("bannerEnabledInput");
  if (bannerEnabledInput) bannerEnabledInput.checked = data.banner_enabled !== false;
  const bannerInput = document.getElementById("bannerMessagesInput");
  if (bannerInput) bannerInput.value = data.banner_messages || "";
  const notifyEnabledInput = document.getElementById("notifyEnabledInput");
  if (notifyEnabledInput) notifyEnabledInput.checked = !!data.notify_enabled;
  if (document.getElementById("googleAuthEnabledInput")) {
    document.getElementById("googleAuthEnabledInput").checked = !!data.google_auth_enabled;
  }
  const publicBaseUrlInput = document.getElementById("publicBaseUrlInput");
  if (publicBaseUrlInput) publicBaseUrlInput.value = data.public_base_url || "";
}

async function saveFooterSettings() {
  const payload = {
    text: document.getElementById("footerTextInput").value.trim(),
    support_url: document.getElementById("footerSupportInput").value.trim(),
    contact_url: document.getElementById("footerContactInput").value.trim(),
    license_text: document.getElementById("footerLicenseTextInput")?.value.trim() || "",
    license_url: document.getElementById("footerLicenseUrlInput")?.value.trim() || "",
    register_enabled: document.getElementById("registerEnabledInput").checked,
    captcha_enabled: document.getElementById("captchaEnabledInput").checked,
    google_auth_enabled: document.getElementById("googleAuthEnabledInput")?.checked || false,
    maintenance_enabled: document.getElementById("maintenanceEnabledInput")?.checked || false,
    maintenance_message: document.getElementById("maintenanceMessageInput")?.value || "",
    system_prompt: document.getElementById("systemPromptInput").value,
    updates_log: document.getElementById("updatesLogInput")?.value || "",
    quota_default_mb: parseInt(document.getElementById("quotaDefaultInput")?.value || "0", 10),
    brand_top_label: document.getElementById("brandTopInput")?.value || "",
    brand_core_label: document.getElementById("brandCoreInput")?.value || "",
    banner_enabled: document.getElementById("bannerEnabledInput")?.checked || false,
    banner_messages: document.getElementById("bannerMessagesInput")?.value || "",
    public_base_url: document.getElementById("publicBaseUrlInput")?.value || "",
    notify_enabled: document.getElementById("notifyEnabledInput")?.checked || false,
  };
  const res = await apiFetch("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!res) return;
  footerStatus.textContent = res.ok ? "Footer gemt." : "Kunne ikke gemme footer.";
}

async function loadEnv() {
  const res = await apiFetch("/admin/env", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  if (envEditor) envEditor.value = data.content || "";
}

async function saveEnv() {
  if (!envEditor) return;
  const res = await apiFetch("/admin/env", {
    method: "PATCH",
    body: JSON.stringify({ content: envEditor.value }),
  });
  if (!res) return;
  envStatus.textContent = res.ok ? ".env gemt." : "Kunne ikke gemme .env.";
}

async function createUser() {
  const username = document.getElementById("createUsername").value.trim();
  const password = document.getElementById("createPassword").value.trim();
  const isAdmin = document.getElementById("createIsAdmin").checked;
  const email = document.getElementById("createEmail").value.trim();
  const fullName = document.getElementById("createFullName").value.trim();
  const lastName = document.getElementById("createLastName").value.trim();
  const city = document.getElementById("createCity").value.trim();
  const phone = document.getElementById("createPhone").value.trim();
  const note = document.getElementById("createNote").value.trim();
  if (!username || !password) {
    createUserStatus.textContent = "Udfyld brugernavn og password.";
    return;
  }
  const res = await apiFetch("/admin/users", {
    method: "POST",
    body: JSON.stringify({
      username,
      password,
      is_admin: isAdmin,
      email,
      full_name: fullName,
      last_name: lastName,
      city,
      phone,
      note,
    }),
  });
  const data = res ? await res.json() : null;
  createUserStatus.textContent = res && res.ok ? "Bruger oprettet." : data?.detail || "Kunne ikke oprette.";
  if (res && res.ok) {
    document.getElementById("createUsername").value = "";
    document.getElementById("createPassword").value = "";
    document.getElementById("createIsAdmin").checked = false;
    loadUsers();
  }
}

async function toggleUser(username, isDisabled) {
  await apiFetch(`/admin/users/${encodeURIComponent(username)}`, {
    method: "PATCH",
    body: JSON.stringify({ disabled: !isDisabled }),
  });
  loadUsers();
}

async function deleteUser(username) {
  await apiFetch(`/admin/users/${encodeURIComponent(username)}`, { method: "DELETE" });
  loadUsers();
}

async function loadSessions() {
  const username = document.getElementById("sessionUser").value.trim();
  const query = username ? `?username=${encodeURIComponent(username)}` : "";
  const res = await apiFetch(`/admin/sessions${query}`, { method: "GET" });
  if (!res) return;
  const data = await res.json();
  sessionsContainer.innerHTML = "";
  const filter = (sessionSearchInput?.value || "").trim().toLowerCase();
  const filtered = (data.sessions || []).filter((s) => (s.name || s.id).toLowerCase().includes(filter));
  if (!filtered.length) {
    sessionsContainer.innerHTML = "<div class=\"small\">Ingen sessions fundet.</div>";
    return;
  }
  filtered.forEach((s) => {
    const row = document.createElement("div");
    row.className = "session-item";
    const size = typeof s.size_bytes === "number" ? `${(s.size_bytes / 1024).toFixed(1)} KB` : "ukendt";
    row.innerHTML = `
      <div class="session-name">
        ${s.name || s.id}
        <div class="small">Størrelse: ${size}</div>
      </div>
      <div class="session-menu">
        <button class="session-menu-btn" aria-label="Menu">…</button>
        <div class="session-menu-panel">
          <button data-action="delete-session" data-id="${s.id}">Slet</button>
        </div>
      </div>
    `;
    sessionsContainer.appendChild(row);
  });
}

async function loadStatus() {
  const res = await apiFetch("/status", { method: "GET" });
  if (!res) return;
  const data = await res.json();
  if (adminStatusText) {
    adminStatusText.textContent = data.online ? "Jarvis er online" : "Jarvis er offline";
  }
  if (adminStatusDot) {
    adminStatusDot.style.background = data.online ? "#22c55e" : "#ef4444";
  }
  if (statusBadge) {
    statusBadge.textContent = data.online ? "Online" : "Offline";
  }
}

usersContainer.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  if (btn.classList.contains("session-menu-btn")) {
    const menu = btn.closest(".session-menu");
    document.querySelectorAll("#users .session-menu").forEach((el) => {
      if (el !== menu) el.classList.remove("open");
    });
    menu.classList.toggle("open");
    return;
  }
  const username = btn.dataset.user;
  const action = btn.dataset.action;
  const isDisabled = btn.dataset.disabled === "true";
  if (action === "toggle") toggleUser(username, isDisabled);
  if (action === "edit") {
    const email = prompt("Email (tom for ingen):");
    const fullName = prompt("Navn (tom for ingen):");
    const lastName = prompt("Efternavn (tom for ingen):");
    const city = prompt("By (tom for ingen):");
    const phone = prompt("Telefon (tom for ingen):");
    const note = prompt("Note (tom for ingen):");
    apiFetch(`/admin/users/${encodeURIComponent(username)}`, {
      method: "PATCH",
      body: JSON.stringify({
        email,
        full_name: fullName,
        last_name: lastName,
        city,
        phone,
        note,
      }),
    }).then(loadUsers);
  }
  if (action === "reset-password") {
    const pwd = prompt("Nyt password:");
    if (pwd) {
      apiFetch(`/admin/users/${encodeURIComponent(username)}`, {
        method: "PATCH",
        body: JSON.stringify({ new_password: pwd }),
      }).then(loadUsers);
    }
  }
  if (action === "delete") deleteUser(username);
});

sessionsContainer.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  if (btn.classList.contains("session-menu-btn")) {
    const menu = btn.closest(".session-menu");
    document.querySelectorAll("#sessions .session-menu").forEach((el) => {
      if (el !== menu) el.classList.remove("open");
    });
    menu.classList.toggle("open");
    return;
  }
  const action = btn.dataset.action;
  if (action === "delete-session") {
    const id = btn.dataset.id;
    apiFetch(`/admin/sessions/${id}`, { method: "DELETE" }).then(loadSessions);
  }
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".session-menu")) {
    document.querySelectorAll(".session-menu.open").forEach((menu) => menu.classList.remove("open"));
  }
});

document.getElementById("loadSessionsBtn").addEventListener("click", loadSessions);
document.getElementById("saveFooterBtn").addEventListener("click", saveFooterSettings);
document.getElementById("renameChatsBtn").addEventListener("click", renameChatsForAll);
document.getElementById("createUserBtn").addEventListener("click", createUser);
document.getElementById("saveEnvBtn").addEventListener("click", saveEnv);
saveModelBtn?.addEventListener("click", saveModelSetting);
document.getElementById("refreshTicketsBtn")?.addEventListener("click", loadTicketsAdmin);
document.getElementById("refreshLogsBtn")?.addEventListener("click", loadLogs);
ticketAdminSave?.addEventListener("click", saveTicketAdmin);
ticketAdminReplyBtn?.addEventListener("click", replyTicketAdmin);
userSearchInput?.addEventListener("input", loadUsers);
sessionSearchInput?.addEventListener("input", loadSessions);
document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  window.location.href = "/login";
});
document.getElementById("backBtn").addEventListener("click", () => {
  window.location.href = "/app";
});

ensureAdmin();
loadUsers();
loadOnlineUsers();
loadFooterSettings();
loadEnv();
loadStatus();
loadTicketsAdmin();

setInterval(() => {
  if (currentPanel === "panel-tickets") {
    loadTicketsAdmin();
  }
}, 15000);
loadLogs();
loadModelsAdmin();
setInterval(loadStatus, 15000);
setInterval(loadOnlineUsers, 15000);

if (logFiles) {
  logFiles.addEventListener("click", async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const name = btn.dataset.name;
    const action = btn.dataset.action;
    if (action === "view") {
      await loadLogContent(name);
    }
    if (action === "delete") {
      await apiFetch(`/admin/logs/${encodeURIComponent(name)}`, { method: "DELETE" });
      await loadLogs();
      if (logContent) logContent.value = "";
    }
  });
}

document.addEventListener("click", (e) => {
  if (!e.target.closest(".admin-search-results") && e.target !== adminSearchAll) {
    adminSearchResults?.classList.remove("open");
  }
});

document.getElementById("saveUserDetailBtn").addEventListener("click", () => {
  const username = document.getElementById("detailUsername").value;
  const payload = {
    email: document.getElementById("detailEmail").value.trim(),
    full_name: document.getElementById("detailFullName").value.trim(),
    city: document.getElementById("detailCity").value.trim(),
    last_name: document.getElementById("detailLastName").value.trim(),
    phone: document.getElementById("detailPhone").value.trim(),
    note: document.getElementById("detailNote").value.trim(),
  };
  const quotaLimitRaw = document.getElementById("detailQuotaLimit").value;
  const quotaCreditsRaw = document.getElementById("detailQuotaCredits").value;
  if (quotaLimitRaw !== "") {
    payload.monthly_limit_mb = parseInt(quotaLimitRaw, 10);
  }
  if (quotaCreditsRaw !== "") {
    payload.credits_mb = parseInt(quotaCreditsRaw, 10);
  }
  const newPassword = document.getElementById("detailNewPassword").value.trim();
  if (newPassword) payload.new_password = newPassword;
  apiFetch(`/admin/users/${encodeURIComponent(username)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }).then((res) => {
    detailStatus.textContent = res && res.ok ? "Bruger opdateret." : "Kunne ikke opdatere bruger.";
    loadUsers();
  });
});

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

loadFooter();

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

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    navItems.forEach((el) => el.classList.remove("active"));
    item.classList.add("active");
    const target = item.dataset.target;
    showPanel(target);
    if (target === "panel-sessions") {
      loadSessions();
    }
    if (target === "panel-tickets") {
      loadTicketsAdmin();
    }
  });
});

const initialPanel = document.querySelector(".admin-nav-item.active")?.dataset.target;
if (initialPanel) {
  showPanel(initialPanel);
}

function applyGlobalSearch() {
  const query = (adminSearchAll?.value || "").trim();
  if (!adminSearchResults) return;
  adminSearchResults.innerHTML = "";
  adminSearchResults.classList.remove("open");
  if (!query) return;

  Promise.all([
    apiFetch("/admin/users", { method: "GET" }).then((res) => (res ? res.json() : { users: [] })),
    apiFetch(`/admin/sessions${document.getElementById("sessionUser").value.trim() ? `?username=${encodeURIComponent(document.getElementById("sessionUser").value.trim())}` : ""}`, { method: "GET" })
      .then((res) => (res ? res.json() : { sessions: [] })),
  ]).then(([usersData, sessionsData]) => {
    const results = [];
    (usersData.users || []).forEach((u) => {
      const label = `${u.username} (${u.email || "ingen email"})`;
      if (label.toLowerCase().includes(query.toLowerCase())) {
        results.push({ type: "Bruger", label, target: "panel-user-detail", username: u.username });
      }
    });
    (sessionsData.sessions || []).forEach((s) => {
      const label = s.name || s.id;
      if (label.toLowerCase().includes(query.toLowerCase())) {
        results.push({ type: "Session", label, target: "panel-sessions" });
      }
    });
    if (
      query.toLowerCase().includes("footer") ||
      query.toLowerCase().includes("login") ||
      query.toLowerCase().includes("indstillinger")
    ) {
      results.push({ type: "Indstillinger", label: "Footer & login", target: "panel-settings" });
    }
    if (query.toLowerCase().includes("log")) {
      results.push({ type: "Logs", label: "System logs", target: "panel-logs" });
    }
    results.slice(0, 10).forEach((item) => {
      const row = document.createElement("div");
      row.className = "admin-search-item";
      row.innerHTML = `
        <div>
          <div>${item.label}</div>
          <div class="admin-search-meta">${item.type}</div>
        </div>
        <button data-target="${item.target}" data-user="${item.username || ""}">Gå til</button>
      `;
      adminSearchResults.appendChild(row);
    });
    if (results.length) {
      adminSearchResults.classList.add("open");
    }
  });
}

adminSearchAll?.addEventListener("input", applyGlobalSearch);
adminSearchResults?.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  const target = btn.dataset.target;
  if (target === "panel-user-detail") {
    const username = btn.dataset.user;
    const found = usersCache.find((u) => u.username === username);
    if (found) openUserDetail(found);
  } else {
    const item = document.querySelector(`.admin-nav-item[data-target="${target}"]`);
    if (item) item.click();
  }
  adminSearchResults.classList.remove("open");
});
