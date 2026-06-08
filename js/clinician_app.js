import { formatTissueGroup, formatFullDate, showToast } from "./utils.js";

// State
const state = {
  token: localStorage.getItem("woundly-token") || "",
  user: null,
  queue: [], // All entries from all patients
  selectedEntry: null, // Currently active entry for review
  activeView: "queue", // "queue" or "patients"
  activeFilter: "all" // "all", "unreviewed", "flagged"
};

// Elements
const authView = document.querySelector("#auth-view");
const appShell = document.querySelector("#app-shell");
const authError = document.querySelector("#auth-error");

const tabLogin = document.querySelector("#tab-login");
const tabRegister = document.querySelector("#tab-register");
const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const logoutButton = document.querySelector("#logout-button");

const navQueueBtn = document.querySelector("#nav-queue-btn");
const navPatientsBtn = document.querySelector("#nav-patients-btn");

const queueView = document.querySelector("#queue-view");
const patientsView = document.querySelector("#patients-view");
const assessmentView = document.querySelector("#assessment-view");

const queueTbody = document.querySelector("#queue-tbody");
const patientsTbody = document.querySelector("#patients-tbody");
const assessmentHistoryList = document.querySelector("#assessment-history-list");

const patientSearchInput = document.querySelector("#patient-search-input");

// ── Auth Handling ────────────────────────────────────────

tabLogin.addEventListener("click", () => switchAuthTab("login"));
tabRegister.addEventListener("click", () => switchAuthTab("register"));

function switchAuthTab(tab) {
  tabLogin.classList.toggle("active", tab === "login");
  tabRegister.classList.toggle("active", tab === "register");
  loginForm.classList.toggle("hidden", tab !== "login");
  registerForm.classList.toggle("hidden", tab !== "register");
  hideAuthError();
}

function showAuthError(message) {
  authError.textContent = message;
  authError.classList.remove("hidden");
}

function hideAuthError() {
  authError.classList.add("hidden");
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAuthError();
  const username = document.querySelector("#login-username").value.trim();
  const password = document.querySelector("#login-password").value;
  
  if (!username || !password) return showAuthError("Please fill in all fields.");
  
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Login failed.");
    
    if (data.user.role !== "clinician") {
      throw new Error("Access denied. Authorized clinicians only.");
    }
    
    setAuth(data.token, data.user);
    enterApp();
  } catch (err) {
    showAuthError(err.message);
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAuthError();
  const username = document.querySelector("#register-username").value.trim();
  const password = document.querySelector("#register-password").value;
  const confirm = document.querySelector("#register-confirm").value;
  const code = document.querySelector("#register-code").value.trim();
  
  if (!username || !password || !confirm || !code) {
    return showAuthError("Please fill in all fields.");
  }
  if (password !== confirm) {
    return showAuthError("Passwords do not match.");
  }
  if (code !== "CLINIC2026") {
    return showAuthError("Invalid activation code.");
  }
  
  try {
    const res = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        role: "clinician",
        registrationCode: code
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Registration failed.");
    
    setAuth(data.token, data.user);
    enterApp();
  } catch (err) {
    showAuthError(err.message);
  }
});

function setAuth(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem("woundly-token", token);
  localStorage.setItem("woundly-user", JSON.stringify(user));
}

function clearAuth() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("woundly-token");
  localStorage.removeItem("woundly-user");
}

logoutButton.addEventListener("click", () => {
  clearAuth();
  exitApp();
});

// Helper for authenticated requests
async function authFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    clearAuth();
    exitApp();
    throw new Error("Session expired. Please log in again.");
  }
  return response;
}

// ── App Lifecycle ───────────────────────────────────────

async function enterApp() {
  authView.classList.add("hidden");
  appShell.classList.remove("hidden");
  
  // Set profile info
  const savedUser = JSON.parse(localStorage.getItem("woundly-user"));
  if (savedUser) {
    state.user = savedUser;
    document.querySelector("#user-avatar").textContent = savedUser.username.slice(0, 2).toUpperCase();
    document.querySelector("#user-display-name").textContent = savedUser.username;
  }
  
  setTodayLabel();
  await loadQueue();
  showView("queue");
}

function exitApp() {
  appShell.classList.add("hidden");
  authView.classList.remove("hidden");
  loginForm.reset();
  registerForm.reset();
  hideAuthError();
  switchAuthTab("login");
}

function setTodayLabel() {
  document.querySelector("#today-label").textContent = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric"
  });
}

