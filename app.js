import { analyzePhoto } from "./js/api.js";
import { login, register, logout, isLoggedIn, getCurrentUser } from "./js/auth.js";
import { bindNavigation, showView } from "./js/navigation.js";
import { addEntry, loadEntries, state } from "./js/state.js";
import { bindUpload, resetUpload } from "./js/upload.js";
import { renderAll, renderResult, setNextCheckinDate, updateUserProfile } from "./js/views.js";
import { showToast } from "./js/utils.js";

const authView = document.querySelector("#auth-view");
const appShell = document.querySelector("#app-shell");
const submitButton = document.querySelector('#checkin-form button[type="submit"]');

// ── Auth UI ─────────────────────────────────────────────

const tabLogin = document.querySelector("#tab-login");
const tabRegister = document.querySelector("#tab-register");
const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const authError = document.querySelector("#auth-error");
const logoutButton = document.querySelector("#logout-button");

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

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthError();
  const username = document.querySelector("#login-username").value.trim();
  const password = document.querySelector("#login-password").value;
  if (!username || !password) return showAuthError("Please fill in all fields.");
  try {
    disableAuthForms(true);
    await login(username, password);
    await enterApp();
  } catch (error) {
    showAuthError(error.message);
  } finally {
    disableAuthForms(false);
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthError();
  const username = document.querySelector("#register-username").value.trim();
  const password = document.querySelector("#register-password").value;
  const confirm = document.querySelector("#register-confirm").value;
  if (!username || !password || !confirm) return showAuthError("Please fill in all fields.");
  if (password !== confirm) return showAuthError("Passwords do not match.");
  if (password.length < 4) return showAuthError("Password must be at least 4 characters.");
  try {
    disableAuthForms(true);
    await register(username, password);
    await enterApp();
  } catch (error) {
    showAuthError(error.message);
  } finally {
    disableAuthForms(false);
  }
});

logoutButton.addEventListener("click", () => {
  logout();
  exitApp();
});

function disableAuthForms(disabled) {
  loginForm.querySelectorAll("input, button").forEach((el) => (el.disabled = disabled));
  registerForm.querySelectorAll("input, button").forEach((el) => (el.disabled = disabled));
}

// ── App lifecycle ───────────────────────────────────────

async function enterApp() {
  authView.classList.add("hidden");
  appShell.classList.remove("hidden");
  updateUserProfile();
  await loadEntries();
  renderAll();
  setNextCheckinDate();
  showView("dashboard");
}

function exitApp() {
  appShell.classList.add("hidden");
  authView.classList.remove("hidden");
  loginForm.reset();
  registerForm.reset();
  hideAuthError();
  switchAuthTab("login");
}

// ── Photo analysis ──────────────────────────────────────

bindNavigation();
bindUpload();
bindPhotoAnalysis();

function bindPhotoAnalysis() {
  document.querySelector("#checkin-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.currentPhoto) return showToast("Add a clear wound photo before running the analysis.");
    if (!document.querySelector("#prototype-consent").checked) {
      return showToast("Please confirm that you understand the prototype's limits.");
    }

    setLoading(true);
    try {
      const entry = {
        id: Date.now(),
        date: new Date().toISOString(),
        photo: state.currentPhoto,
        modelAnalysis: await analyzePhoto(state.currentPhoto),
      };
      await addEntry(entry);
      renderAll();
      renderResult(entry);
      resetUpload();
      document.querySelector("#checkin-form").reset();
      showView("result");
    } catch (error) {
      showToast(error.message);
    } finally {
      setLoading(false);
    }
  });
}

function setLoading(loading) {
  submitButton.disabled = loading;
  submitButton.innerHTML = loading
    ? "Running AI models..."
    : 'Analyze and save check-in <svg viewBox="0 0 24 24"><path d="m9 18 6-6-6-6" /></svg>';
}

// ── Boot ────────────────────────────────────────────────

if (isLoggedIn()) {
  enterApp();
}
