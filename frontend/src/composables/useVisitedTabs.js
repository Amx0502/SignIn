import { computed, nextTick, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { isCurrentMenuVisible, menuState } from "../menu/menuStore.js";

const TABS_STORAGE_PREFIX = "signin_visited_tabs";
const MAX_TABS = 15;
const LEGACY_TAB_PATHS = {
  "/miaoying/tasks": "/miaoying/auto",
  "/miaoying/checkin": "/miaoying/auto",
  "/miaoying/checkin/auto": "/miaoying/auto",
};

export function useVisitedTabs({
  router,
  route,
  currentUser,
  isMobile,
  sidebarSections,
  resolveIcon,
}) {
  const tabs = ref([]);
  const tabsScrollRef = ref(null);
  const tabsOverflow = ref(false);
  let lastEvictNoticeAt = 0;
  let resizeObserver = null;

  function storageKey() {
    const userId = currentUser.value?.id;
    return userId != null
      ? `${TABS_STORAGE_PREFIX}:${userId}`
      : TABS_STORAGE_PREFIX;
  }

  function persistTabs() {
    try {
      localStorage.setItem(storageKey(), JSON.stringify(tabs.value));
    } catch {
      /* ignore storage errors */
    }
  }

  function loadTabs() {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey()) || "[]");
      if (!Array.isArray(parsed)) return void (tabs.value = []);
      const migrated = new Map();
      parsed
        .filter(
          (item) =>
            item &&
            typeof item.path === "string" &&
            typeof item.title === "string",
        )
        .forEach((item, index) => {
          const path = LEGACY_TAB_PATHS[item.path] || item.path;
          const resolved = router.resolve(path);
          const normalized = {
            path,
            title: resolved.meta?.title || item.title,
            parentTitle:
              resolved.meta?.parentTitle ||
              (typeof item.parentTitle === "string" ? item.parentTitle : ""),
            lastUsedAt:
              typeof item.lastUsedAt === "number"
                ? item.lastUsedAt
                : Date.now() - index * 1000,
          };
          const previous = migrated.get(path);
          if (!previous || normalized.lastUsedAt > previous.lastUsedAt)
            migrated.set(path, normalized);
        });
      tabs.value = [...migrated.values()]
        .sort((a, b) => a.lastUsedAt - b.lastUsedAt)
        .slice(-MAX_TABS);
      persistTabs();
    } catch {
      tabs.value = [];
    }
  }

  function clearTabs() {
    tabs.value = [];
    try {
      localStorage.removeItem(storageKey());
    } catch {
      /* ignore storage errors */
    }
  }

  function updateTabsOverflow() {
    const element = tabsScrollRef.value;
    tabsOverflow.value = element
      ? element.scrollWidth > element.clientWidth + 2
      : false;
  }

  function evictLeastUsed() {
    const victim = [...tabs.value].sort(
      (a, b) => (a.lastUsedAt || 0) - (b.lastUsedAt || 0),
    )[0];
    if (!victim) return;
    const index = tabs.value.findIndex((item) => item.path === victim.path);
    if (index === -1) return;
    tabs.value.splice(index, 1);
    const now = Date.now();
    if (!isMobile.value && now - lastEvictNoticeAt > 5000) {
      lastEvictNoticeAt = now;
      ElMessage.warning(
        `标签已达上限（${MAX_TABS}），已自动关闭最久未使用的标签`,
      );
    }
  }

  function addTab(target) {
    if (
      !target?.meta?.title ||
      tabs.value.some((item) => item.path === target.path)
    )
      return;
    tabs.value.push({
      path: target.path,
      title: target.meta.title,
      parentTitle: target.meta.parentTitle || "",
      lastUsedAt: Date.now(),
    });
    if (tabs.value.length > MAX_TABS) evictLeastUsed();
    persistTabs();
    nextTick(updateTabsOverflow);
  }

  function touchTab(path) {
    const item = tabs.value.find((tab) => tab.path === path);
    if (item) item.lastUsedAt = Date.now();
  }

  function activateTab(path) {
    touchTab(path);
    if (path !== route.path) router.push(path);
  }

  function closeTab(path) {
    const index = tabs.value.findIndex((item) => item.path === path);
    if (index === -1) return;
    const wasActive = path === route.path;
    tabs.value.splice(index, 1);
    persistTabs();
    if (wasActive)
      router.push(
        tabs.value[index]?.path || tabs.value[index - 1]?.path || "/dashboard",
      );
    nextTick(updateTabsOverflow);
  }

  function removeTabs(paths) {
    const removed = new Set(paths);
    if (!removed.size) return;
    const activeRemoved = removed.has(route.path);
    tabs.value = tabs.value.filter((item) => !removed.has(item.path));
    persistTabs();
    if (activeRemoved) router.push(tabs.value[0]?.path || "/dashboard");
    nextTick(updateTabsOverflow);
  }

  function handleTabMenuCommand(command) {
    const currentIndex = tabs.value.findIndex(
      (item) => item.path === route.path,
    );
    if (command === "close-left" && currentIndex > 0)
      removeTabs(tabs.value.slice(0, currentIndex).map((item) => item.path));
    if (
      command === "close-right" &&
      currentIndex !== -1 &&
      currentIndex < tabs.value.length - 1
    )
      removeTabs(tabs.value.slice(currentIndex + 1).map((item) => item.path));
    if (command === "close-others")
      removeTabs(
        tabs.value
          .filter((item) => item.path !== route.path)
          .map((item) => item.path),
      );
    if (command === "close-all")
      removeTabs(tabs.value.map((item) => item.path));
  }

  function pruneHiddenTabs() {
    if (!currentUser.value || currentUser.value.role === "admin") return;
    const visible = tabs.value.filter((item) => {
      const meta = router.resolve(item.path)?.meta || {};
      if (meta.requiresAdmin) return false;
      return (
        !meta.menuKey ||
        !menuState.loaded ||
        isCurrentMenuVisible(meta.menuKey, currentUser.value)
      );
    });
    if (visible.length !== tabs.value.length) {
      tabs.value = visible;
      persistTabs();
    }
  }

  function syncCurrentTab() {
    if (route.path === "/login" || !route.meta?.title) return;
    addTab(route);
    touchTab(route.path);
    pruneHiddenTabs();
    if (!tabs.value.some((item) => item.path === route.path)) addTab(route);
  }

  function onTabsWheel(event) {
    if (tabsScrollRef.value)
      tabsScrollRef.value.scrollLeft +=
        (event.deltaY || event.deltaX) > 0 ? 48 : -48;
  }

  function scrollTabs(direction) {
    const element = tabsScrollRef.value;
    if (!element) return;
    element.scrollBy({
      left: direction * Math.max(160, Math.round(element.clientWidth * 0.6)),
      behavior: "smooth",
    });
  }

  function scrollActiveTabIntoView() {
    requestAnimationFrame(() => {
      const element = tabsScrollRef.value;
      const active = element?.querySelector(".tab-item.active");
      if (!element || !active) return;
      const left = active.offsetLeft - 12;
      const right = active.offsetLeft + active.offsetWidth + 12;
      if (left < element.scrollLeft)
        element.scrollTo({ left, behavior: "smooth" });
      else if (right > element.scrollLeft + element.clientWidth)
        element.scrollTo({
          left: right - element.clientWidth,
          behavior: "smooth",
        });
    });
  }

  function iconNameForTab(tab) {
    for (const section of sidebarSections.value) {
      if (section.path === tab.path) return section.icon;
      const child = section.children?.find((item) => item.path === tab.path);
      if (child) return child.icon;
    }
    return "";
  }

  const tabIcon = (tab) => resolveIcon(iconNameForTab(tab) || "Grid");
  const currentTabIndex = computed(() =>
    tabs.value.findIndex((item) => item.path === route.path),
  );
  const canCloseLeft = computed(() => currentTabIndex.value > 0);
  const canCloseRight = computed(
    () =>
      currentTabIndex.value !== -1 &&
      currentTabIndex.value < tabs.value.length - 1,
  );
  const canCloseOthers = computed(() =>
    tabs.value.some((item) => item.path !== route.path),
  );
  const canCloseAll = computed(() => tabs.value.length > 0);

  function startTabsObserver() {
    resizeObserver?.disconnect();
    resizeObserver = new ResizeObserver(updateTabsOverflow);
    if (tabsScrollRef.value) resizeObserver.observe(tabsScrollRef.value);
    nextTick(updateTabsOverflow);
  }

  function stopTabsObserver() {
    resizeObserver?.disconnect();
    resizeObserver = null;
  }

  loadTabs();
  watch(
    () => route.path,
    () => {
      syncCurrentTab();
      nextTick(() => {
        scrollActiveTabIntoView();
        updateTabsOverflow();
      });
    },
    { immediate: true },
  );
  watch(() => menuState.version, pruneHiddenTabs);
  watch(currentUser, () => {
    if (currentUser.value) syncCurrentTab();
  });

  return {
    tabs,
    tabsScrollRef,
    tabsOverflow,
    clearTabs,
    activateTab,
    closeTab,
    handleTabMenuCommand,
    onTabsWheel,
    scrollTabs,
    updateTabsOverflow,
    tabIcon,
    canCloseLeft,
    canCloseRight,
    canCloseOthers,
    canCloseAll,
    loadTabs,
    syncCurrentTab,
    startTabsObserver,
    stopTabsObserver,
  };
}