function showView(view) {
  state.activeView = view;
  
  // Hide pages
  queueView.classList.remove("active");
  patientsView.classList.remove("active");
  assessmentView.classList.remove("active");
  
  // Toggle nav
  navQueueBtn.classList.toggle("active", view === "queue");
  navPatientsBtn.classList.toggle("active", view === "patients");
  
  if (view === "queue") {
    queueView.classList.add("active");
    document.querySelector("#page-title").textContent = "Monitoring Review Queue";
    renderQueueTable();
  } else if (view === "patients") {
    patientsView.classList.add("active");
    document.querySelector("#page-title").textContent = "Patient Directory";
    renderPatientsTable();
  } else if (view === "assessment") {
    assessmentView.classList.add("active");
    document.querySelector("#page-title").textContent = "Clinical Assessment Workspace";
    renderAssessmentWorkspace();
  }
  
  window.scrollTo({ top: 0, behavior: "smooth" });
}

navQueueBtn.addEventListener("click", () => showView("queue"));
navPatientsBtn.addEventListener("click", () => showView("patients"));

// ── Queue Operations & Renderers ──────────────────────────

async function loadQueue() {
  try {
    const res = await authFetch("/api/clinician/queue");
    if (!res.ok) throw new Error("Failed to fetch queue.");
    state.queue = await res.json();
    calculateStats();
  } catch (err) {
    showToast(err.message);
  }
}

function calculateStats() {
  const total = state.queue.length;
  const pending = state.queue.filter(e => e.clinician_status === "unreviewed").length;
  const flagged = state.queue.filter(e => e.clinician_status === "flagged").length;
  
  document.querySelector("#stat-total-submissions").textContent = total;
  document.querySelector("#stat-pending-reviews").textContent = pending;
  document.querySelector("#stat-flagged-cases").textContent = flagged;
}

// Queue filters
document.querySelectorAll(".filter-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    state.activeFilter = chip.dataset.filter;
    renderQueueTable();
  });
});

function renderQueueTable() {
  const filtered = state.queue.filter(entry => {
    if (state.activeFilter === "unreviewed") return entry.clinician_status === "unreviewed";
    if (state.activeFilter === "flagged") return entry.clinician_status === "flagged";
    return true; // "all"
  });
  
  const emptyState = document.querySelector("#queue-empty");
  const table = document.querySelector("#queue-table");
  
  if (filtered.length === 0) {
    emptyState.classList.remove("hidden");
    table.classList.add("hidden");
    return;
  }
  
  emptyState.classList.add("hidden");
  table.classList.remove("hidden");
  
  queueTbody.innerHTML = filtered.map(entry => {
    const model = entry.modelAnalysis;
    const isQualityPassed = model.photo_quality.notes.length === 0;
    const qualityLabel = isQualityPassed 
      ? `<span class="quality-chip passed">Passed</span>` 
      : `<span class="quality-chip warning" title="${model.photo_quality.notes.join(', ')}">Issue Flagged</span>`;
      
    const statusText = entry.clinician_status.charAt(0).toUpperCase() + entry.clinician_status.slice(1);
    
    return `
      <tr>
        <td><strong>${entry.username}</strong></td>
        <td>${formatFullDate(entry.date)}</td>
        <td><strong>${model.segmentation.coverage_percent}%</strong></td>
        <td>${formatTissueGroup(model.tissue_color_analysis?.dominant_group)}</td>
        <td>${qualityLabel}</td>
        <td>
          <span class="status-badge ${entry.clinician_status}">
            <i></i>${statusText}
          </span>
        </td>
        <td>
          <button class="secondary-button compact review-btn" data-id="${entry.id}">
            Assess Check-in
          </button>
        </td>
      </tr>
    `;
  }).join("");
  
  // Bind Assess button click
  document.querySelectorAll(".review-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const entryId = btn.dataset.id;
      state.selectedEntry = state.queue.find(e => String(e.id) === String(entryId));
      showView("assessment");
    });
  });
}

// ── Patient Directory Operations & Renderers ───────────────

