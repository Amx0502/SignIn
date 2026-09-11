<template>
  <el-config-provider :locale="zhCn">
    <router-view v-if="isLoginPage" />
    <el-container
      v-else
      class="app-wrapper"
      :class="{ 'app-wrapper--keyboard-open': mobileKeyboardOpen }"
    >
      <el-aside
        :width="sidebarCollapsed ? '80px' : '280px'"
        class="sidebar"
        :class="{ 'sidebar-collapsed': sidebarCollapsed }"
      >
        <div
          class="brand"
          role="button"
          tabindex="0"
          aria-label="打开综合总览"
          @click="router.push('/dashboard')"
          @keydown.enter="router.push('/dashboard')"
        >
          <img src="./img/logo.png" class="logo-img" alt="签到" />
          <div v-if="!sidebarCollapsed">
            <h1>签到管理系统</h1>
            <p>Professional Admin Console</p>
          </div>
        </div>
        <div class="sidebar-menu-scroll">
          <el-menu
            :key="sidebarMenuRenderKey"
            ref="sidebarMenuRef"
            :default-active="$route.path"
            router
            class="sidebar-menu"
            :collapse="sidebarCollapsed"
            :persistent="false"
            @select="closeSidebar"
          >
            <template v-for="parent in sidebarSections" :key="parent.key">
              <el-sub-menu v-if="!parent.path" :index="`menu:${parent.key}`">
                <template #title>
                  <el-icon>
                    <img
                      v-if="isImageMenuIcon(parent.icon)"
                      :src="menuImage(parent.icon)"
                      class="menu-custom-icon"
                      :alt="parent.title"
                    />
                    <component :is="menuIcon(parent.icon)" v-else />
                  </el-icon>
                  <span>{{ parent.title }}</span>
                </template>
                <el-menu-item
                  v-for="child in parent.children || []"
                  :key="child.key"
                  :index="child.path"
                >
                  <el-icon><component :is="menuIcon(child.icon)" /></el-icon>
                  <span>{{ child.title }}</span>
                </el-menu-item>
              </el-sub-menu>
              <el-menu-item v-else :index="parent.path">
                <el-icon>
                  <img
                    v-if="isImageMenuIcon(parent.icon)"
                    :src="menuImage(parent.icon)"
                    class="menu-custom-icon"
                    :alt="parent.title"
                  />
                  <component :is="menuIcon(parent.icon)" v-else />
                </el-icon>
                <span>{{ parent.title }}</span>
              </el-menu-item>
            </template>
          </el-menu>
        </div>
      </el-aside>

      <el-container class="main-shell">
        <el-header class="top-header">
          <div class="header-left">
            <el-button
              class="menu-btn"
              :icon="Menu"
              :aria-label="sidebarCollapsed ? '展开菜单' : '收起菜单'"
              @click="toggleSidebar"
            >
              {{ sidebarCollapsed ? "展开菜单" : "收起菜单" }}
            </el-button>
            <img
              v-if="isMobile"
              :src="mobilePlatform?.image || appLogo"
              class="mobile-header-logo"
              :alt="mobilePlatform ? `${mobilePlatform.title} Logo` : '签到管理系统'"
            />
            <div class="header-copy">
              <p class="breadcrumb">
                <span>{{ breadcrumb.parentTitle }}</span>
                <span class="breadcrumb-current"> / {{ breadcrumb.title }}</span>
              </p>
              <h2>{{ breadcrumb.title }}</h2>
            </div>
          </div>
          <el-space wrap class="header-right">
            <span
              class="header-current-time"
              aria-label="当前时间"
              role="timer"
            >
              <span class="header-current-time__indicator"></span>
              <span class="header-current-time__content">
                <span class="header-current-time__date">{{
                  currentTime.slice(0, 10)
                }}</span>
                <span class="header-current-time__clock">{{
                  currentTime.slice(11)
                }}</span>
              </span>
            </span>
            <el-popover
              v-model:visible="notifyVisible"
              placement="bottom-end"
              :width="isMobile ? 300 : 400"
              trigger="click"
              popper-class="notify-popper"
            >
              <template #reference>
                <el-badge
                  :value="unreadCount"
                  :hidden="unreadCount === 0"
                  :max="99"
                  class="notify-badge"
                  :class="{ pulse: unreadCount > 0 }"
                >
                  <el-button
                    class="notify-btn"
                    :icon="Bell"
                    circle
                    aria-label="通知"
                  />
                </el-badge>
              </template>
              <div class="notify-panel">
                <div class="notify-header">
                  <span>通知</span>
                  <span v-if="unreadCount" class="notify-unread"
                    >（{{ unreadCount }} 条未读）</span
                  >
                  <div class="notify-header-actions">
                    <el-select
                      v-model="notifyLevelFilter"
                      size="small"
                      style="width: 108px"
                    >
                      <el-option label="全部级别" value="ALL" />
                      <el-option label="INFO" value="INFO" />
                      <el-option label="WARNING" value="WARNING" />
                      <el-option label="ERROR" value="ERROR" />
                    </el-select>
                    <el-switch
                      v-model="dndEnabled"
                      size="small"
                      active-text="免打扰"
                      @change="toggleDnd"
                    />
                  </div>
                </div>
                <div v-if="notifyGroups.length" class="notify-list">
                  <div
                    v-for="group in notifyGroups"
                    :key="group.key"
                    class="notify-group"
                  >
                    <div class="notify-group-title">
                      {{ group.label }}
                      <span class="notify-group-count">{{
                        group.items.length
                      }}</span>
                    </div>
                    <div
                      v-for="item in group.items"
                      :key="item.id"
                      class="notify-item"
                      :class="[
                        `notify-level-${item.level.toLowerCase()}`,
                        { unread: !item.read },
                      ]"
                      @click="openNotification(item)"
                    >
                      <span
                        class="notify-dot"
                        :class="`notify-dot-${item.level.toLowerCase()}`"
                      ></span>
                      <div class="notify-body">
                        <div class="notify-title">
                          {{ item.title }}
                          <span class="notify-time">{{ item.time }}</span>
                        </div>
                        <div class="notify-message">{{ item.message }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无通知" :image-size="60" />
                <div class="notify-footer">
                  <el-button
                    link
                    type="primary"
                    size="small"
                    :disabled="!notifications.length"
                    @click="markAllRead"
                    >全部已读</el-button
                  >
                  <el-button
                    link
                    size="small"
                    :disabled="!notifications.length"
                    @click="clearNotifications"
                    >清空通知</el-button
                  >
                </div>
              </div>
            </el-popover>
            <el-dropdown @command="handleUserCommand">
              <span class="user-info" role="button" tabindex="0" aria-label="用户菜单">
                <el-icon><User /></el-icon>
                <span>{{ currentUser?.username || "用户" }}</span>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </el-space>
        </el-header>
        <div class="tabs-bar" @wheel.prevent="onTabsWheel">
          <button
            v-show="tabsOverflow"
            class="tabs-nav-btn"
            :aria-label="'向左滚动'"
            @click="scrollTabs(-1)"
          >
            <el-icon><ArrowLeft /></el-icon>
          </button>
          <div class="tabs-scroll" ref="tabsScrollRef">
            <div class="tabs-track">
              <div
                v-for="element in tabs"
                :key="element.path"
                class="tab-item"
                :class="{ active: element.path === route.path }"
                :title="
                  element.parentTitle
                    ? element.parentTitle + ' / ' + element.title
                    : element.title
                "
                @click="activateTab(element.path)"
                @click.middle.prevent="closeTab(element.path)"
              >
                <el-icon class="tab-icon"
                  ><component :is="tabIcon(element)"
                /></el-icon>
                <span class="tab-title">{{ element.title }}</span>
                <span
                  v-if="tabs.length > 1"
                  class="tab-close"
                  :aria-label="'关闭标签'"
                  @click.stop="closeTab(element.path)"
                >
                  <el-icon><Close /></el-icon>
                </span>
              </div>
            </div>
          </div>
          <button
            v-show="tabsOverflow"
            class="tabs-nav-btn"
            :aria-label="'向右滚动'"
            @click="scrollTabs(1)"
          >
            <el-icon><ArrowRight /></el-icon>
          </button>
          <el-dropdown trigger="click" @command="handleTabMenuCommand">
            <button class="tabs-nav-btn" :aria-label="'标签操作菜单'">
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="close-left" :disabled="!canCloseLeft"
                  >关闭左侧</el-dropdown-item
                >
                <el-dropdown-item
                  command="close-right"
                  :disabled="!canCloseRight"
                  >关闭右侧</el-dropdown-item
                >
                <el-dropdown-item
                  command="close-others"
                  :disabled="!canCloseOthers"
                  >关闭其他</el-dropdown-item
                >
                <el-dropdown-item
                  divided
                  command="close-all"
                  :disabled="!canCloseAll"
                  >关闭全部</el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <el-main>
          <router-view />
        </el-main>
      </el-container>

      <div
        v-if="!sidebarCollapsed && isMobile"
        class="sidebar-mask"
        @click="closeSidebar"
      ></div>
    </el-container>

    <van-tabbar
      v-if="isMobile && !isLoginPage && mobilePlatform"
      :model-value="mobileActiveTab"
      fixed
      safe-area-inset-bottom
      :border="false"
      :z-index="50"
      active-color="#2563eb"
      inactive-color="#718096"
      class="mobile-tabbar"
      :class="{ 'mobile-tabbar--keyboard-open': mobileKeyboardOpen }"
    >
      <van-tabbar-item
        v-for="item in mobilePrimaryItems"
        :key="item.key"
        :name="item.path"
        :aria-label="item.label"
        @click="openMobilePath(item.path)"
      >
        <template #icon
          ><el-icon><component :is="item.component" /></el-icon
        ></template>
        {{ item.label }}
      </van-tabbar-item>
      <van-tabbar-item name="more" aria-label="更多" @click="openMobileMore">
        <template #icon
          ><el-icon><Grid /></el-icon
        ></template>
        更多
      </van-tabbar-item>
    </van-tabbar>

    <van-popup
      v-if="isMobile && !isLoginPage"
      v-model:show="mobileMoreVisible"
      position="bottom"
      round
      safe-area-inset-bottom
      teleport="body"
      :style="{ maxHeight: '78vh' }"
      class="mobile-more-popup"
    >
      <header class="mobile-more-header">
        <img
          v-if="mobilePlatform"
          :src="mobilePlatform.image"
          :alt="mobilePlatform.title"
        />
        <div>
          <strong>更多功能</strong>
          <span>当前平台 · {{ mobilePlatform?.title }}</span>
        </div>
        <button
          type="button"
          class="mobile-more-close"
          aria-label="关闭更多功能"
          @click="mobileMoreVisible = false"
        >
          <el-icon><Close /></el-icon>
        </button>
      </header>

      <section v-if="mobilePlatforms.length" class="mobile-more-section">
        <div class="mobile-more-section__heading">
          <h3>切换平台</h3>
          <span>选择后同步切换底部主导航</span>
        </div>
        <van-grid clickable :border="false" :column-num="3" :gutter="8">
          <van-grid-item
            v-for="item in mobilePlatforms"
            :key="item.key"
            :class="{ 'is-current-platform': item.key === mobilePlatform?.key }"
            @click="openMobilePath(item.path, true)"
          >
            <template #icon
              ><img
                :src="item.image"
                :alt="item.title"
                class="mobile-platform-icon"
            /></template>
            <template #text>
              <strong>{{ item.title }}</strong>
              <small>{{
                item.key === mobilePlatform?.key ? "当前平台" : "进入平台"
              }}</small>
            </template>
          </van-grid-item>
        </van-grid>
      </section>

      <section
        v-if="mobileExtraItems.length"
        class="mobile-more-section mobile-more-section--extras"
      >
        <div class="mobile-more-section__heading">
          <h3>{{ mobilePlatform?.title }}其他功能</h3>
          <span>未固定在底栏的功能</span>
        </div>
        <van-cell-group inset>
          <van-cell
            v-for="item in mobileExtraItems"
            :key="item.key"
            clickable
            :title="item.title"
            :label="item.description"
            @click="openMobilePath(item.path, true)"
          >
            <template #icon>
              <span class="mobile-cell-icon"
                ><el-icon><component :is="item.component" /></el-icon
              ></span>
            </template>
            <template #right-icon><el-icon><ArrowRight /></el-icon></template>
          </van-cell>
        </van-cell-group>
      </section>

      <section
        v-if="mobileSystemItems.length"
        class="mobile-more-section mobile-more-section--system"
      >
        <div class="mobile-more-section__heading">
          <h3>管理功能</h3>
          <span>仅管理员可见</span>
        </div>
        <van-cell-group inset>
          <van-cell
            v-for="item in mobileSystemItems"
            :key="item.key"
            clickable
            :title="item.title"
            :label="item.description"
            @click="openMobilePath(item.path, true)"
          >
            <template #icon>
              <span class="mobile-cell-icon"
                ><el-icon><component :is="item.component" /></el-icon
              ></span>
            </template>
            <template #right-icon><el-icon><ArrowRight /></el-icon></template>
          </van-cell>
        </van-cell-group>
      </section>

      <section class="mobile-more-section mobile-more-section--account">
        <div class="mobile-more-section__heading">
          <h3>账户</h3>
          <span>{{ currentUser?.username || "当前用户" }}</span>
        </div>
        <van-cell-group inset>
          <van-cell
            clickable
            title="修改密码"
            label="更新当前账户登录密码"
            @click="openMobilePath('/change-password', true)"
          >
            <template #icon>
              <span class="mobile-cell-icon"><el-icon><Key /></el-icon></span>
            </template>
            <template #right-icon><el-icon><ArrowRight /></el-icon></template>
          </van-cell>
          <van-cell
            clickable
            title="退出登录"
            label="安全退出当前账户"
            class="mobile-logout-cell"
            @click="mobileLogout"
          >
            <template #icon>
              <span class="mobile-cell-icon mobile-cell-icon--danger"
                ><el-icon><SwitchButton /></el-icon
              ></span>
            </template>
            <template #right-icon><el-icon><ArrowRight /></el-icon></template>
          </van-cell>
        </van-cell-group>
      </section>
    </van-popup>
  </el-config-provider>
</template>

<script setup>
import {
  ref,
  computed,
  defineAsyncComponent,
  onMounted,
  onUnmounted,
} from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  Odometer,
  User,
  Document,
  Timer,
  List,
  Menu,
  UserFilled,
  Grid,
  Setting,
  Close,
  Bell,
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  Key,
  SwitchButton,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import "vant/lib/grid/style";
import "vant/lib/grid-item/style";
import "vant/lib/cell/style";
import "vant/lib/cell-group/style";
import "vant/lib/popup/style";
import "vant/lib/tabbar/style";
import "vant/lib/tabbar-item/style";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { useAppState } from "./composables/useAppState";
import { formatCurrentTime } from "./utils/currentTime";
import { getBreadcrumb } from "./utils/breadcrumb";
import { logoutApi } from "./api";
import xxqdImage from "./img/xxqd.png";
import classCubeImage from "./img/bjmf.png";
import miaoyingImage from "./img/miaoying.png";
import appLogo from "./img/logo.png";
import {
  menuState,
  resetMenuState,
  startMenuSync,
  stopMenuSync,
} from "./menu/menuStore.js";
import { buildSidebarSections } from "./menu/sidebarSections.js";
import { useMobileNavigation } from "./composables/useMobileNavigation.js";
import { useNotifications } from "./composables/useNotifications.js";
import { useVisitedTabs } from "./composables/useVisitedTabs.js";

const VanGrid = defineAsyncComponent(() => import("vant/es/grid"));
const VanGridItem = defineAsyncComponent(() => import("vant/es/grid-item"));
const VanCell = defineAsyncComponent(() => import("vant/es/cell"));
const VanCellGroup = defineAsyncComponent(() => import("vant/es/cell-group"));
const VanPopup = defineAsyncComponent(() => import("vant/es/popup"));
const VanTabbar = defineAsyncComponent(() => import("vant/es/tabbar"));
const VanTabbarItem = defineAsyncComponent(() => import("vant/es/tabbar-item"));

const router = useRouter();
const route = useRoute();

const { logs } = useAppState();

const sidebarCollapsed = ref(false);
const sidebarMenuRef = ref(null);
const sidebarMenuRenderKey = ref(0);
const isMobile = ref(false);
const currentUser = ref(null);
const currentTime = ref(formatCurrentTime());
const breadcrumb = computed(() => getBreadcrumb(route.meta));
const sidebarSections = computed(() =>
  buildSidebarSections(menuState.menus, currentUser.value?.role === "admin"),
);
let currentTimeTimer = null;
const iconMap = {
  Odometer,
  User,
  Document,
  Timer,
  List,
  Grid,
  Setting,
  UserFilled,
  Menu,
};
const imageMap = {
  xxqd: xxqdImage,
  class_cube: classCubeImage,
  miaoying: miaoyingImage,
};

const isLoginPage = computed(() => route.path === "/login");

const {
  mobileMoreVisible,
  mobileKeyboardOpen,
  mobilePlatform,
  mobilePrimaryItems,
  mobileExtraItems,
  mobilePlatforms,
  mobileSystemItems,
  mobileActiveTab,
  openMobilePath,
  openMobileMore,
  mobileLogout,
  attachMobileNavigation,
  detachMobileNavigation,
} = useMobileNavigation({
  router,
  route,
  sidebarSections,
  currentUser,
  platformImages: {
    xxqd: xxqdImage,
    class_cube: classCubeImage,
    miaoying: miaoyingImage,
  },
  resolveIcon: (name) => iconMap[name] || Grid,
  onLogout: () => handleUserCommand("logout"),
});

const {
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
} = useVisitedTabs({
  router,
  route,
  currentUser,
  isMobile,
  sidebarSections,
  resolveIcon: (name) => iconMap[name] || Grid,
});

const {
  notifyVisible,
  notifications,
  notifyLevelFilter,
  dndEnabled,
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
} = useNotifications({ router, route, currentUser, isLoginPage, logs });
function menuIcon(name) {
  return iconMap[name] || Grid;
}
function isImageMenuIcon(name) {
  return Boolean(imageMap[name]);
}
function menuImage(name) {
  return imageMap[name] || "";
}

function getUserInfo() {
  const userStr = localStorage.getItem("user");
  if (userStr) {
    try {
      currentUser.value = JSON.parse(userStr);
    } catch {
      currentUser.value = null;
    }
  }
}

async function handleUserCommand(command) {
  if (command === "logout") {
    try {
      await logoutApi();
    } catch {
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("expires_at");
      localStorage.removeItem("user");
      resetMenuState();
      clearTabs();
      stopCcLogPolling();
      resetNotifications();
      currentUser.value = null;
      ElMessage.success("已退出登录");
      router.push("/login");
    }
  }
}

function checkMobile() {
  isMobile.value = window.innerWidth <= 768;
  sidebarCollapsed.value = window.innerWidth <= 1024;
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function closeSidebar() {
  if (isMobile.value || sidebarCollapsed.value) {
    sidebarMenuRef.value?.close("menu:xxqd");
    sidebarMenuRef.value?.close("menu:class_cube");
    sidebarMenuRef.value?.close("menu:miaoying");
    sidebarMenuRef.value?.close("menu:system");
    sidebarMenuRenderKey.value += 1;
    sidebarCollapsed.value = true;
  }
}

onMounted(async () => {
  checkMobile();
  getUserInfo();
  loadTabs();
  loadNotifications();
  syncCurrentTab();
  currentTimeTimer = window.setInterval(() => {
    currentTime.value = formatCurrentTime();
  }, 1000);
  window.addEventListener("resize", checkMobile);
  window.addEventListener("resize", updateTabsOverflow);
  attachMobileNavigation();
  if (!isLoginPage.value) {
    startTabsObserver();
    try {
      await startMenuSync(router);
    } catch (error) {
      ElMessage.warning(error.message || "菜单配置暂时无法同步");
    }
    syncCcLogPolling();
  }
});

onUnmounted(() => {
  window.clearInterval(currentTimeTimer);
  window.removeEventListener("resize", checkMobile);
  window.removeEventListener("resize", updateTabsOverflow);
  detachMobileNavigation();
  stopTabsObserver();
  stopCcLogPolling();
  stopMenuSync();
});
</script>

<style scoped>
.app-wrapper {
  width: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  overflow-x: clip;
}
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #07111f 0%, #0f172a 46%, #111827 100%);
  color: #e5eefc;
  padding: 22px 14px;
  box-shadow: 18px 0 45px rgba(15, 23, 42, 0.18);
  z-index: 20;
  transition: width 0.3s ease;
}
.sidebar.sidebar-collapsed {
  padding: 14px 8px;
}
.sidebar::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at 20% 0%,
    rgba(59, 130, 246, 0.28),
    transparent 34%
  );
  pointer-events: none;
}
.brand {
  position: relative;
  z-index: 1;
  flex: none;
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
  padding: 0 8px;
}
.brand h1 {
  margin: 0;
  font-size: 21px;
  color: #fff;
  letter-spacing: -0.03em;
}
.brand p {
  margin: 6px 0 0;
  font-size: 11px;
  color: #9fb0cf;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.sidebar-menu-scroll {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.sidebar-menu-scroll::-webkit-scrollbar {
  width: 6px;
}
.sidebar-menu-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.sidebar-menu-scroll::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.28);
  border-radius: 999px;
}
.sidebar-menu-scroll:hover::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.48);
}
.sidebar-menu {
  position: relative;
  border-right: none;
  background: transparent;
}
.sidebar-menu :deep(.el-sub-menu__title),
.sidebar-menu :deep(.el-menu-item) {
  border-radius: 14px;
  margin: 5px 0;
  height: 48px;
  line-height: 48px;
  color: #dbeafe;
  transition: all 0.22s ease;
}
.sidebar-menu :deep(.el-sub-menu__title:hover),
.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(96, 165, 250, 0.14);
  transform: translateX(3px);
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(
    90deg,
    rgba(37, 99, 235, 0.28),
    rgba(14, 165, 233, 0.12)
  );
  box-shadow: inset 3px 0 0 #60a5fa;
  color: #fff;
  font-weight: 700;
}
.sidebar-menu :deep(.el-sub-menu .el-menu) {
  background: rgba(255, 255, 255, 0.035);
  border-radius: 14px;
  padding: 4px;
}
.menu-custom-icon {
  width: 22px;
  height: 22px;
  object-fit: contain;
  display: block;
}
.logo-img {
  width: 48px;
  height: 48px;
  object-fit: contain;
  display: block;
}
.mobile-header-logo {
  display: none;
}
.main-shell {
  min-width: 0;
  overflow-x: clip;
}
.main-shell :deep(.el-main) {
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}
.top-header {
  min-height: 76px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 0 28px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(18px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}
.header-copy {
  min-width: 0;
}
.menu-btn {
  flex: none;
  margin-right: 4px;
  color: #2563eb;
  border-color: #bfdbfe;
  background: #eff6ff;
}
.breadcrumb {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 12px;
}
.top-header h2 {
  margin: 0;
  font-size: 22px;
  color: #0f172a;
  letter-spacing: -0.03em;
}
.header-current-time {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-height: 42px;
  padding: 6px 14px 6px 11px;
  overflow: hidden;
  color: #1e3a8a;
  white-space: nowrap;
  border: 1px solid rgba(96, 165, 250, 0.42);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      rgba(239, 246, 255, 0.96),
      rgba(219, 234, 254, 0.72)
    ),
    radial-gradient(circle at 100% 0%, rgba(14, 165, 233, 0.2), transparent 58%);
  box-shadow:
    0 8px 22px rgba(37, 99, 235, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.header-current-time::after {
  content: "";
  position: absolute;
  width: 34px;
  height: 34px;
  right: -15px;
  top: -18px;
  border-radius: 50%;
  background: rgba(56, 189, 248, 0.2);
}
.header-current-time__indicator {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: #38bdf8;
  box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.14);
  animation: headerTimePulse 2s ease-in-out infinite;
}
.header-current-time__content {
  display: grid;
  gap: 1px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.header-current-time__date {
  color: #64748b;
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.06em;
}
.header-current-time__clock {
  color: #1e3a8a;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.04em;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #374151;
}
.user-info:hover {
  background: rgba(0, 0, 0, 0.05);
}
.sidebar-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 15;
  animation: fadeIn 0.2s ease;
}
@keyframes pulse {
  50% {
    box-shadow: 0 0 0 10px rgba(34, 197, 94, 0);
  }
}
@keyframes headerTimePulse {
  50% {
    opacity: 0.58;
    box-shadow: 0 0 0 7px rgba(56, 189, 248, 0);
  }
}
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.tabs-bar {
  position: sticky;
  top: 76px;
  z-index: 9;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 6px 12px 0;
  background: linear-gradient(
    180deg,
    rgba(239, 246, 255, 0.92),
    rgba(255, 255, 255, 0.66)
  );
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(191, 219, 254, 0.9);
  box-shadow: 0 4px 18px rgba(37, 99, 235, 0.06);
  overflow: hidden;
}
.tabs-scroll {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 0 2px 6px;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
  scroll-behavior: smooth;
  scroll-snap-type: x proximity;
  touch-action: pan-x;
}
.tabs-scroll::-webkit-scrollbar {
  display: none;
}
.tabs-track {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
}
.tab-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: none;
  height: 34px;
  padding: 0 10px 0 12px;
  border: 1px solid transparent;
  border-radius: 12px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: all 0.22s ease;
  animation: tabIn 0.25s cubic-bezier(0.34, 1.3, 0.64, 1);
  scroll-snap-align: start;
}
.tab-item .tab-icon {
  color: #60a5fa;
  font-size: 15px;
  transition: color 0.22s ease;
}
.tab-item:hover {
  color: #1d4ed8;
  background: rgba(219, 234, 254, 0.65);
  border-color: rgba(147, 197, 253, 0.55);
}
.tab-item.active {
  color: #fff;
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 55%, #38bdf8 130%);
  border-color: rgba(255, 255, 255, 0.18);
  box-shadow:
    0 6px 16px rgba(37, 99, 235, 0.32),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
}
.tab-item.active .tab-icon {
  color: #e0f2fe;
}
.tab-item.active::after {
  content: "";
  position: absolute;
  left: 18%;
  right: 18%;
  bottom: -8px;
  height: 3px;
  border-radius: 3px;
  background: linear-gradient(90deg, #2563eb, #38bdf8);
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.8);
  animation: tabActivePulse 2.4s ease-in-out infinite;
}
.tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  font-size: 11px;
  transition: all 0.18s ease;
}
.tab-close {
  opacity: 0.85;
  margin-left: 1px;
}
.tab-item.active .tab-close {
  color: #e0f2fe;
}
.tab-close:hover {
  opacity: 1 !important;
  color: #fff;
  background: #ef4444;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.5);
}
.tabs-nav-btn {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(147, 197, 253, 0.7);
  border-radius: 9px;
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  color: #2563eb;
  cursor: pointer;
  transition: all 0.2s ease;
}
.tabs-nav-btn:hover {
  background: linear-gradient(135deg, #dbeafe, #eff6ff);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.18);
}
.tabs-nav-btn:active {
  transform: scale(0.95);
}
.notify-badge {
  display: inline-flex;
  align-items: center;
}
.notify-badge.pulse .notify-btn {
  animation: notifyPulse 1.6s ease-in-out infinite;
}
.notify-btn {
  border: 1px solid rgba(96, 165, 250, 0.45);
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  color: #2563eb;
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.1);
  transition: all 0.2s ease;
}
.notify-btn:hover {
  color: #1d4ed8;
  border-color: #60a5fa;
}
.notify-popper {
  border-radius: 14px;
}
.notify-panel {
  display: grid;
  gap: 10px;
}
.notify-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-weight: 700;
  color: #0f172a;
}
.notify-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.notify-unread {
  color: #ef4444;
  font-size: 12px;
  font-weight: 600;
}
.notify-list {
  display: grid;
  gap: 8px;
  max-height: 340px;
  overflow-y: auto;
}
.notify-group {
  display: grid;
  gap: 4px;
}
.notify-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 2px 6px;
}
.notify-group-count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: rgba(148, 163, 184, 0.18);
  color: #475569;
  font-size: 11px;
}
.notify-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.18s ease;
}
.notify-item:hover {
  background: #eff6ff;
}
.notify-item.unread {
  background: rgba(219, 234, 254, 0.5);
}
.notify-dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
}
.notify-dot-info {
  background: #94a3b8;
}
.notify-dot-warning {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}
.notify-dot-error {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
}
.notify-body {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 2px;
}
.notify-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.notify-item.unread .notify-title {
  color: #1d4ed8;
}
.notify-message {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}
.notify-item.notify-level-warning .notify-message {
  color: #b45309;
}
.notify-item.notify-level-error .notify-message {
  color: #b91c1c;
}
.notify-time {
  font-size: 11px;
  color: #94a3b8;
  margin-left: auto;
  flex: none;
}
.notify-footer {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  border-top: 1px solid #eef2f7;
  padding-top: 8px;
}

