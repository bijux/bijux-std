(function () {
  "use strict";
  const shell = (window.bijuxShell = window.bijuxShell || {});
  if (shell.bootstrap) return;
  let lifetime;
  let closeDrawer;
  let readingIntent = false;
  const compact = window.matchMedia("(max-width: 76.2344em)");

  function upgradeControls() {
    for (const label of document.querySelectorAll("label[data-bijux-control-target]")) {
      const button = document.createElement("button");
      for (const attr of label.attributes) {
        if (!["role", "tabindex"].includes(attr.name)) button.setAttribute(attr.name, attr.value);
      }
      button.type = "button";
      button.replaceChildren(...label.childNodes);
      label.replaceWith(button);
    }
  }

  function bindDrawer(signal) {
    const toggle = document.getElementById("__drawer");
    const sidebar = document.querySelector(".md-sidebar--primary");
    const navigation = document.getElementById("bijux-navigation");
    const opener = document.querySelector('[data-bijux-header-control="drawer-toggle"]');
    if (!toggle || !sidebar || !navigation || !opener) return;
    let open = false;
    let background = [];
    const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== "hidden";
    const focusable = () => [...navigation.querySelectorAll('a[href], button:not([disabled]), summary, [tabindex="0"]')].filter(visible);

    function restoreBackground() {
      for (const [node, previous] of background) node.inert = previous;
      background = [];
    }

    function sync(restore = false) {
      const next = compact.matches && toggle.checked;
      const changed = next !== open;
      open = next;
      opener.setAttribute("aria-expanded", String(open));
      opener.setAttribute("aria-controls", "bijux-navigation");
      opener.setAttribute("aria-haspopup", "dialog");
      sidebar.inert = compact.matches && !open;
      document.body.dataset.bijuxDrawerOpen = String(open);
      restoreBackground();
      if (open) {
        sidebar.setAttribute("role", "dialog");
        sidebar.setAttribute("aria-modal", "true");
        sidebar.setAttribute("aria-label", "Site navigation");
        for (const node of document.querySelectorAll(".md-content, .md-sidebar--secondary, .md-footer")) {
          background.push([node, node.inert]);
          node.inert = true;
        }
        if (changed) (focusable()[0] || navigation).focus({ preventScroll: true });
      } else {
        sidebar.removeAttribute("role");
        sidebar.removeAttribute("aria-modal");
        sidebar.removeAttribute("aria-label");
        if (restore && compact.matches) opener.focus({ preventScroll: true });
      }
    }

    function close(restore = true) {
      toggle.checked = false;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
      sync(restore);
    }
    closeDrawer = close;
    // Material closes toggles on a delayed location emission. A later explicit
    // drawer opening owns its state; an older synthetic click cannot revoke it.
    toggle.addEventListener("click", event => {
      if (!event.isTrusted && open && !toggle.checked) event.preventDefault();
    }, { capture: true, signal });
    toggle.addEventListener("change", () => sync(open && !toggle.checked && !readingIntent), { signal });
    compact.addEventListener("change", () => close(false), { signal });
    for (const control of document.querySelectorAll('[data-bijux-control-target="__drawer"]')) {
      control.addEventListener("click", () => {
        if (control.hasAttribute("data-bijux-control-close")) close();
        else {
          toggle.checked = !toggle.checked;
          toggle.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }, { signal });
    }
    document.addEventListener("keydown", event => {
      if (!open) return;
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      } else if (event.key === "Tab") {
        const nodes = focusable();
        if (!nodes.length) return;
        // Traverse the complete dialog explicitly, including Safari's non-default link stops.
        event.preventDefault();
        const index = nodes.indexOf(document.activeElement);
        const next = index < 0 ? (event.shiftKey ? nodes.length - 1 : 0) : (index + (event.shiftKey ? -1 : 1) + nodes.length) % nodes.length;
        nodes[next].focus();
      }
    }, { signal });
    document.addEventListener("focusin", event => {
      if (open && !navigation.contains(event.target)) (focusable()[0] || navigation).focus();
    }, { signal });
    navigation.addEventListener("click", event => {
      const link = event.target.closest("a[href]");
      if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      readingIntent = true;
      close(false);
    }, { signal });
    signal.addEventListener("abort", () => {
      restoreBackground(); sidebar.inert = false;
      document.body.dataset.bijuxDrawerOpen = "false";
    }, { once: true });
    sync();
  }

  function bindSearch(signal) {
    const toggle = document.getElementById("__search");
    const control = document.querySelector('[data-bijux-header-control="search-toggle"]');
    if (!toggle || !control) return;
    function sync() { control.setAttribute("aria-expanded", String(toggle.checked)); }
    control.addEventListener("click", () => {
      closeDrawer?.(false);
      toggle.checked = !toggle.checked;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
      sync();
      if (toggle.checked) document.querySelector(".md-search__input")?.focus();
    }, { signal });
    toggle.addEventListener("change", sync, { signal });
    sync();
  }

  function runShellNavigationSync() {
    lifetime?.abort();
    lifetime = new AbortController();
    closeDrawer = undefined;
    upgradeControls();
    bindDrawer(lifetime.signal);
    bindSearch(lifetime.signal);
    shell.detailTabs?.runDetailTabsSync?.();
    shell.navReveal?.runDesktopNavigationSync?.();
    if (readingIntent) {
      readingIntent = false;
      const heading = document.querySelector(".md-content h1");
      if (heading) {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      }
    }
  }

  function ensureBound() {
    if (shell.bootstrap.bound) return;
    shell.bootstrap.bound = true;
    if (window.document$ && typeof window.document$.subscribe === "function") {
      window.document$.subscribe(runShellNavigationSync);
    } else if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", runShellNavigationSync, { once: true });
    } else runShellNavigationSync();
    window.addEventListener("pagehide", () => lifetime?.abort());
    window.addEventListener("pageshow", event => { if (event.persisted) runShellNavigationSync(); });
  }

  shell.bootstrap = { runShellNavigationSync, ensureBound, bound: false };
  ensureBound();
})();
