import { computed, ref, watch } from "vue";
import {
  MOBILE_PLATFORM_DEFINITIONS,
  buildMobileExtraItems,
  buildMobilePrimaryItems,
  detectMobilePlatform,
  resolveMobilePlatformKey,
} from "../utils/mobileNavigation.js";

const MOBILE_PLATFORM_STORAGE_KEY = "signin_mobile_platform";

export function useMobileNavigation({
  router,
  route,
  sidebarSections,
  currentUser,
  platformImages,
  resolveIcon,
  onLogout,
}) {
  const mobileMoreVisible = ref(false);
  const mobileKeyboardOpen = ref(false);
  let historyActive = false;
  let pendingPath = "";
  let pendingLogout = false;

  const businessSections = computed(() =>
    sidebarSections.value.filter(
      (section) => MOBILE_PLATFORM_DEFINITIONS[section.key],
    ),
  );
  const platformKey = computed(() =>
    resolveMobilePlatformKey(
      sidebarSections.value,
      route.path,
      localStorage.getItem(MOBILE_PLATFORM_STORAGE_KEY) || "",
    ),
  );
  const platform = computed(() => {
    const key = platformKey.value;
    return key
      ? { key, ...MOBILE_PLATFORM_DEFINITIONS[key], image: platformImages[key] }
      : null;
  });
  const primaryItems = computed(() =>
    buildMobilePrimaryItems(sidebarSections.value, platformKey.value).map(
      (item) => ({ ...item, component: resolveIcon(item.icon) }),
    ),
  );
  const extraItems = computed(() =>
    buildMobileExtraItems(sidebarSections.value, platformKey.value).map(
      (item) => ({ ...item, component: resolveIcon(item.icon) }),
    ),
  );
  const platforms = computed(() =>
    businessSections.value
      .map((section) => ({
        key: section.key,
        title: section.title,
        image: platformImages[section.key],
        path:
          section.path ||
          section.children?.find((item) => item.path)?.path ||
          "",
      }))
      .filter((item) => item.path),
  );
  const systemItems = computed(() => {
    if (currentUser.value?.role !== "admin") return [];
    const systemSection = sidebarSections.value.find(
      (section) => section.key === "system",
    );
    return [
      {
        key: "dashboard",
        title: "综合总览",
        path: "/dashboard",
        component: resolveIcon("Odometer"),
      },
      ...(systemSection?.children || []).map((item) => ({
        ...item,
        component: resolveIcon(item.icon),
      })),
    ];
  });
  const activeTab = computed(() => {
    if (mobileMoreVisible.value) return "more";
    return primaryItems.value.some((item) => item.path === route.path)
      ? route.path
      : "more";
  });

  function scrollPageToTop() {
    document
      .querySelector(".main-shell .el-main")
      ?.scrollTo({ top: 0, behavior: "smooth" });
  }

  function completePendingAction() {
    if (pendingLogout) {
      pendingLogout = false;
      onLogout();
    } else if (pendingPath) {
      const path = pendingPath;
      pendingPath = "";
      if (path !== route.path) router.push(path);
      else scrollPageToTop();
    }
  }

  function openPath(path, fromPopup = false) {
    if (!path) return;
    if (fromPopup && mobileMoreVisible.value) {
      pendingPath = path;
      mobileMoreVisible.value = false;
      if (!historyActive) completePendingAction();
      return;
    }
    if (path === route.path) scrollPageToTop();
    else router.push(path);
  }

  function openMore() {
    if (mobileMoreVisible.value) return;
    historyActive = true;
    window.history.pushState({ signinMobileMore: true }, "");
    mobileMoreVisible.value = true;
  }

  function handlePopState() {
    if (!historyActive) return;
    historyActive = false;
    mobileMoreVisible.value = false;
    completePendingAction();
  }

  function logout() {
    pendingLogout = true;
    mobileMoreVisible.value = false;
    if (!historyActive) completePendingAction();
  }

  function updateKeyboardState() {
    const viewport = window.visualViewport;
    mobileKeyboardOpen.value = Boolean(
      viewport && viewport.height < window.innerHeight * 0.72,
    );
  }

  function attachMobileNavigation() {
    window.addEventListener("popstate", handlePopState);
    window.visualViewport?.addEventListener("resize", updateKeyboardState);
    updateKeyboardState();
  }

  function detachMobileNavigation() {
    window.removeEventListener("popstate", handlePopState);
    window.visualViewport?.removeEventListener("resize", updateKeyboardState);
  }

  watch(
    () => route.path,
    (path) => {
      const detected = detectMobilePlatform(path);
      if (detected) localStorage.setItem(MOBILE_PLATFORM_STORAGE_KEY, detected);
    },
    { immediate: true },
  );
  watch(mobileMoreVisible, (visible) => {
    if (!visible && historyActive) window.history.back();
  });

  return {
    mobileMoreVisible,
    mobileKeyboardOpen,
    mobilePlatform: platform,
    mobilePrimaryItems: primaryItems,
    mobileExtraItems: extraItems,
    mobilePlatforms: platforms,
    mobileSystemItems: systemItems,
    mobileActiveTab: activeTab,
    openMobilePath: openPath,
    openMobileMore: openMore,
    mobileLogout: logout,
    attachMobileNavigation,
    detachMobileNavigation,
  };
}
