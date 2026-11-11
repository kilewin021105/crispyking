/* Customer ordering page: menu browsing + floating cart + slide-in checkout. */
let allProducts = [];
let selectedCategory = "";
const cart = new Map(); // product_id -> { product, quantity }

const cartOffcanvasEl = document.getElementById("cartOffcanvas");
const cartOffcanvas = new bootstrap.Offcanvas(cartOffcanvasEl);
const successModal = new bootstrap.Modal(document.getElementById("successModal"));

const CATEGORY_EMOJI = {
  Chicken: "🍗",
  "Street Food": "🥟",
  Beverages: "🥤",
};
function emojiFor(category) {
  return CATEGORY_EMOJI[category] || "🍽️";
}

// ---------------------------------------------------------------- Menu ----
async function loadCategories() {
  try {
    const { data } = await api.get("/menu/categories");
    const container = document.getElementById("category-pills");
    data.forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pill";
      btn.dataset.category = cat;
      btn.textContent = `${emojiFor(cat)} ${cat}`;
      container.appendChild(btn);
    });
    container.addEventListener("click", (evt) => {
      const btn = evt.target.closest(".pill");
      if (!btn) return;
      container.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      selectedCategory = btn.dataset.category;
      loadMenu();
    });
  } catch (err) {
    console.error(err);
  }
}

async function loadMenu() {
  const search = document.getElementById("search-input").value;
  const params = new URLSearchParams();
  if (selectedCategory) params.set("category", selectedCategory);
  if (search) params.set("search", search);

  try {
    const { data } = await api.get(`/menu?${params.toString()}`);
    allProducts = data;
    renderMenu(data);
  } catch (err) {
    document.getElementById("menu-container").innerHTML =
      `<div class="alert alert-danger">Failed to load menu: ${err.message}</div>`;
  }
}

function renderMenu(products) {
  const container = document.getElementById("menu-container");
  if (products.length === 0) {
    container.innerHTML = `<p class="text-muted">No items found.</p>`;
    return;
  }

  const byCategory = {};
  products.forEach((p) => {
    byCategory[p.category] = byCategory[p.category] || [];
    byCategory[p.category].push(p);
  });

  let html = "";
  Object.keys(byCategory).sort().forEach((cat) => {
    html += `<h6 class="category-heading">${emojiFor(cat)} ${cat}</h6><div class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3 mb-2">`;
    byCategory[cat].forEach((p) => {
      const outOfStock = p.stock_quantity <= 0;
      html += `
        <div class="col">
          <div class="card product-card h-100">
            <div class="product-thumb">
              ${emojiFor(p.category)}
              <span class="price-tag">${money(p.price)}</span>
            </div>
            <div class="card-body d-flex flex-column">
              <h6 class="card-title mb-1">${p.name}</h6>
              <p class="card-text small text-muted flex-grow-1">${p.description || ""}</p>
              ${outOfStock
                ? `<span class="badge bg-secondary">Out of stock</span>`
                : `<button class="btn btn-sm btn-crispy" onclick="addToCart(${p.product_id})">Add to cart</button>`
              }
            </div>
          </div>
        </div>`;
    });
    html += `</div>`;
  });
  container.innerHTML = html;
}

// ---------------------------------------------------------------- Cart ----
function cartCount() {
  let total = 0;
  cart.forEach(({ quantity }) => (total += quantity));
  return total;
}

function bumpCartFab() {
  const fab = document.getElementById("cart-fab");
  fab.classList.remove("bump");
  // force reflow so the animation can restart on rapid adds
  void fab.offsetWidth;
  fab.classList.add("bump");
}

function updateCartBadge() {
  const badge = document.getElementById("cart-badge");
  const count = cartCount();
  badge.textContent = count;
  badge.classList.toggle("d-none", count === 0);
}

function addToCart(productId) {
  const product = allProducts.find((p) => p.product_id === productId);
  if (!product) return;

  const entry = cart.get(productId) || { product, quantity: 0 };
  if (entry.quantity + 1 > product.stock_quantity) {
    toast(`Only ${product.stock_quantity} of '${product.name}' available`, "warning");
    return;
  }
  entry.quantity += 1;
  cart.set(productId, entry);
  renderCart();
  updateCartBadge();
  bumpCartFab();
}

function changeQty(productId, delta) {
  const entry = cart.get(productId);
  if (!entry) return;
  entry.quantity += delta;
  if (entry.quantity <= 0) {
    cart.delete(productId);
  } else if (entry.quantity > entry.product.stock_quantity) {
    entry.quantity = entry.product.stock_quantity;
  }
  renderCart();
  updateCartBadge();
}

function cartTotals() {
  let subtotal = 0;
  cart.forEach(({ product, quantity }) => (subtotal += product.price * quantity));
  const tax = subtotal * taxRate();
  return { subtotal, tax, total: subtotal + tax };
}

