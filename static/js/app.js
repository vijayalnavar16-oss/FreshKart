const productGrid = document.querySelector("#product-grid");
const productStatus = document.querySelector("#product-status");
const noResults = document.querySelector("#no-results");
const searchInput = document.querySelector("#search-input");
const clearSearch = document.querySelector("#clear-search");
const categoryList = document.querySelector("#category-list");
const sortSelect = document.querySelector("#sort-products");
const inStockOnly = document.querySelector("#in-stock-only");
const cartCount = document.querySelector("#cart-count");
const cartDrawer = document.querySelector("#cart-drawer");
const cartBackdrop = document.querySelector("#cart-backdrop");
const cartItems = document.querySelector("#cart-items");
const cartEmpty = document.querySelector("#cart-empty");
const cartSummary = document.querySelector("#cart-summary");
const toast = document.querySelector("#toast");

let products = [];
let activeCategory = "all";
let toastTimer;
let cart = readCart();

function readCart() {
  try {
    const saved = JSON.parse(localStorage.getItem("freshkart-demo-cart") || "{}");
    return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
  } catch {
    return {};
  }
}

function formatRupees(paise) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(paise / 100);
}

function filteredProducts() {
  const query = searchInput.value.trim().toLocaleLowerCase("en-IN");
  let result = products.filter((product) => {
    const matchesSearch = product.name.toLocaleLowerCase("en-IN").includes(query);
    const matchesCategory = activeCategory === "all" || product.category.toLocaleLowerCase("en-IN") === activeCategory.toLocaleLowerCase("en-IN");
    const matchesStock = !inStockOnly.checked || product.stock_quantity > 0;
    return matchesSearch && matchesCategory && matchesStock;
  });

  if (sortSelect.value === "price-low") result.sort((a, b) => a.price_paise - b.price_paise);
  if (sortSelect.value === "price-high") result.sort((a, b) => b.price_paise - a.price_paise);
  if (sortSelect.value === "recent") result.sort((a, b) => b.id - a.id);
  return result;
}

function quantityControl(productId, quantity) {
  return `<div class="quantity-control" aria-label="Quantity ${quantity}">
    <button type="button" data-action="decrease" data-id="${productId}" aria-label="Remove one">−</button>
    <span>${quantity}</span>
    <button type="button" data-action="increase" data-id="${productId}" aria-label="Add one">+</button>
  </div>`;
}

function renderProducts() {
  const visibleProducts = filteredProducts();
  productGrid.replaceChildren();
  const catalogIsEmpty = products.length === 0;
  productStatus.textContent = catalogIsEmpty ? "" : `${visibleProducts.length} available ${visibleProducts.length === 1 ? "item" : "items"}`;
  noResults.hidden = visibleProducts.length > 0;
  productGrid.hidden = visibleProducts.length === 0;
  document.querySelector("#no-results h3").textContent = catalogIsEmpty
    ? "No items available right now. Please check back later."
    : "No items match your search.";
  document.querySelector("#no-results-help").hidden = catalogIsEmpty;
  document.querySelector("#reset-filters").hidden = catalogIsEmpty;

  for (const product of visibleProducts) {
    const card = document.createElement("article");
    card.className = "product-card";
    const quantity = Number(cart[product.id] || 0);
    const photo = document.createElement("div");
    photo.className = "product-photo";
    if (product.image_url) {
      const image = document.createElement("img");
      image.src = product.image_url;
      image.alt = product.name;
      image.loading = "lazy";
      image.addEventListener("error", () => photo.classList.add("image-failed"), { once: true });
      photo.append(image);
    } else {
      photo.classList.add("image-failed");
    }

    const category = document.createElement("p");
    category.className = "product-category";
    category.textContent = product.category;
    const name = document.createElement("h3");
    name.className = "product-name";
    name.textContent = product.name;
    const unit = document.createElement("p");
    unit.className = "product-unit";
    unit.textContent = `${product.unit} · In stock`;

    const bottom = document.createElement("div");
    bottom.className = "product-card-bottom";
    const price = document.createElement("div");
    price.className = "product-price";
    price.textContent = formatRupees(product.price_paise);
    bottom.append(price);
    if (quantity) {
      bottom.insertAdjacentHTML("beforeend", quantityControl(product.id, quantity));
    } else {
      const addButton = document.createElement("button");
      addButton.className = "add-button";
      addButton.type = "button";
      addButton.dataset.action = "add";
      addButton.dataset.id = product.id;
      addButton.textContent = "ADD +";
      bottom.append(addButton);
    }
    card.append(photo, category, name, unit, bottom);
    productGrid.append(card);
  }
}

function reconcileCart() {
  const availableProducts = new Map(products.map((product) => [String(product.id), product]));
  for (const id of Object.keys(cart)) {
    const quantity = Number(cart[id]);
    const product = availableProducts.get(id);
    if (!product || !Number.isInteger(quantity) || quantity < 1) {
      delete cart[id];
    } else {
      cart[id] = Math.min(quantity, product.stock_quantity);
      if (cart[id] < 1) delete cart[id];
    }
  }
  localStorage.setItem("freshkart-demo-cart", JSON.stringify(cart));
}