function renderPatientsTable() {
  // Group by patient
  const patientsMap = {};
  state.queue.forEach(entry => {
    if (!patientsMap[entry.user_id]) {
      patientsMap[entry.user_id] = {
        username: entry.username,
        submissionsCount: 0,
        entries: []
      };
    }
    patientsMap[entry.user_id].submissionsCount++;
    patientsMap[entry.user_id].entries.push(entry);
  });
  
  // Sort entries chronologically
  Object.keys(patientsMap).forEach(uid => {
    patientsMap[uid].entries.sort((a, b) => new Date(b.date) - new Date(a.date));
  });
  
  let patientsList = Object.values(patientsMap);
  
  // Filter by search
  const searchQuery = patientSearchInput.value.toLowerCase().trim();
  if (searchQuery) {
    patientsList = patientsList.filter(p => p.username.toLowerCase().includes(searchQuery));
  }
  
  const emptyState = document.querySelector("#patients-empty");
  const table = document.querySelector("#patients-table");
  
  if (patientsList.length === 0) {
    emptyState.classList.remove("hidden");
    table.classList.add("hidden");
    return;
  }
  
  emptyState.classList.add("hidden");
  table.classList.remove("hidden");
  
  patientsTbody.innerHTML = patientsList.map(p => {
    const latest = p.entries[0];
    const statusText = latest.clinician_status.charAt(0).toUpperCase() + latest.clinician_status.slice(1);
    
    return `
      <tr>
        <td><strong>${p.username}</strong></td>
        <td>${p.submissionsCount} check-ins</td>
        <td>${formatFullDate(latest.date)}</td>
        <td>
          <span class="status-badge ${latest.clinician_status}">
            <i></i>${statusText}
          </span>
        </td>
        <td>
          <button class="secondary-button compact view-history-btn" data-user-id="${latest.user_id}">
            View History (${p.submissionsCount})
          </button>
        </td>
      </tr>
    `;
  }).join("");
  
  document.querySelectorAll(".view-history-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const uid = btn.dataset.userId;
      const patient = patientsList.find(p => p.entries[0].user_id === uid);
      if (patient && patient.entries.length > 0) {
        state.selectedEntry = patient.entries[0]; // Select latest entry
        showView("assessment");
      }
    });
  });
}

patientSearchInput.addEventListener("input", renderPatientsTable);

// ── Assessment Workspace & Splitted Panel View ─────────────

const workspaceBackBtn = document.querySelector("#workspace-back-btn");
const maskToggleCheckbox = document.querySelector("#mask-toggle-checkbox");
const clinicalAssessmentForm = document.querySelector("#clinical-assessment-form");

workspaceBackBtn.addEventListener("click", () => {
  // Return to the active navigation view
  showView(state.activeView === "assessment" ? "queue" : state.activeView);
});

maskToggleCheckbox.addEventListener("change", () => {
  const mask = document.querySelector("#assessment-mask");
  mask.classList.toggle("hidden", !maskToggleCheckbox.checked);
});

function renderAssessmentWorkspace() {
  const entry = state.selectedEntry;
  if (!entry) return;
  
  const model = entry.modelAnalysis;
  
  // Left Panel data
  document.querySelector("#workspace-username").textContent = entry.username;
  document.querySelector("#assessment-photo").src = entry.photo;
  
  const maskImg = document.querySelector("#assessment-mask");
  if (model.segmentation?.mask_data_url) {
    maskImg.src = model.segmentation.mask_data_url;
    maskImg.style.display = "block";
    document.querySelector(".overlay-legend-row").style.display = "flex";
  } else {
    maskImg.style.display = "none";
    document.querySelector(".overlay-legend-row").style.display = "none";
  }
  
  maskToggleCheckbox.checked = true;
  maskImg.classList.remove("hidden");
  
  // Right Panel: Metrics
  document.querySelector("#metric-coverage").textContent = `${model.segmentation.coverage_percent}%`;
  document.querySelector("#metric-perimeter").textContent = `${model.segmentation.perimeter_pixels} px`;
  document.querySelector("#metric-circularity").textContent = model.features.shape_circularity;
  
  // Quality Checks
  const qualityChipsRow = document.querySelector("#quality-chips-row");
  const quality = model.photo_quality;
  if (quality.notes.length === 0) {
    qualityChipsRow.innerHTML = `<span class="quality-chip passed">✓ Lighting check passed</span><span class="quality-chip passed">✓ Focus check passed</span>`;
  } else {
    qualityChipsRow.innerHTML = quality.notes.map(note => `
      <span class="quality-chip warning">⚠️ ${note}</span>
    `).join("");
  }
  
  // Tissue colors composition
  const tissueWrap = document.querySelector("#tissue-composition-wrap");
  if (model.tissue_color_analysis) {
    tissueWrap.innerHTML = renderTissueComposition(model.tissue_color_analysis);
  } else {
    tissueWrap.innerHTML = `<div style="color: var(--muted); font-size:12px; margin-top:16px;">Tissue-color calculations unavailable.</div>`;
  }
  
  // Fill Review Form
  const statusRadios = document.getElementsByName("review-status");
  statusRadios.forEach(radio => {
    radio.checked = (radio.value === entry.clinician_status);
  });
  
  document.querySelector("#review-note").value = entry.clinician_note || "";
  
  // Render longitudinal check-in history of this patient
  const patientEntries = state.queue.filter(e => e.user_id === entry.user_id);
  // Sort reverse chronological
  patientEntries.sort((a, b) => new Date(b.date) - new Date(a.date));
  
  assessmentHistoryList.innerHTML = patientEntries.map(pe => {
    const isCurrent = pe.id === entry.id;
    const dateStr = formatFullDate(pe.date);
    const statusText = pe.clinician_status.charAt(0).toUpperCase() + pe.clinician_status.slice(1);
    
    return `
      <div class="history-card-item ${isCurrent ? 'active' : ''}" data-history-id="${pe.id}">
        <img class="history-thumb" src="${pe.photo}" alt="Historical upload" />
        <div class="history-details">
          <strong>${dateStr}</strong>
          <span>Coverage: ${pe.modelAnalysis.segmentation.coverage_percent}%</span>
          <span class="mini-status ${pe.clinician_status}">${statusText}</span>
        </div>
      </div>
    `;
  }).join("");
  
  // Bind history clicks
  document.querySelectorAll(".history-card-item").forEach(item => {
    item.addEventListener("click", () => {
      const histId = item.dataset.historyId;
      state.selectedEntry = state.queue.find(e => String(e.id) === String(histId));
      renderAssessmentWorkspace();
    });
  });
}

