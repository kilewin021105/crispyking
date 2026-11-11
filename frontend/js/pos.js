/* Staff & Admin dashboard: login, order management, inventory, ingredients,
   expenses, reports, settings, suppliers. */
let currentUser = JSON.parse(sessionStorage.getItem("ck_user") || "null");

function isAdmin() {
  return !!currentUser && currentUser.role === "admin";
}

function applyRoleVisibility() {
  const admin = isAdmin();
  document.querySelectorAll("[data-admin-only]").forEach((el) => {
    el.classList.toggle("d-none", !admin);
  });
}

function resetToOrdersTab() {
  // Always land on Orders after login — also guards against an admin-only
  // tab-pane staying visible if a different role logs in in the same tab
  // without a page reload.
  document.querySelectorAll("#posTabs button").forEach((b) => b.classList.remove("active"));
  document.querySelector('#posTabs button[data-tab="orders"]').classList.add("active");
  document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("d-none"));
  document.getElementById("tab-orders").classList.remove("d-none");
}

function showDashboard() {
  document.getElementById("login-section").classList.add("d-none");
  document.getElementById("dashboard-section").classList.remove("d-none");
  document.getElementById("logout-btn").classList.remove("d-none");
  document.getElementById("whoami").textContent = `${currentUser.full_name} (${currentUser.role})`;
  applyRoleVisibility();
  resetToOrdersTab();
  loadOrders();
}

function showLogin() {
  document.getElementById("login-section").classList.remove("d-none");
  document.getElementById("dashboard-section").classList.add("d-none");
  document.getElementById("logout-btn").classList.add("d-none");
  document.getElementById("whoami").textContent = "";
}

document.getElementById("login-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;
  try {
    const { data } = await api.post("/auth/login", { username, password });
    currentUser = data;
    sessionStorage.setItem("ck_user", JSON.stringify(data));
    showDashboard();
  } catch (err) {
    toast(err.message, "danger");
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  sessionStorage.removeItem("ck_user");
  currentUser = null;
  showLogin();
});

// ---- Tabs -------------------------------------------------------------
document.querySelectorAll("#posTabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#posTabs button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("d-none"));
    const tab = document.getElementById(`tab-${btn.dataset.tab}`);
    tab.classList.remove("d-none");

    if (btn.dataset.tab === "orders") loadOrders();
    if (btn.dataset.tab === "inventory") loadInventory();
    if (btn.dataset.tab === "ingredients") loadIngredients();
    if (btn.dataset.tab === "expenses") { loadExpenseCategories(); loadExpenses(); }
    if (btn.dataset.tab === "reports") loadReports();
    if (btn.dataset.tab === "settings") loadSettings();
    if (btn.dataset.tab === "suppliers") loadSuppliers();
  });
});

// ---- Orders -------------------------------------------------------------
const STATUS_FLOW = { pending: "preparing", preparing: "ready", ready: "completed" };

async function loadOrders() {
  const status = document.getElementById("order-status-filter").value;
  const params = status ? `?status=${status}` : "";
  try {
    const { data } = await api.get(`/orders${params}`);
    const tbody = document.getElementById("orders-tbody");
    tbody.innerHTML = data.map((o) => `
      <tr>
        <td>#${o.order_id}</td>
        <td><span class="badge text-bg-light">${o.order_type}</span></td>
        <td>${o.customer_name || "—"} ${o.table_number ? `(Table ${o.table_number})` : ""}</td>
        <td>${o.item_count}</td>
        <td>${money(o.total_amount)}</td>
        <td><span class="badge ${statusBadge(o.status)}">${o.status}</span></td>
        <td>${orderActions(o)}</td>
      </tr>`).join("") || `<tr><td colspan="7" class="text-muted text-center">No orders</td></tr>`;
  } catch (err) {
    toast(err.message, "danger");
  }
}

function statusBadge(status) {
  return {
    pending: "text-bg-secondary",
    preparing: "text-bg-warning",
    ready: "text-bg-info",
    completed: "text-bg-success",
    cancelled: "text-bg-danger",
  }[status] || "text-bg-light";
}