@keyframes notifyPulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(37, 99, 235, 0);
  }
}

@keyframes tabIn {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
@keyframes tabActivePulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

.mobile-tabbar {
  --van-tabbar-height: 62px;
  --van-tabbar-background: rgba(255, 255, 255, 0.96);
  --van-tabbar-item-active-background: #f4f8ff;
  --van-tabbar-item-font-size: 11px;
  border-top: 1px solid rgba(191, 219, 254, 0.85);
  box-shadow: 0 -4px 16px rgba(15, 23, 42, 0.07);
  backdrop-filter: blur(18px);
}
.mobile-tabbar :deep(.van-tabbar-item) {
  min-width: 0;
  min-height: 54px;
  border-radius: 13px;
}
.mobile-tabbar :deep(.van-tabbar-item__icon) {
  margin-bottom: 3px;
  font-size: 21px;
}
.mobile-tabbar :deep(.van-tabbar-item__text) {
  overflow: hidden;
  max-width: 100%;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mobile-tabbar--keyboard-open {
  pointer-events: none;
  opacity: 0;
  transform: translateY(110%);
}

.mobile-more-popup {
  box-sizing: border-box;
  width: min(520px, 100%);
  padding: 18px 0 16px;
  overflow-y: auto;
  --van-popup-round-radius: 24px;
  --van-grid-item-content-background: #f8fafc;
}
.mobile-more-header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 1px 16px 15px;
  border-bottom: 1px solid #e2e8f0;
}
.mobile-more-header img {
  width: 36px;
  height: 36px;
  flex: none;
  object-fit: contain;
}
.mobile-more-header > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}
.mobile-more-header strong {
  color: #172033;
  font-size: 18px;
  line-height: 1.2;
}
.mobile-more-header span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mobile-more-close {
  display: grid;
  width: 42px;
  height: 42px;
  flex: none;
  margin-left: auto;
  place-items: center;
  border: 0;
  border-radius: 13px;
  background: #f1f5f9;
  color: #64748b;
  font: inherit;
  cursor: pointer;
}
.mobile-more-close:active {
  background: #e2e8f0;
  color: #334155;
}
.mobile-more-section {
  margin-top: 18px;
}
.mobile-more-section__heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 0 16px 9px;
}
.mobile-more-section__heading h3 {
  margin: 0;
  color: #334155;
  font-size: 13px;
  font-weight: 750;
}
.mobile-more-section__heading span {
  overflow: hidden;
  color: #94a3b8;
  font-size: 10px;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mobile-more-section :deep(.van-grid-item__content) {
  min-height: 70px;
  gap: 7px;
  padding: 9px 4px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  color: #334155;
}
.mobile-more-section :deep(.van-grid-item__content:active) {
  background: #eff6ff;
}
.mobile-more-section :deep(.van-grid-item__icon) {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 10px;
  background: #eaf3ff;
  color: #2563eb;
  font-size: 18px;
}
.mobile-more-section :deep(.van-grid-item__text) {
  display: grid;
  justify-items: center;
  gap: 3px;
  max-width: 100%;
  color: inherit;
  font-size: 12px;
  font-weight: 650;
}
.mobile-more-section :deep(.van-grid-item__text span),
.mobile-more-section :deep(.van-grid-item__text strong) {
  overflow: hidden;
  max-width: 100%;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mobile-more-section :deep(.van-grid-item__text small) {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 500;
}
.mobile-platform-icon {
  width: 29px;
  height: 29px;
  object-fit: contain;
}
.mobile-more-section :deep(.van-grid-item__icon:has(.mobile-platform-icon)) {
  width: 36px;
  height: 36px;
  background: transparent;
}
.is-current-platform :deep(.van-grid-item__content) {
  border-color: #60a5fa;
  background: #eff6ff;
  color: #1d4ed8;
}
.mobile-more-section :deep(.van-cell-group--inset) {
  margin: 0;
  border-radius: 0;
}
.mobile-more-section :deep(.van-cell) {
  min-height: 62px;
  align-items: center;
  padding: 10px 16px;
}
.mobile-more-section :deep(.van-cell::after) {
  left: 64px;
  right: 16px;
}
.mobile-more-section :deep(.van-cell__title) {
  color: #263247;
  font-size: 14px;
  font-weight: 650;
}
.mobile-more-section :deep(.van-cell__label) {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 11px;
}
.mobile-more-section :deep(.van-cell__right-icon) {
  align-self: center;
  color: #a0aec0;
}
.mobile-cell-icon {
  display: grid;
  width: 36px;
  height: 36px;
  margin-right: 12px;
  place-items: center;
  border-radius: 11px;
  background: #eaf3ff;
  color: #2563eb;
  font-size: 18px;
}
.mobile-cell-icon--danger {
  background: #fff1f2;
  color: #dc2626;
}
.mobile-logout-cell :deep(.van-cell__title) {
  color: #dc2626;
}

@media (max-width: 768px) {
  .tabs-bar {
    display: none;
  }
  .tab-item {
    height: 32px;
    padding: 0 8px 0 10px;
    font-size: 12px;
  }
  .tab-icon {
    display: none;
  }
  .tabs-nav-btn {
    width: 26px;
    height: 26px;
  }
}

@media (max-width: 900px) {
  .top-header {
    padding: 12px 16px;
    height: auto;
    flex-wrap: wrap;
  }
  .header-left {
    flex-wrap: wrap;
  }
}

@media (max-width: 768px) {
  .top-header {
    min-height: 62px;
    padding: 8px 16px;
    flex-wrap: nowrap;
  }
  .header-left {
    flex-direction: row;
    flex-wrap: nowrap;
    align-items: center;
    gap: 8px;
  }
  .top-header h2 {
    font-size: 18px;
    line-height: 1.15;
  }
  .breadcrumb {
    margin-bottom: 2px;
    font-size: 11px;
    line-height: 1.15;
  }
  .breadcrumb-current {
    display: none;
  }
  .menu-btn,
  .header-current-time,
  .sidebar,
  .sidebar-mask {
    display: none;
  }
  .mobile-header-logo {
    display: block;
    width: 34px;
    height: 34px;
    flex: none;
    object-fit: contain;
  }
  .header-right {
    flex: none;
    margin-top: 0;
  }
  .header-right :deep(.el-space__item) {
    display: inline-flex;
  }
  .notify-btn,
  .user-info {
    box-sizing: border-box;
    width: 34px;
    height: 34px;
  }
  .notify-btn {
    min-height: 34px;
    padding: 0;
    box-shadow: none;
  }
  .user-info {
    justify-content: center;
    padding: 0;
    border: 1px solid transparent;
    border-radius: 50%;
    color: #475569;
    background: transparent;
  }
  .user-info:hover,
  .user-info:focus-visible {
    border-color: #dbeafe;
    outline: none;
    background: #f8fafc;
  }
  .user-info > span {
    display: none;
  }
  .main-shell :deep(.el-main) {
    padding: 0;
    padding-bottom: calc(84px + env(safe-area-inset-bottom));
    background: #f1f5f9;
  }
  .app-wrapper--keyboard-open .main-shell :deep(.el-main) {
    padding-bottom: 16px;
  }
}

@media (max-width: 480px) {
  .top-header {
    padding: 8px 14px;
  }
  .breadcrumb {
    max-width: 170px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
