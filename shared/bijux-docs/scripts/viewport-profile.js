(function () {
  // Breakpoint contract:
  // - phone: < 48em
  // - normal: 48em to 76.2344em
  // - desktop: > 76.2344em and < 120em
  // - wide: >= 120em
  const PHONE_MAX_MEDIA = "(max-width: 47.9375em)";
  const NORMAL_MAX_MEDIA = "(max-width: 76.2344em)";
  const WIDE_MIN_MEDIA = "(min-width: 120em)";
  const VIEWPORT_PROFILES = Object.freeze({
    PHONE: "phone",
    NORMAL: "normal",
    DESKTOP: "desktop",
    WIDE: "wide",
  });
  const PHONE_MAX_EM = 47.9375;
  const NORMAL_MAX_EM = 76.2344;
  const WIDE_MIN_EM = 120;

  function mediaMatches(query) {
    return typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  }

  function toPixelsFromEm(em) {
    const rootFontSize = Number.parseFloat(window.getComputedStyle(document.documentElement).fontSize || "16");
    return em * (Number.isFinite(rootFontSize) ? rootFontSize : 16);
  }

  function currentViewportWidth() {
    if (window.visualViewport && typeof window.visualViewport.width === "number") {
      return window.visualViewport.width;
    }
    if (typeof window.innerWidth === "number") {
      return window.innerWidth;
    }
    return document.documentElement.clientWidth;
  }

  function resolveViewportProfile() {
    if (typeof window.matchMedia !== "function") {
      const width = currentViewportWidth();
      if (width <= toPixelsFromEm(PHONE_MAX_EM)) {
        return VIEWPORT_PROFILES.PHONE;
      }
      if (width >= toPixelsFromEm(WIDE_MIN_EM)) {
        return VIEWPORT_PROFILES.WIDE;
      }
      if (width <= toPixelsFromEm(NORMAL_MAX_EM)) {
        return VIEWPORT_PROFILES.NORMAL;
      }
      return VIEWPORT_PROFILES.DESKTOP;
    }

    if (mediaMatches(PHONE_MAX_MEDIA)) {
      return VIEWPORT_PROFILES.PHONE;
    }

    if (mediaMatches(WIDE_MIN_MEDIA)) {
      return VIEWPORT_PROFILES.WIDE;
    }

    if (mediaMatches(NORMAL_MAX_MEDIA)) {
      return VIEWPORT_PROFILES.NORMAL;
    }

    return VIEWPORT_PROFILES.DESKTOP;
  }

  function applyViewportProfile() {
    const profile = resolveViewportProfile();
    // Keep both targets in sync because CSS and JS hooks read from each in different contexts.
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
      // Coalesce rapid resize/orientation events into one profile recompute per frame.
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
    media: {
      phoneMax: PHONE_MAX_MEDIA,
      normalMax: NORMAL_MAX_MEDIA,
      wideMin: WIDE_MIN_MEDIA,
    },
    describe: () => ({
      profile: resolveViewportProfile(),
      matches: {
        phone: mediaMatches(PHONE_MAX_MEDIA),
        normal: mediaMatches(NORMAL_MAX_MEDIA),
        wide: mediaMatches(WIDE_MIN_MEDIA),
      },
    }),
  };

  document$.subscribe(init);
})();