function persistCart() {
  localStorage.setItem("freshkart-demo-cart", JSON.stringify(cart));
  renderProducts();
  renderCart();
}

function changeQuantity(id, delta) {
  const product = products.find((item) => item.id === id);
  if (!product) return;
  const next = Number(cart[id] || 0) + delta;
  if (next > product.stock_quantity) {
    showToast("That is all we currently have in stock.");
    return;
  }
  if (next <= 0) delete cart[id];
  else cart[id] = next;
  persistCart();
}

function renderCart() {
  const totalCount = Object.values(cart).reduce((sum, quantity) => sum + Number(quantity || 0), 0);
  cartCount.textContent = totalCount;
  cartCount.setAttribute("aria-label", `${totalCount} items in basket`);
  cartItems.replaceChildren();
  let subtotal = 0;

  for (const [id, quantity] of Object.entries(cart)) {
    const product = products.find((item) => item.id === Number(id));
    if (!product || quantity <= 0) continue;
    subtotal += product.price_paise * quantity;
    const line = document.createElement("div");
    line.className = "cart-line";
    const image = document.createElement("img");
    image.alt = "";
    image.loading = "lazy";
    if (product.image_url) {
      image.src = product.image_url;
      image.addEventListener("error", () => { image.hidden = true; }, { once: true });
    } else {
      image.hidden = true;
    }
    const details = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = product.name;
    const description = document.createElement("p");
    description.textContent = `${product.unit} · ${formatRupees(product.price_paise)}`;
    details.append(name, description);
    details.insertAdjacentHTML("beforeend", quantityControl(product.id, quantity));
    const total = document.createElement("div");
    total.className = "cart-line-total";
    total.textContent = formatRupees(product.price_paise * quantity);
    line.append(image, details, total);
    cartItems.append(line);
  }

  const empty = totalCount === 0;
  cartEmpty.hidden = !empty;
  cartItems.hidden = empty;
  cartSummary.hidden = empty;
  document.querySelector("#cart-subtotal").textContent = formatRupees(subtotal);
}

function openCart() {
  cartBackdrop.hidden = false;
  cartDrawer.classList.add("open");
  cartDrawer.setAttribute("aria-hidden", "false");
  document.querySelector("#close-cart").focus();
  document.body.style.overflow = "hidden";
}

function closeCart() {
  cartDrawer.classList.remove("open");
  cartDrawer.setAttribute("aria-hidden", "true");
  cartBackdrop.hidden = true;
  document.body.style.overflow = "";
  document.querySelector("#open-cart").focus();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

async function loadProducts() {
  try {
    const response = await fetch("/api/products");
    if (!response.ok) throw new Error("Catalog request failed");
    const data = await response.json();
    products = data.products;
    reconcileCart();
    renderProducts();
    renderCart();
  } catch {
    productStatus.textContent = "We could not load the catalog. Check your connection and refresh.";
    productGrid.hidden = true;
  }
}

productGrid.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === "add") {
    changeQuantity(id, 1);
    const product = products.find((item) => item.id === id);
    if (product) showToast(`${product.name} added to your basket`);
  } else {
    changeQuantity(id, button.dataset.action === "increase" ? 1 : -1);
  }
});

cartItems.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  changeQuantity(Number(button.dataset.id), button.dataset.action === "increase" ? 1 : -1);
});

searchInput.addEventListener("input", () => {
  clearSearch.hidden = searchInput.value.length === 0;
  renderProducts();
});
document.querySelector("#search-form").addEventListener("submit", (event) => event.preventDefault());
clearSearch.addEventListener("click", () => { searchInput.value = ""; clearSearch.hidden = true; searchInput.focus(); renderProducts(); });
categoryList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-category]");
  if (!button) return;
  activeCategory = button.dataset.category;
  categoryList.querySelectorAll(".category-item").forEach((item) => item.classList.toggle("active", item === button));
  renderProducts();
  document.querySelector("#shop").scrollIntoView({ behavior: "smooth", block: "start" });
});
sortSelect.addEventListener("change", renderProducts);
inStockOnly.addEventListener("change", renderProducts);
document.querySelector("#reset-filters").addEventListener("click", () => {
  activeCategory = "all";
  searchInput.value = "";
  clearSearch.hidden = true;
  inStockOnly.checked = false;
  categoryList.querySelectorAll(".category-item").forEach((item, index) => item.classList.toggle("active", index === 0));
  renderProducts();
});
document.querySelector("#open-cart").addEventListener("click", openCart);
document.querySelector("#close-cart").addEventListener("click", closeCart);
document.querySelector("#continue-shopping").addEventListener("click", closeCart);
cartBackdrop.addEventListener("click", closeCart);
document.querySelector("#demo-checkout").addEventListener("click", () => showToast("Checkout arrives in a later FreshKart phase."));
document.querySelector(".account-button").addEventListener("click", () => showToast("Customer accounts arrive in a later FreshKart phase."));
document.querySelector(".location-button").addEventListener("click", () => showToast("Location selection arrives in a later FreshKart phase."));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && cartDrawer.classList.contains("open")) closeCart();
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    searchInput.focus();
  }
});

renderCart();
loadProducts();