function orderActions(o) {
  let html = "";
  if (STATUS_FLOW[o.status]) {
    html += `<button class="btn btn-sm btn-crispy me-1" onclick="advanceOrder(${o.order_id}, '${STATUS_FLOW[o.status]}')">
      Mark ${STATUS_FLOW[o.status]}
    </button>`;
  }
  if (o.status === "pending" || o.status === "preparing") {
    html += `<button class="btn btn-sm btn-outline-danger" onclick="advanceOrder(${o.order_id}, 'cancelled')">Cancel</button>`;
  }
  return html || "—";
}

async function advanceOrder(orderId, status) {
  try {
    await api.put(`/orders/${orderId}/status`, { status });
    toast(`Order #${orderId} → ${status}`);
    loadOrders();
  } catch (err) {
    toast(err.message, "danger");
  }
}

document.getElementById("order-status-filter").addEventListener("change", loadOrders);
document.getElementById("refresh-orders-btn").addEventListener("click", loadOrders);

// ---- Inventory (finished menu items) -------------------------------------
async function loadInventory() {
  try {
    const { data } = await api.get("/inventory");
    const tbody = document.getElementById("inventory-tbody");
    tbody.innerHTML = data.map((p) => `
      <tr class="${p.low_stock ? "low-stock-row" : ""}">
        <td>${p.sku || "—"}</td>
        <td>${p.name}</td>
        <td>${p.category}</td>
        <td>${p.stock_quantity}${p.low_stock ? ' <span class="badge text-bg-warning">Low</span>' : ""}</td>
        <td>${p.reorder_level}</td>
        <td><button class="btn btn-sm btn-outline-secondary" onclick="quickRestock(${p.product_id})">+Restock</button></td>
      </tr>`).join("") || `<tr><td colspan="6" class="text-muted text-center">No menu items</td></tr>`;

    const select = document.getElementById("restock-product");
    select.innerHTML = data.map((p) => `<option value="${p.product_id}">${p.name} (stock: ${p.stock_quantity})</option>`).join("");
  } catch (err) {
    toast(err.message, "danger");
  }
}

function quickRestock(productId) {
  document.getElementById("restock-product").value = productId;
  document.getElementById("restock-quantity").focus();
}

document.getElementById("restock-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const productId = document.getElementById("restock-product").value;
  const quantity = document.getElementById("restock-quantity").value;
  const note = document.getElementById("restock-note").value;
  try {
    await api.post("/inventory/restock", { product_id: Number(productId), quantity: Number(quantity), note });
    toast("Stock updated");
    document.getElementById("restock-form").reset();
    loadInventory();
  } catch (err) {
    toast(err.message, "danger");
  }
});

// ---- Ingredients (raw materials: oil, flour, wrappers, gas...) -----------
async function loadIngredients() {
  try {
    const { data } = await api.get("/ingredients");
    const tbody = document.getElementById("ingredients-tbody");
    tbody.innerHTML = data.map((i) => `
      <tr class="${i.low_stock ? "low-stock-row" : ""}">
        <td>${i.name}</td>
        <td>${i.unit}</td>
        <td>${i.stock_quantity}${i.low_stock ? ' <span class="badge text-bg-warning">Low</span>' : ""}</td>
        <td>${i.reorder_level}</td>
        <td>${money(i.cost_per_unit)}</td>
        <td>${i.supplier_name || "—"}</td>
        <td><button class="btn btn-sm btn-outline-secondary" onclick="quickIngredientRestock(${i.ingredient_id})">+Restock</button></td>
      </tr>`).join("") || `<tr><td colspan="7" class="text-muted text-center">No ingredients yet — add one on the right</td></tr>`;

    const select = document.getElementById("ingredient-restock-select");
    select.innerHTML = data.map((i) => `<option value="${i.ingredient_id}">${i.name} (${i.stock_quantity} ${i.unit})</option>`).join("");

    document.getElementById("ing-stat-count").textContent = data.length;
    document.getElementById("ing-stat-low").textContent = data.filter((i) => i.low_stock).length;

    const { data: valueData } = await api.get("/ingredients/value");
    document.getElementById("ing-stat-value").textContent = money(valueData.total_stock_value);
  } catch (err) {
    toast(err.message, "danger");
  }
}

function quickIngredientRestock(ingredientId) {
  document.getElementById("ingredient-restock-select").value = ingredientId;
  document.getElementById("ingredient-restock-quantity").focus();
}

