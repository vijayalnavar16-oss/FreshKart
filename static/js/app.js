// Ask before risky actions (forms with data-confirm), prevent double submits,
// and hide flash messages after 5 seconds.
document.addEventListener("submit", function (event) {
  var form = event.target;
  if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
    return;
  }
  var button = form.querySelector("button[type=submit], button:not([type])");
  if (button) { button.disabled = true; }
});

(function () {
  var toggle = document.getElementById("admin-menu-toggle");
  var panel = document.getElementById("admin-menu-panel");
  var backdrop = document.getElementById("admin-menu-backdrop");
  var close = document.getElementById("admin-menu-close");
  if (!toggle || !panel || !backdrop) return;
  function setOpen(open) {
    panel.classList.toggle("is-open", open);
    backdrop.classList.toggle("is-visible", open);
    panel.setAttribute("aria-hidden", String(!open));
    toggle.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("menu-open", open);
  }
  toggle.addEventListener("click", function () { setOpen(!panel.classList.contains("is-open")); });
  if (close) close.addEventListener("click", function () { setOpen(false); });
  backdrop.addEventListener("click", function () { setOpen(false); });
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") setOpen(false); });
  panel.querySelectorAll("a").forEach(function (link) { link.addEventListener("click", function () { setOpen(false); }); });
})();

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".flash").forEach(function (el) {
    window.setTimeout(function () {
      el.classList.add("flash-hide");
      window.setTimeout(function () { el.remove(); }, 250);
    }, 4500);
  });
});
