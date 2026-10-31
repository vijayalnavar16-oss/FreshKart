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
setTimeout(function () {
  document.querySelectorAll(".flash").forEach(function (el) { el.remove(); });
}, 5000);