function renderCart() {
  const list = document.getElementById("cart-items");
  const checkoutBtn = document.getElementById("checkout-btn");

  if (cart.size === 0) {
    list.innerHTML = `
      <li class="list-group-item text-muted small border-0 px-0" id="cart-empty">
        🛒 Your cart is empty. Tap "Add to cart" on something tasty!
      </li>`;
    checkoutBtn.disabled = true;
  } else {
    let html = "";
    cart.forEach(({ product, quantity }) => {
      const lineTotal = product.price * quantity;
      html += `
        <li class="list-group-item cart-line-item d-flex justify-content-between align-items-center px-0">
          <div class="d-flex align-items-start">
            <span class="item-thumb">${emojiFor(product.category)}</span>
            <div>
              <div class="small fw-semibold">${product.name}</div>
              <div class="text-muted small mb-1">${money(product.price)} each</div>
              <div class="btn-group btn-group-sm qty-stepper" role="group">
                <button type="button" class="btn btn-outline-secondary" onclick="changeQty(${product.product_id}, -1)">−</button>
                <button type="button" class="btn btn-outline-secondary disabled">${quantity}</button>
                <button type="button" class="btn btn-outline-secondary" onclick="changeQty(${product.product_id}, 1)">+</button>
              </div>
            </div>
          </div>
          <span class="small fw-semibold">${money(lineTotal)}</span>
        </li>`;
    });
    list.innerHTML = html;
    checkoutBtn.disabled = false;
  }

  const { subtotal, tax, total } = cartTotals();
  document.getElementById("cart-subtotal").textContent = money(subtotal);
  document.getElementById("cart-tax").textContent = money(tax);
  document.getElementById("cart-total").textContent = money(total);
}

// ---------------------------------------------------------- Drawer steps ----
function showCartStep() {
  document.getElementById("checkout-view").classList.add("d-none");
  document.getElementById("checkout-view").classList.remove("d-flex");
  document.getElementById("cart-view").classList.remove("d-none");
  document.getElementById("cart-view").classList.add("d-flex");
  document.getElementById("offcanvas-title").textContent = "Your Cart";
}

function showCheckoutStep() {
  document.getElementById("cart-view").classList.add("d-none");
  document.getElementById("cart-view").classList.remove("d-flex");
  document.getElementById("checkout-view").classList.remove("d-none");
  document.getElementById("checkout-view").classList.add("d-flex");
  document.getElementById("offcanvas-title").textContent = "Checkout";
  document.getElementById("checkout-total").textContent = money(cartTotals().total);
}

document.getElementById("checkout-btn").addEventListener("click", () => {
  if (cart.size === 0) return;
  showCheckoutStep();
});
document.getElementById("back-to-cart-btn").addEventListener("click", showCartStep);

function toggleTableNumberField() {
  const isDineIn = document.getElementById("order-type").value === "dine-in";
  document.getElementById("table-number-group").style.display = isDineIn ? "block" : "none";
}
document.getElementById("order-type").addEventListener("change", toggleTableNumberField);

// ------------------------------------------------------------ Place order ----
async function placeOrder(evt) {
  evt.preventDefault();
  if (cart.size === 0) return;

  const payload = {
    order_type: document.getElementById("order-type").value,
    table_number: document.getElementById("table-number").value || null,
    customer_name: document.getElementById("customer-name").value || null,
    payment_method: document.getElementById("payment-method").value,
    items: Array.from(cart.values()).map(({ product, quantity }) => ({
      product_id: product.product_id,
      quantity,
    })),
  };

  const btn = document.getElementById("place-order-btn");
  btn.disabled = true;
  btn.textContent = "Processing payment…";

  try {
    const { data: order } = await api.post("/orders", payload);

    document.getElementById("success-subtitle").textContent =
      `Order #${order.order_id} · ${order.order_type === "dine-in" ? `Table ${order.table_number || "-"}` : "Takeout"}`;
    document.getElementById("success-body").innerHTML = `
      <ul class="list-unstyled mb-2">
        ${order.items.map((i) => `<li class="d-flex justify-content-between"><span>${i.quantity} × ${i.product_name}</span><span>${money(i.line_total)}</span></li>`).join("")}
      </ul>
      <hr class="my-2">
      <div class="d-flex justify-content-between"><span>Subtotal</span><span>${money(order.subtotal)}</span></div>
      <div class="d-flex justify-content-between"><span>Tax</span><span>${money(order.tax_amount)}</span></div>
      <div class="d-flex justify-content-between fw-bold"><span>Total paid</span><span>${money(order.total_amount)}</span></div>
      <div class="mt-2 text-muted">Paid via ${order.payment_method}</div>
    `;

    cartOffcanvas.hide();
    // Reset drawer/cart state for next visit, then show the success animation.
    cart.clear();
    renderCart();
    updateCartBadge();
    document.getElementById("order-form").reset();
    toggleTableNumberField();
    showCartStep();
    loadMenu(); // refresh stock levels

    playSuccessAnimation();
    successModal.show();
  } catch (err) {
    toast(err.message, "danger");
  } finally {
    btn.disabled = false;
    btn.textContent = "Pay & Place Order";
  }
}
document.getElementById("order-form").addEventListener("submit", placeOrder);

function playSuccessAnimation() {
  const wrap = document.querySelector(".checkmark-wrap");
  wrap.classList.remove("animate");
  void wrap.offsetWidth; // restart animation on repeat orders
  wrap.classList.add("animate");
}

// ------------------------------------------------------------------ Init ----
document.getElementById("search-input").addEventListener("input", debounce(loadMenu, 300));

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

(async function init() {
  await loadSiteSettings();
  await loadCategories();
  await loadMenu();
  toggleTableNumberField();
})();
