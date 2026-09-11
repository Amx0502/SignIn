import { computed, ref, watch } from "vue";
import classCubeApi from "../api/classCube.js";
import { isCurrentMenuVisible, menuState } from "../menu/menuStore.js";
import { parseLogLine } from "../utils/logConsole.js";

const NOTIFY_STORAGE_PREFIX = "signin_notifications";
const NOTIFY_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const NOTIFY_LEVELS = ["INFO", "WARNING", "ERROR"];

export function useNotifications({
  router,
  route,
  currentUser,
  isLoginPage,
  logs,
}) {
  const notifyVisible = ref(false);
  const notifications = ref([]);
  const notifyLevelFilter = ref("ALL");
  const dndEnabled = ref(false);
  const ccLogs = ref([]);
  let notifySequence = 0;
  let xxqdLogBaselineSet = false;
  let lastXxqdLogKey = "";
  let ccLogBaselineSet = false;
  let lastCcLogKey = "";
  let ccLogTimer = null;

  function storageKey() {
    const userId = currentUser.value?.id;
    return userId != null
      ? `${NOTIFY_STORAGE_PREFIX}:${userId}`
      : NOTIFY_STORAGE_PREFIX;
  }

  function pruneOldNotifications() {
    const cutoff = Date.now() - NOTIFY_TTL_MS;
    notifications.value = notifications.value.filter(
      (item) => (item.ts || 0) >= cutoff,
    );
  }

  function persistNotifications() {
    pruneOldNotifications();
    try {
      localStorage.setItem(
        storageKey(),
        JSON.stringify({
          dnd: dndEnabled.value,
          notifications: notifications.value,
        }),
      );
    } catch {
      /* ignore storage errors */
    }
  }

  function loadNotifications() {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey()) || "null");
      if (parsed && typeof parsed === "object") {
        dndEnabled.value = parsed.dnd === true;
        if (Array.isArray(parsed.notifications)) {
          notifications.value = parsed.notifications
            .filter(
              (item) =>
                item &&
                typeof item.path === "string" &&
                typeof item.message === "string",
            )
            .map((item) => ({
              id: item.id,
              path: item.path,
              source: item.source === "class_cube" ? "class_cube" : "xxqd",
              title: typeof item.title === "string" ? item.title : "",
              level: NOTIFY_LEVELS.includes(item.level) ? item.level : "INFO",
              message: String(item.message || "").slice(0, 120),
              time: typeof item.time === "string" ? item.time : "",
              ts: typeof item.ts === "number" ? item.ts : Date.now(),
              read: item.read === true,
            }));
        }
      }
    } catch {
      /* ignore storage errors */
    }
    pruneOldNotifications();
    notifySequence = notifications.value.reduce(
      (max, item) => Math.max(max, item.id || 0),
      0,
    );
  }

  const menuKeyForPath = (path) =>
    path === "/class-cube/logs" ? "class_cube.logs" : "xxqd.logs";
  function notificationVisible(item) {
    return (
      currentUser.value?.role === "admin" ||
      !menuState.loaded ||
      isCurrentMenuVisible(menuKeyForPath(item.path), currentUser.value)
    );
  }

  const visibleNotifications = computed(() =>
    notifications.value.filter(
      (item) =>
        (notifyLevelFilter.value === "ALL" ||
          item.level === notifyLevelFilter.value) &&
        notificationVisible(item),
    ),
  );
  const unreadCount = computed(
    () =>
      notifications.value.filter(
        (item) => !item.read && notificationVisible(item),
      ).length,
  );
  const notifyGroups = computed(() => {
    const groups = [
      { key: "xxqd", label: "小小签到", items: [] },
      { key: "class_cube", label: "班级魔方", items: [] },
    ];
    const index = { xxqd: groups[0], class_cube: groups[1] };
    visibleNotifications.value.forEach((item) =>
      index[item.source].items.push(item),
    );
    return groups.filter((group) => group.items.length);
  });

  function pushNotification(path, rawLine) {
    if (!notificationVisible({ path })) return;
    const parsed = parseLogLine(rawLine);
    const isClassCube = path === "/class-cube/logs";
    const now = Date.now();
    notifications.value.unshift({
      id: ++notifySequence,
      path,
      source: isClassCube ? "class_cube" : "xxqd",
      title: isClassCube ? "魔方日志" : "运行日志",
      level: NOTIFY_LEVELS.includes(parsed.level) ? parsed.level : "INFO",
      message: (parsed.message || String(rawLine || "")).slice(0, 120),
      time: new Date(now).toLocaleTimeString("zh-CN", { hour12: false }),
      ts: now,
      read: dndEnabled.value,
    });
    if (notifications.value.length > 200) notifications.value.pop();
    persistNotifications();
  }

  function markPathRead(path) {
    let changed = false;
    notifications.value.forEach((item) => {
      if (item.path === path && !item.read) {
        item.read = true;
        changed = true;
      }
    });
    if (changed) persistNotifications();
  }

  function markAllRead() {
    let changed = false;
    notifications.value.forEach((item) => {
      if (!item.read) {
        item.read = true;
        changed = true;
      }
    });
    if (changed) persistNotifications();
  }

  function clearNotifications() {
    notifications.value = [];
    persistNotifications();
  }
  function openNotification(item) {
    if (!item.read) {
      item.read = true;
      persistNotifications();
    }
    notifyVisible.value = false;
    if (item.path !== route.path) router.push(item.path);
  }
  function toggleDnd(value) {
    dndEnabled.value = value;
    persistNotifications();
  }

  function resetNotifications() {
    notifications.value = [];
    notifyVisible.value = false;
    notifyLevelFilter.value = "ALL";
    dndEnabled.value = false;
    xxqdLogBaselineSet = false;
    lastXxqdLogKey = "";
    ccLogBaselineSet = false;
    lastCcLogKey = "";
  }

  const canPollCcLogs = computed(
    () =>
      currentUser.value?.role === "admin" ||
      Boolean(
        currentUser.value &&
          menuState.loaded &&
          isCurrentMenuVisible("class_cube.logs", currentUser.value),
      ),
  );

  async function refreshCcLogs() {
    if (!canPollCcLogs.value) return;
    try {
      const response = await classCubeApi.listLogs(50);
      if (response.ok) ccLogs.value = response.data || [];
    } catch {
      /* ignore polling errors */
    }
  }

  function stopCcLogPolling() {
    if (ccLogTimer) window.clearInterval(ccLogTimer);
    ccLogTimer = null;
  }
  function startCcLogPolling() {
    stopCcLogPolling();
    refreshCcLogs();
    ccLogTimer = window.setInterval(refreshCcLogs, 3000);
  }
  function syncCcLogPolling() {
    if (isLoginPage.value || !canPollCcLogs.value) {
      stopCcLogPolling();
      ccLogs.value = [];
      ccLogBaselineSet = false;
      lastCcLogKey = "";
    } else if (!ccLogTimer) startCcLogPolling();
  }

  loadNotifications();
  watch(
    () => route.path,
    (path) => {
      if (path === "/logs" || path === "/class-cube/logs") markPathRead(path);
    },
    { immediate: true },
  );
  watch(logs, (list) => {
    const last = list?.[list.length - 1];
    const key = last ? String(last) : "";
    if (!xxqdLogBaselineSet) {
      xxqdLogBaselineSet = true;
      lastXxqdLogKey = key;
    } else if (key && key !== lastXxqdLogKey) {
      lastXxqdLogKey = key;
      pushNotification("/logs", last);
    }
  });
  watch(ccLogs, (list) => {
    const last = list?.[list.length - 1];
    const key = last ? String(last) : "";
    if (!ccLogBaselineSet) {
      ccLogBaselineSet = true;
      lastCcLogKey = key;
    } else if (key && key !== lastCcLogKey) {
      lastCcLogKey = key;
      pushNotification("/class-cube/logs", last);
    }
  });
  watch(
    [
      () => menuState.loaded,
      () => menuState.version,
      () => currentUser.value?.id,
      () => currentUser.value?.role,
      () => route.path,
    ],
    syncCcLogPolling,
  );

  return {
    notifyVisible,
    notifications,
    notifyLevelFilter,
    dndEnabled,
    visibleNotifications,
    unreadCount,
    notifyGroups,
    markAllRead,
    clearNotifications,
    openNotification,
    toggleDnd,
    resetNotifications,
    loadNotifications,
    syncCcLogPolling,
    stopCcLogPolling,
  };
}
