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

  // Share buttons (see the share_bar macro). The image is the same PNG the server draws for
  // link previews, so the copied/downloaded picture matches what Discord or X would show.
  const revealNativeShare = (scope) => {
    if (!navigator.share) return;
    for (const button of scope.querySelectorAll("[data-share-native]")) button.hidden = false;
  };
  revealNativeShare(document);
  document.addEventListener("htmx:load", (event) => revealNativeShare(event.detail.elt));

  const fetchImage = async (url) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error("image " + response.status);
    return response.blob();
  };

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-share-copy-image], [data-share-copy-link], [data-share-native]");
    const bar = button && button.closest("[data-share]");
    if (!bar) return;
    const status = bar.querySelector("[data-share-status]");
    const say = (text) => {
      status.textContent = text;
    };
    const image = bar.dataset.image;
    try {
      if (button.matches("[data-share-copy-link]")) {
        await navigator.clipboard.writeText(location.href);
        say("Link copied.");
      } else if (button.matches("[data-share-copy-image]")) {
        if (!window.ClipboardItem || !navigator.clipboard?.write) throw new Error("unsupported");
        // Passing the promise keeps Safari happy: the copy still counts as part of the click.
        await navigator.clipboard.write([new ClipboardItem({ "image/png": fetchImage(image) })]);
        say("Image copied. Paste it anywhere.");
      } else {
        const blob = await fetchImage(image);
        const file = new File([blob], image.split("/").pop(), { type: "image/png" });
        const data = { title: document.title, url: location.href };
        await navigator.share(navigator.canShare?.({ files: [file] }) ? { ...data, files: [file] } : data);
      }
    } catch (error) {
      if (error.name === "AbortError") return; // the share sheet was closed
      say(button.matches("[data-share-copy-image]") ? "Can't copy images here. Use Download instead." : "That didn't work. Try again.");
    }
  });
})();
