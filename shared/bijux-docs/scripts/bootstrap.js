(function () {
  "use strict";
  const shell = (window.bijuxShell = window.bijuxShell || {});
  if (shell.bootstrap) return;
  let lifetime;
  let closeDrawer;
  let readingIntent = false;
  const compact = window.matchMedia("(max-width: 76.2344em)");

  function upgradeControls() {
    for (const label of document.querySelectorAll('label[data-bijux-control-target], label.md-header__button[for="__search"]')) {
      const button = document.createElement("button");
      for (const attr of label.attributes) {
        if (!["role", "tabindex"].includes(attr.name)) button.setAttribute(attr.name, attr.value);
      }
      button.type = "button";
      if (label.matches('.md-header__button[for="__search"]')) {
        // Native Material headers share the owned search focus and dismissal contract.
        button.dataset.bijuxHeaderControl = "search-toggle";
        button.dataset.bijuxControlTarget = "__search";
        if (!button.hasAttribute("aria-label")) {
          button.setAttribute("aria-label", label.getAttribute("title") || document.querySelector(".md-search__input")?.getAttribute("aria-label") || "Search");
        }
      }
      button.replaceChildren(...label.childNodes);
      label.replaceWith(button);
    }
  }

  function bindDrawer(signal) {
    // Native Material headers retain their own drawer; this component requires shared ownership.
    if (!document.querySelector("header[data-bijux-drawer-target]")) return false;
    const toggle = document.getElementById("__drawer");
    const sidebar = document.querySelector(".md-sidebar--primary");
    const navigation = document.getElementById("bijux-navigation");
    const opener = document.querySelector('[data-bijux-header-control="drawer-toggle"]');
    if (!toggle || !sidebar || !navigation || !opener) throw new Error("Shared drawer initialization requires its native control, sidebar, tree and opener");
    let open = false;
    let background = [];
    const initialSidebarInert = sidebar.inert;
    const remember = (node, names) => names.map(name => [name, node.getAttribute(name)]);
    const sidebarAttributes = remember(sidebar, ["role", "aria-modal", "aria-label"]);
    const openerAttributes = remember(opener, ["aria-expanded", "aria-controls", "aria-haspopup"]);
    const restore = (node, attributes) => {
      for (const [name, value] of attributes) {
        if (value === null) node.removeAttribute(name);
        else node.setAttribute(name, value);
      }
    };
    signal.addEventListener("abort", () => {
      restoreBackground();
      sidebar.inert = initialSidebarInert;
      restore(sidebar, sidebarAttributes);
      restore(opener, openerAttributes);
      delete document.body.dataset.bijuxDrawerOpen;
      delete document.body.dataset.bijuxDrawerReady;
    }, { once: true });
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
    sync();
    return true;
  }

  function bindSearch(signal) {
    const toggle = document.getElementById("__search");
    const control = document.querySelector('[data-bijux-header-control="search-toggle"]');
    if (!toggle || !control) return;
    const dialog = document.querySelector("[data-md-component='search']");
    const input = document.querySelector("[data-md-component='search-query']");
    let closedInlineFocus = false;
    const visible = node => node && node.getClientRects().length && getComputedStyle(node).visibility !== "hidden";
    function returnFocus() {
      if (visible(control)) {
        closedInlineFocus = false;
        control.focus({ preventScroll: true });
      } else if (visible(input)) {
        // Native Material opens on debounced input focus. Returning the closed
        // inline invoker retains focus without establishing a new search intent.
        closedInlineFocus = true;
        input.focus({ preventScroll: true });
      }
    }
    function inlineIntent() {
      if (visible(control) || !visible(input) || toggle.checked) return;
      closedInlineFocus = false;
      toggle.checked = true;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
    }
    input?.addEventListener("focus", () => { if (!closedInlineFocus) inlineIntent(); }, { signal });
    input?.addEventListener("click", inlineIntent, { signal });
    input?.addEventListener("input", inlineIntent, { signal });
    input?.addEventListener("keydown", event => {
      if (!event.ctrlKey && !event.metaKey && !event.altKey &&
          (event.key.length === 1 || ["Backspace", "Delete", "Enter", "ArrowUp", "ArrowDown"].includes(event.key))) inlineIntent();
    }, { signal });
    input?.addEventListener("blur", () => { closedInlineFocus = false; }, { signal });
    let background = [];
    let open = false;
    function restoreBackground() {
      for (const [node, previous] of background) node.inert = previous;
      background = [];
    }
    function sync() {
      const wasOpen = open;
      open = toggle.checked;
      control.setAttribute("aria-expanded", String(open));
      control.setAttribute("aria-haspopup", "dialog");
      restoreBackground();
      if (!dialog) return;
      dialog.setAttribute("aria-label", "Search documentation");
      if (open) {
        dialog.setAttribute("aria-modal", "true");
        const nodes = new Set(document.querySelectorAll(".md-content, .md-sidebar, .md-footer"));
        for (let node = dialog; node.parentElement?.closest("header"); node = node.parentElement) {
          for (const sibling of node.parentElement.children) if (sibling !== node) nodes.add(sibling);
        }
        for (const node of nodes) { background.push([node, node.inert]); node.inert = true; }
      } else {
        dialog.removeAttribute("aria-modal");
        if (wasOpen && !readingIntent) returnFocus();
      }
    }
    control.addEventListener("click", () => {
      closedInlineFocus = false;
      closeDrawer?.(false);
      toggle.checked = !toggle.checked;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
      sync();
      if (toggle.checked) document.querySelector(".md-search__input")?.focus();
    }, { signal });
    toggle.addEventListener("change", sync, { signal });
    toggle.addEventListener("click", event => {
      if (!event.isTrusted && ((open && !toggle.checked) || (closedInlineFocus && toggle.checked))) event.preventDefault();
    }, { capture: true, signal });
    document.addEventListener("keydown", event => {
      if (!toggle.checked) return;
      if (event.key === "Tab" && dialog) {
        const nodes = [...dialog.querySelectorAll('input, button:not([disabled]), a[href], summary, [tabindex="0"]')]
          .filter(node => node.getClientRects().length && getComputedStyle(node).visibility !== "hidden");
        if (!nodes.length) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const index = nodes.indexOf(document.activeElement);
        const next = index < 0 ? (event.shiftKey ? nodes.length - 1 : 0) : (index + (event.shiftKey ? -1 : 1) + nodes.length) % nodes.length;
        nodes[next].focus();
        return;
      }
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      toggle.checked = false;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
    }, { capture: true, signal });
    dialog?.addEventListener("click", event => {
      const link = event.target.closest("a[href]");
      if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      readingIntent = true;
      toggle.checked = false;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
    }, { signal });
    let back = dialog?.querySelector('.md-search__icon[for="__search"]');
    if (back?.tagName === "LABEL") {
      const button = document.createElement("button");
      for (const attr of back.attributes) button.setAttribute(attr.name, attr.value);
      button.replaceChildren(...back.childNodes);
      back.replaceWith(button);
      back = button;
    }
    if (back) {
      back.type = "button";
      back.setAttribute("aria-label", "Close search");
      back.addEventListener("click", () => {
        toggle.checked = false;
        toggle.dispatchEvent(new Event("change", { bubbles: true }));
      }, { signal });
    }
    document.addEventListener("focusin", event => {
      if (open && dialog && !dialog.contains(event.target)) dialog.querySelector(".md-search__input")?.focus();
    }, { signal });
    signal.addEventListener("abort", restoreBackground, { once: true });
    sync();
  }

  function bindQueryInput(signal) {
    const input = document.querySelector("[data-md-component='search-query']");
    if (input) {
      // Material's admitted query observer reads keyup; paste, IME and voice emit input.
      const notify = () => {
        if (!signal.aborted) input.dispatchEvent(new KeyboardEvent("keyup", { key: "Unidentified", bubbles: true }));
      };
      input.addEventListener("input", event => { if (!event.isComposing) notify(); }, { signal });
      input.addEventListener("compositionend", notify, { signal });
      let resetJob;
      input.form?.addEventListener("reset", () => {
        // The reset default action runs after the event, including its microtasks.
        // Notify the native query observer in the next task with the cleared value.
        clearTimeout(resetJob);
        resetJob = setTimeout(notify, 0);
      }, { signal });
      signal.addEventListener("abort", () => clearTimeout(resetJob), { once: true });
    }
  }

  function runShellNavigationSync() {
    lifetime?.abort();
    delete document.body.dataset.bijuxDrawerReady;
    delete document.body.dataset.bijuxDrawerOpen;
    lifetime = new AbortController();
    closeDrawer = undefined;
    try {
      upgradeControls();
      const drawerBound = bindDrawer(lifetime.signal);
      bindSearch(lifetime.signal);
      bindQueryInput(lifetime.signal);
      shell.searchRecovery?.bind(lifetime.signal);
      shell.contentReflow?.bind(lifetime.signal);
      window.dispatchEvent(new Event("bijux:search-location"));
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
      // Material's generic JS class does not establish this owned lifecycle.
      if (drawerBound) document.body.dataset.bijuxDrawerReady = "true";
    } catch (error) {
      lifetime.abort();
      closeDrawer = undefined;
      throw error;
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
