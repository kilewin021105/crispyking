/* Thin wrapper around fetch() for the POS REST API. All endpoints return
   { success, data|error, ... } JSON — this normalizes error handling. */
const API_BASE = "/api";

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  let body;
  try {
    body = await res.json();
  } catch {
    throw new Error(`Server returned a non-JSON response (status ${res.status})`);
  }

  if (!res.ok || body.success === false) {
    throw new Error(body.error || `Request failed (status ${res.status})`);
  }
  return body;
}

const api = {
  get: (path) => apiRequest(path),
  post: (path, data) => apiRequest(path, { method: "POST", body: JSON.stringify(data) }),
  put: (path, data) => apiRequest(path, { method: "PUT", body: JSON.stringify(data) }),
  del: (path) => apiRequest(path, { method: "DELETE" }),
};

/* ---- Site settings (business name / currency / tax rate) --------------
   Loaded once at startup on every page so the whole system is
   reconfigurable from the Settings tab instead of hardcoded. */
let siteSettings = { currency_symbol: "$", tax_rate: "0.10", business_name: "Crispy King" };

function money(n) {
  return `${siteSettings.currency_symbol}${Number(n).toFixed(2)}`;
}

function taxRate() {
  return parseFloat(siteSettings.tax_rate) || 0;
}

async function loadSiteSettings() {
  try {
    const { data } = await api.get("/settings");
    siteSettings = data;
    document.querySelectorAll("[data-site-business-name]").forEach((el) => {
      el.textContent = data.business_name || el.textContent;
    });
  } catch (err) {
    console.error("Could not load site settings, using defaults:", err.message);
  }
  return siteSettings;
}

function toast(message, variant = "success") {
  const container = document.getElementById("toast-container");
  if (!container) {
    alert(message);
    return;
  }
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${variant} border-0`;
  el.setAttribute("role", "alert");
  el.innerHTML = `<div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(el);
  const toastInstance = new bootstrap.Toast(el, { delay: 4000 });
  toastInstance.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}