document.getElementById("ingredient-restock-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const ingredient_id = Number(document.getElementById("ingredient-restock-select").value);
  const quantity = Number(document.getElementById("ingredient-restock-quantity").value);
  const note = document.getElementById("ingredient-restock-note").value;
  try {
    await api.post("/ingredients/restock", { ingredient_id, quantity, note });
    toast("Ingredient stock updated");
    document.getElementById("ingredient-restock-form").reset();
    loadIngredients();
  } catch (err) {
    toast(err.message, "danger");
  }
});

document.getElementById("ingredient-add-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const payload = {
    name: document.getElementById("ingredient-add-name").value.trim(),
    unit: document.getElementById("ingredient-add-unit").value.trim() || "pcs",
    cost_per_unit: Number(document.getElementById("ingredient-add-cost").value || 0),
    stock_quantity: Number(document.getElementById("ingredient-add-stock").value || 0),
    reorder_level: Number(document.getElementById("ingredient-add-reorder").value || 0),
  };
  try {
    await api.post("/ingredients", payload);
    toast(`Added '${payload.name}' to ingredients`);
    document.getElementById("ingredient-add-form").reset();
    loadIngredients();
  } catch (err) {
    toast(err.message, "danger");
  }
});

// ---- Expenses (admin only) -----------------------------------------------
function setDefaultExpenseDate() {
  const field = document.getElementById("expense-date");
  if (field && !field.value) field.value = new Date().toISOString().slice(0, 10);
}
setDefaultExpenseDate();

async function loadExpenseCategories() {
  try {
    const { data } = await api.get("/expenses/categories");
    const addSelect = document.getElementById("expense-category");
    const previous = addSelect.value;
    addSelect.innerHTML = data.map((c) => `<option value="${c}">${c}</option>`).join("")
      + `<option value="__other">Other (type below)</option>`;
    if (previous) addSelect.value = previous;

    const filterSelect = document.getElementById("expense-filter-category");
    const previousFilter = filterSelect.value;
    filterSelect.innerHTML = `<option value="">All categories</option>`
      + data.map((c) => `<option value="${c}">${c}</option>`).join("");
    filterSelect.value = previousFilter;
  } catch (err) {
    console.error(err);
  }
}

document.getElementById("expense-category").addEventListener("change", (evt) => {
  const otherInput = document.getElementById("expense-category-other");
  const isOther = evt.target.value === "__other";
  otherInput.classList.toggle("d-none", !isOther);
  if (isOther) otherInput.focus();
});

async function loadExpenses() {
  const params = new URLSearchParams();
  const start = document.getElementById("expense-filter-start").value;
  const end = document.getElementById("expense-filter-end").value;
  const category = document.getElementById("expense-filter-category").value;
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  if (category) params.set("category", category);

  try {
    const { data, total_amount } = await api.get(`/expenses?${params.toString()}`);
    const tbody = document.getElementById("expenses-tbody");
    tbody.innerHTML = data.map((e) => `
      <tr>
        <td>${e.expense_date}</td>
        <td>${e.category}</td>
        <td>${e.description || "—"}</td>
        <td>${money(e.amount)}</td>
        <td class="text-capitalize">${e.payment_method.replace("_", " ")}</td>
        <td>${e.recorded_by_name || "—"}</td>
        <td><button class="btn btn-sm btn-outline-danger" onclick="deleteExpense(${e.expense_id})">Delete</button></td>
      </tr>`).join("") || `<tr><td colspan="7" class="text-muted text-center">No expenses recorded for this filter</td></tr>`;

    // "Total Expenses" — the headline number for this module.
    document.getElementById("exp-stat-total").textContent = money(total_amount);
    document.getElementById("exp-stat-count").textContent = data.length;

    const byCategory = {};
    data.forEach((e) => { byCategory[e.category] = (byCategory[e.category] || 0) + e.amount; });
    const top = Object.entries(byCategory).sort((a, b) => b[1] - a[1])[0];
    document.getElementById("exp-stat-top").textContent = top ? top[0] : "—";
  } catch (err) {
    toast(err.message, "danger");
  }
}

