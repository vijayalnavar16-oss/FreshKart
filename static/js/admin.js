
document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.getElementById("admin-menu-toggle");
  const sidebar = document.querySelector(".admin-sidebar");

  // Mobile sidebar toggle
  menuButton?.addEventListener("click", () => {
    sidebar?.classList.toggle("open");
  });

  // Navigation active state
  document.querySelectorAll(".admin-nav-link").forEach(link => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".admin-nav-link").forEach(item => {
        item.classList.remove("active");
      });

      link.classList.add("active");
      sidebar?.classList.remove("open");
    });
  });

  // Display current date
  const dateElement = document.getElementById("admin-date");

  if (dateElement) {
    dateElement.textContent = new Intl.DateTimeFormat("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    }).format(new Date());
  }

  // Format numbers using Indian numbering
  function formatNumber(value) {
    return new Intl.NumberFormat("en-IN").format(Number(value) || 0);
  }

  // Safely update an existing HTML element
  function updateElement(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value;
    }
  }

  // Load real dashboard statistics
  async function loadDashboard() {
    const refreshButton = document.getElementById("refresh-admin");

    if (refreshButton) {
      refreshButton.disabled = true;
    }

    try {
      const response = await fetch("/api/admin/dashboard", {
        method: "GET",
        credentials: "same-origin",
        headers: {
          Accept: "application/json"
        }
      });

      if (response.status === 401) {
        console.warn("Admin login is required.");
        return;
      }

      if (!response.ok) {
        throw new Error(`Dashboard request failed: ${response.status}`);
      }

      const data = await response.json();

      if (!data.ok || !data.products) {
        throw new Error("Invalid dashboard response.");
      }

      const products = data.products;

      updateElement("stat-products", formatNumber(products.total));
      updateElement(
        "stat-available-products",
        formatNumber(products.available)
      );
      updateElement(
        "stat-out-of-stock",
        formatNumber(products.out_of_stock)
      );
      updateElement(
        "stat-total-stock",
        formatNumber(products.total_stock)
      );

      updateElement("admin-total-products", formatNumber(products.total));
      updateElement(
        "admin-available-products",
        formatNumber(products.available)
      );
      updateElement(
        "admin-out-of-stock",
        formatNumber(products.out_of_stock)
      );

      console.info("Dashboard statistics loaded.");
    } catch (error) {
      console.error("Could not load dashboard statistics:", error);
    } finally {
      if (refreshButton) {
        refreshButton.disabled = false;
      }
    }
  }

  // Load products into the admin product section
  async function loadProducts() {
    const container = document.getElementById("admin-product-list");

    if (!container) {
      return;
    }

    try {
      const response = await fetch("/api/admin/products", {
        method: "GET",
        credentials: "same-origin",
        headers: {
          Accept: "application/json"
        }
      });

      if (response.status === 401) {
        console.warn("Admin login is required to load products.");
        return;
      }

      if (!response.ok) {
        throw new Error(`Product request failed: ${response.status}`);
      }

      const data = await response.json();
      const products = Array.isArray(data.products) ? data.products : [];

      if (products.length === 0) {
        container.textContent = "No products found.";
        return;
      }

      const fragment = document.createDocumentFragment();

      products.forEach(product => {
        const item = document.createElement("div");
        item.className = "admin-product-item";

        const name = document.createElement("h4");
        name.textContent = product.name || "Unnamed product";

        const category = document.createElement("p");
        category.textContent = product.category || "Uncategorized";

        const price = document.createElement("p");
        price.textContent =
          `Price: ₹${(Number(product.price_paise || 0) / 100).toFixed(2)}` +
          ` / ${product.unit || "unit"}`;

        const stock = document.createElement("p");
        stock.textContent =
          `Stock: ${formatNumber(product.stock_quantity)}`;

        const status = document.createElement("span");
        const available =
          Number(product.is_available) === 1 &&
          Number(product.stock_quantity) > 0;

        status.className = available
          ? "admin-product-status available"
          : "admin-product-status unavailable";

        status.textContent = available
          ? "Available"
          : "Unavailable / Out of stock";

        item.append(name, category, price, stock, status);
        fragment.appendChild(item);
      });

      container.replaceChildren(fragment);
    } catch (error) {
      console.error("Could not load products:", error);
      container.textContent = "Unable to load products. Please try again.";
    }
  }

  // Refresh button updates data without reloading the entire page
  document.getElementById("refresh-admin")?.addEventListener("click", () => {
    loadDashboard();
    loadProducts();
  });

  // Initial load
  loadDashboard();
  loadProducts();
});
