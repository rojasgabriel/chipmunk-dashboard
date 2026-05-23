(function () {
  const STORAGE_KEY = "chipmunk-dashboard.sidebar-collapsed";
  let initialized = false;

  function getRoot() {
    return document.querySelector(".dashboard-root");
  }

  function getButton() {
    return document.querySelector("#sidebar-toggle-button");
  }

  function getSidebar() {
    return document.querySelector(".dashboard-sidebar");
  }

  function setCollapsed(root, collapsed) {
    root.classList.toggle("sidebar-collapsed", collapsed);
    window.localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    const sidebar = getSidebar();
    if (sidebar) {
      sidebar.hidden = collapsed;
    }
    const button = getButton();
    if (button) {
      button.setAttribute("aria-pressed", collapsed ? "true" : "false");
    }
  }

  function toggleSidebar() {
    const root = getRoot();
    if (!root) {
      return;
    }
    setCollapsed(root, !root.classList.contains("sidebar-collapsed"));
  }

  function init() {
    if (initialized) {
      return;
    }

    const root = getRoot();
    const button = getButton();
    if (!root || !button) {
      return;
    }
    initialized = true;

    const collapsed = window.localStorage.getItem(STORAGE_KEY) === "1";
    setCollapsed(root, collapsed);

    button.addEventListener("click", toggleSidebar);
  }

  function initWhenDashLayoutExists() {
    init();
    if (initialized) {
      return;
    }

    const observer = new MutationObserver(() => {
      init();
      if (initialized) {
        observer.disconnect();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initWhenDashLayoutExists, {
      once: true,
    });
    return;
  }

  initWhenDashLayoutExists();
})();