document.getElementById("expense-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const categorySelect = document.getElementById("expense-category").value;
  const category = categorySelect === "__other"
    ? document.getElementById("expense-category-other").value.trim()
    : categorySelect;
  if (!category) {
    toast("Please choose or type a category", "warning");
    return;
  }

  const payload = {
    category,
    description: document.getElementById("expense-description").value || null,
    amount: Number(document.getElementById("expense-amount").value),
    expense_date: document.getElementById("expense-date").value,
    payment_method: document.getElementById("expense-payment-method").value,
    recorded_by: currentUser ? currentUser.user_id : null,
  };
  try {
    await api.post("/expenses", payload);
    toast("Expense saved");
    document.getElementById("expense-form").reset();
    document.getElementById("expense-category-other").classList.add("d-none");
    setDefaultExpenseDate();
    await loadExpenseCategories();
    loadExpenses();
  } catch (err) {
    toast(err.message, "danger");
  }
});

async function deleteExpense(expenseId) {
  if (!confirm("Delete this expense entry? This can't be undone.")) return;
  try {
    await api.del(`/expenses/${expenseId}`);
    toast("Expense deleted");
    loadExpenses();
  } catch (err) {
    toast(err.message, "danger");
  }
}

document.getElementById("expense-filter-apply").addEventListener("click", loadExpenses);
document.getElementById("expense-filter-reset").addEventListener("click", () => {
  document.getElementById("expense-filter-start").value = "";
  document.getElementById("expense-filter-end").value = "";
  document.getElementById("expense-filter-category").value = "";
  loadExpenses();
});

// ---- Reports --------------------------------------------------------------
let dailySalesChart = null;
let expensesCategoryChart = null;

function reportsDays() {
  return Number(document.getElementById("reports-days").value);
}

async function loadReports() {
  const days = reportsDays();
  const admin = isAdmin();
  try {
    const requests = [
      api.get(`/reports/summary?days=${days}`),
      api.get(`/reports/top-products?limit=5&days=${days}`),
      api.get(`/reports/sales-by-category?days=${days}`),
      api.get(`/reports/inventory-value`),
      api.get(`/reports/daily-sales?days=${days}`),
    ];
    if (admin) requests.push(api.get(`/reports/profit-loss?days=${days}`));

    const results = await Promise.all(requests);
    const [{ data: summary }, { data: top }, { data: byCategory }, { data: stockValue }, { data: dailySales }] = results;

    document.getElementById("stat-orders").textContent = summary.summary.order_count;
    document.getElementById("stat-revenue").textContent = money(summary.summary.total_revenue);
    document.getElementById("stat-avg").textContent = money(summary.summary.avg_order_value);
    document.getElementById("stat-stock-value").textContent = money(stockValue.total_stock_value);

    document.getElementById("top-products-tbody").innerHTML = top.map((p) => `
      <tr><td>${p.name}</td><td>${p.units_sold}</td><td>${money(p.revenue)}</td></tr>
    `).join("") || `<tr><td colspan="3" class="text-muted">No completed sales yet</td></tr>`;

    document.getElementById("category-sales-tbody").innerHTML = byCategory.map((c) => `
      <tr><td>${c.category}</td><td>${c.units_sold}</td><td>${money(c.revenue)}</td></tr>
    `).join("") || `<tr><td colspan="3" class="text-muted">No completed sales yet</td></tr>`;

    renderDailySalesChart(dailySales);

    if (admin) {
      const { data: pl } = results[5];
      renderProfitLoss(pl);
      renderExpensesCategoryChart(pl.expenses_by_category);
    }
  } catch (err) {
    toast(err.message, "danger");
  }
}

function renderProfitLoss(pl) {
  document.getElementById("pl-revenue").textContent = money(pl.revenue);
  document.getElementById("pl-cogs").textContent = money(pl.cogs);
  document.getElementById("pl-gross").textContent = money(pl.gross_profit);
  // "Total Expenses" — always shown alongside revenue/COGS so cost never gets lost.
  document.getElementById("pl-expenses").textContent = money(pl.total_expenses);
  document.getElementById("pl-net").textContent = money(pl.net_profit);

  const netCard = document.getElementById("pl-net-card");
  const netLabel = document.getElementById("pl-net-label");
  netCard.classList.remove("bg-green", "bg-red");
  if (pl.net_profit >= 0) {
    netCard.classList.add("bg-green");
    netLabel.textContent = "Net Profit";
  } else {
    netCard.classList.add("bg-red");
    netLabel.textContent = "Net Loss";
  }
}

