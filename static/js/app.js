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


(function () {
  document.querySelectorAll("[data-phone-editor]").forEach(function (form) {
    var input = form.querySelector('input[name="phone_number"]');
    var button = form.querySelector(".user-edit-toggle");
    if (!input || !button) return;
    button.addEventListener("click", function () {
      if (input.readOnly) {
        input.readOnly = false;
        button.textContent = "Done";
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      } else {
        input.blur();
      }
    });
    input.addEventListener("blur", function () {
      input.readOnly = true;
      button.textContent = "✎ Edit";
      if (input.value.trim() !== input.dataset.original) {
        if (input.checkValidity()) form.requestSubmit();
        else input.reportValidity();
      }
    });
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        input.blur();
      }
      if (event.key === "Escape") {
        input.value = input.dataset.original || "";
        input.blur();
      }
    });
  });
})();

document.addEventListener("click", function (event) {
  var edit = event.target.closest("[data-account-editor] .user-edit-toggle");
  var cancel = event.target.closest("[data-account-editor] .user-edit-cancel");
  if (edit) {
    var form = edit.closest("[data-account-editor]");
    form.classList.add("is-editing");
    form.querySelectorAll("input[readonly]").forEach(function (field) { field.readOnly = false; });
    var password = form.querySelector('input[name="new_password"]');
    if (password) password.disabled = false;
    edit.hidden = true;
    form.querySelector(".user-edit-done").hidden = false;
    form.querySelector(".user-edit-cancel").hidden = false;
    var first = form.querySelector('input[name="username"]');
    if (first) first.focus();
  }
  if (cancel) {
    var form = cancel.closest("[data-account-editor]");
    form.reset();
    form.classList.remove("is-editing");
    form.querySelectorAll("input[readonly]").forEach(function (field) { field.readOnly = true; });
    var password = form.querySelector('input[name="new_password"]');
    if (password) { password.value = ""; password.disabled = true; }
    form.querySelector(".user-edit-toggle").hidden = false;
    form.querySelector(".user-edit-done").hidden = true;
    cancel.hidden = true;
  }
});
document.addEventListener("submit", function (event) {
  var form = event.target.closest("[data-account-editor]");
  if (!form) return;
  var button = form.querySelector(".user-edit-done");
  if (button) { button.disabled = true; button.textContent = "Updating…"; }
});


/* Account cards stay compact; tap a row to reveal its profile and edit controls. */
document.addEventListener("click", function (event) {
  var summary = event.target.closest("[data-account-card] .user-account-summary");
  if (!summary) return;
  var card = summary.closest("[data-account-card]");
  var details = card.querySelector(".user-account-details");
  var opening = summary.getAttribute("aria-expanded") !== "true";
  summary.setAttribute("aria-expanded", String(opening));
  details.hidden = !opening;
  card.classList.toggle("is-expanded", opening);
});