function renderTissueComposition(tissue) {
  const groups = [
    ["red_pink_like", "red-pink", "Red/Pink (Granulation)"],
    ["yellow_tan_like", "yellow-tan", "Yellow/Tan (Slough)"],
    ["dark_like", "dark", "Dark (Eschar)"],
    ["pale_like", "pale", "Pale (Epithelial)"],
    ["unclassified", "other", "Unclassified"]
  ];
  
  return `
    <div style="margin-top: 20px;">
      <strong style="display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 8px;">Segmented Tissue Composition</strong>
      <div style="display: flex; flex-direction: column; gap: 8px; padding: 4px 0;">
        ${groups.map(([key, cssClass, label]) => {
          const pct = tissue.percentages[key] || 0;
          return `
            <div style="display: flex; align-items: center; justify-content: space-between; font-size: 12px;">
              <span style="width: 150px; text-align: left; color: var(--muted); font-size:11px;">${label}</span>
              <div style="flex-grow: 1; margin: 0 12px; height: 8px; background: #e3eeee; border-radius: 4px; overflow: hidden; position: relative;">
                <div style="position: absolute; left: 0; top: 0; bottom: 0; width: ${pct}%; background: ${getTissueColor(key)};"></div>
              </div>
              <strong style="width: 36px; text-align: right; color: var(--ink); font-size:11px;">${pct}%</strong>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function getTissueColor(group) {
  return {
    red_pink_like: "#e17f6b",
    yellow_tan_like: "#e5b567",
    dark_like: "#2c3e50",
    pale_like: "#cfeee8",
    unclassified: "#9bb5b8"
  }[group] || "#9bb5b8";
}

// Handle clinical assessment submission
clinicalAssessmentForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const entry = state.selectedEntry;
  if (!entry) return;
  
  const statusRadios = document.getElementsByName("review-status");
  let selectedStatus = "unreviewed";
  statusRadios.forEach(radio => {
    if (radio.checked) selectedStatus = radio.value;
  });
  
  const noteText = document.querySelector("#review-note").value.trim();
  const saveBtn = document.querySelector("#save-review-btn");
  
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving Assessment...";
  
  try {
    const res = await authFetch("/api/clinician/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entry_id: entry.id,
        status: selectedStatus,
        note: noteText
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to save review.");
    
    showToast("Assessment saved successfully!");
    
    // Update local state queue
    const queueIdx = state.queue.findIndex(e => String(e.id) === String(entry.id));
    if (queueIdx !== -1) {
      state.queue[queueIdx].clinician_status = selectedStatus;
      state.queue[queueIdx].clinician_note = noteText;
      state.queue[queueIdx].reviewed_by = data.reviewed_by;
      state.queue[queueIdx].reviewed_at = data.reviewed_at;
    }
    
    // Recalculate and re-render
    calculateStats();
    
    // Re-render current assessment workspace to update details (like status badge in patient history)
    state.selectedEntry = state.queue[queueIdx];
    renderAssessmentWorkspace();
    
  } catch (err) {
    showToast(err.message);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save Assessment and Status";
  }
});

// ── Boot ────────────────────────────────────────────────

if (state.token) {
  enterApp();
} else {
  exitApp();
}