function renderDailySalesChart(rows) {
  const ctx = document.getElementById("chart-daily-sales");
  if (!ctx || typeof Chart === "undefined") return;

  if (dailySalesChart) dailySalesChart.destroy();
  dailySalesChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: rows.map((r) => r.day),
      datasets: [{
        label: "Revenue",
        data: rows.map((r) => r.revenue),
        borderColor: "#d81324",
        backgroundColor: "rgba(216, 19, 36, 0.1)",
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: "#d81324",
        pointBorderColor: "#fff",
        pointBorderWidth: 2,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (item) => money(item.parsed.y) } },
      },
      scales: {
        y: { beginAtZero: true, grid: { color: "#f1e7db" }, ticks: { callback: (v) => money(v) } },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderExpensesCategoryChart(rows) {
  const ctx = document.getElementById("chart-expenses-category");
  if (!ctx || typeof Chart === "undefined") return;
  const sorted = [...rows].sort((a, b) => b.total - a.total);

  if (expensesCategoryChart) expensesCategoryChart.destroy();
  expensesCategoryChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map((r) => r.category),
      datasets: [{
        label: "Expenses",
        data: sorted.map((r) => r.total),
        backgroundColor: "#a30d1c",
        borderRadius: 4,
        maxBarThickness: 24,
      }],
    },
    options: {
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (item) => money(item.parsed.x) } },
      },
      scales: {
        x: { beginAtZero: true, grid: { color: "#f1e7db" }, ticks: { callback: (v) => money(v) } },
        y: { grid: { display: false } },
      },
    },
  });
}

document.getElementById("reports-days").addEventListener("change", loadReports);

// ---- Settings (admin only) -------------------------------------------------
async function loadSettings() {
  try {
    const { data } = await api.get("/settings");
    document.getElementById("settings-business-name").value = data.business_name || "";
    document.getElementById("settings-currency-symbol").value = data.currency_symbol || "";
    document.getElementById("settings-tax-rate").value = Number((parseFloat(data.tax_rate || 0) * 100).toFixed(2));
    document.getElementById("settings-business-phone").value = data.business_phone || "";
    document.getElementById("settings-business-address").value = data.business_address || "";
    document.getElementById("settings-receipt-footer").value = data.receipt_footer || "";
  } catch (err) {
    toast(err.message, "danger");
  }
}

document.getElementById("settings-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const payload = {
    business_name: document.getElementById("settings-business-name").value.trim(),
    currency_symbol: document.getElementById("settings-currency-symbol").value.trim(),
    tax_rate: (Number(document.getElementById("settings-tax-rate").value) / 100).toFixed(4),
    business_phone: document.getElementById("settings-business-phone").value.trim(),
    business_address: document.getElementById("settings-business-address").value.trim(),
    receipt_footer: document.getElementById("settings-receipt-footer").value.trim(),
  };
  try {
    await api.put("/settings", payload);
    await loadSiteSettings();
    toast("Settings saved — applied across the whole system");
  } catch (err) {
    toast(err.message, "danger");
  }
});

// ---- Suppliers --------------------------------------------------------------
async function loadSuppliers() {
  try {
    const { data } = await api.get("/suppliers");
    document.getElementById("suppliers-tbody").innerHTML = data.map((s) => `
      <tr>
        <td>${s.name}</td>
        <td>${s.contact_person || "—"}</td>
        <td>${s.phone || "—"}</td>
        <td>${s.email || "—"}</td>
        <td><button class="btn btn-sm btn-outline-secondary" onclick="viewSupplier(${s.supplier_id})">View</button></td>
      </tr>`).join("");
  } catch (err) {
    toast(err.message, "danger");
  }
}

async function viewSupplier(id) {
  try {
    const { data } = await api.get(`/suppliers/${id}`);
    const products = data.products.map((p) => `${p.name} (${money(p.price)})`).join(", ") || "No products linked";
    alert(`${data.name}\nProducts: ${products}`);
  } catch (err) {
    toast(err.message, "danger");
  }
}

// ---- Init --------------------------------------------------------------
(async function init() {
  await loadSiteSettings();
  if (currentUser) {
    showDashboard();
  } else {
    showLogin();
  }
})();
