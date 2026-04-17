(function () {
  // phone < 48em, normal 48em–76.2344em, desktop > 76.2344em, wide >= 120em
  const PHONE_MAX_MEDIA = "(max-width: 47.9375em)";
  const NORMAL_MAX_MEDIA = "(max-width: 76.2344em)";
  const WIDE_MIN_MEDIA = "(min-width: 120em)";

  function resolveViewportProfile() {
    if (window.matchMedia(PHONE_MAX_MEDIA).matches) {
      return "phone";
    }

    if (window.matchMedia(WIDE_MIN_MEDIA).matches) {
      return "wide";
    }

    if (window.matchMedia(NORMAL_MAX_MEDIA).matches) {
      return "normal";
    }

    return "desktop";
  }

  function applyViewportProfile() {
    const profile = resolveViewportProfile();
    document.documentElement.setAttribute("data-bijux-viewport", profile);
    document.body?.setAttribute("data-bijux-viewport", profile);
    return profile;
  }

  function bindViewportUpdates() {
    if (window.__bijuxViewportBound === true) {
      return;
    }

    window.__bijuxViewportBound = true;

    let rafId = 0;
    const onResize = () => {
      if (rafId !== 0) {
        return;
      }
      rafId = window.requestAnimationFrame(() => {
        rafId = 0;
        applyViewportProfile();
      });
    };

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("orientationchange", onResize, { passive: true });
  }

  function init() {
    applyViewportProfile();
    bindViewportUpdates();
  }

  window.bijuxViewportProfile = {
    current: resolveViewportProfile,
    apply: applyViewportProfile,
  };

  document$.subscribe(init);
})();
