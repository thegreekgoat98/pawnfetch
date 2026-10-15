(() => {
  const root = document.documentElement;

  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-theme-toggle]")) return;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try {
      localStorage.setItem("pf-theme", next);
    } catch {}
  });

  const RECENT_KEY = "pf-recent";
  const NAME_RE = /^[A-Za-z0-9_-]{3,25}$/;
  const MAX_RECENT = 6;

  const readRecent = () => {
    try {
      const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(raw) ? raw.filter((n) => typeof n === "string" && NAME_RE.test(n)) : [];
    } catch {
      return [];
    }
  };

  const remember = (raw) => {
    const name = raw.trim().toLowerCase();
    if (!NAME_RE.test(name)) return;
    const next = [name, ...readRecent().filter((n) => n !== name)].slice(0, MAX_RECENT);
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {}
  };

  const player = document.querySelector("[data-player]");
  if (player) remember(player.dataset.player);

  const box = document.getElementById("recent");
  if (box) {
    const names = readRecent();
    if (names.length) {
      const chips = box.querySelector("[data-chips]");
      for (const name of names) {
        const link = document.createElement("a");
        link.href = "/player/" + encodeURIComponent(name);
        link.textContent = name;
        link.className =
          "rounded-full border-2 border-line bg-surface px-3 py-1 text-sm font-semibold hover:border-accent";
        chips.append(link);
      }
      box.hidden = false;
    }
  }
})();
