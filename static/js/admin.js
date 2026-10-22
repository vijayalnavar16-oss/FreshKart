
document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.getElementById("admin-menu-toggle");
  const sidebar = document.querySelector(".admin-sidebar");

  menuButton?.addEventListener("click", () => {
    sidebar?.classList.toggle("open");
  });

  document.querySelectorAll(".admin-nav-link").forEach(link => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".admin-nav-link")
        .forEach(item => item.classList.remove("active"));

      link.classList.add("active");
      sidebar?.classList.remove("open");
    });
  });

  const dateElement = document.getElementById("admin-date");

  if (dateElement) {
    dateElement.textContent = new Intl.DateTimeFormat("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    }).format(new Date());
  }

  document.getElementById("refresh-admin")?.addEventListener("click", () => {
    window.location.reload();
  });
});
