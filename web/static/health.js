async function pollHealth() {
  const badge = document.getElementById("connBadge");
  if (!badge) return;

  try {
    const r = await fetch("/health", { cache: "no-store" });
    if (!r.ok) throw new Error("bad status");
    badge.textContent = "Connected";
    badge.classList.remove("badge-bad");
    badge.classList.add("badge-ok");
  } catch (e) {
    badge.textContent = "Disconnected";
    badge.classList.remove("badge-ok");
    badge.classList.add("badge-bad");
  }
}

pollHealth();
setInterval(pollHealth, 3000);
