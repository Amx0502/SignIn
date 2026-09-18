// 小小签到「检测填写项」结果缓存
// 按「账号 + 项目序号」缓存检测结果与勾选项，localStorage 持久化（页面刷新后仍有效）。
// 以项目数据的指纹（stable JSON）做失效判断：项目数据变化后缓存自动失效，才会要求重新检测。

const STORE_KEY = "xxqd_fill_options_cache_v1";
const MAX_ENTRIES = 100;

function stableStringify(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys
    .map((k) => `${JSON.stringify(k)}:${stableStringify(value[k])}`)
    .join(",")}}`;
}

function readStore() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const data = raw ? JSON.parse(raw) : null;
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

function writeStore(store) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  } catch {
    /* 存储不可用时静默降级为不缓存 */
  }
}

// 项目数据指纹：项目列表项内容变化（如标题改动、顺序变化）时指纹变化，缓存失效
export function projectFingerprint(projectItem) {
  return stableStringify(projectItem ?? null);
}

// 读取缓存；指纹不匹配（数据已变化）或结构异常时返回 null
export function getFillOptionsCache(accountKey, projectIndex, fingerprint) {
  const entry = readStore()[`${accountKey}|${projectIndex}`];
  if (!entry || typeof entry !== "object") return null;
  if (entry.fingerprint !== fingerprint) return null;
  if (!Array.isArray(entry.items)) return null;
  return {
    items: entry.items,
    title: entry.title || "",
    keys: Array.isArray(entry.keys)
      ? new Set(entry.keys.map(String))
      : null,
    savedAt: entry.savedAt || 0,
  };
}

export function setFillOptionsCache(
  accountKey,
  projectIndex,
  fingerprint,
  { items, title, keys },
) {
  if (!Array.isArray(items)) return;
  const store = readStore();
  store[`${accountKey}|${projectIndex}`] = {
    fingerprint,
    items,
    title: title || "",
    keys: [...(keys || [])].map(String),
    savedAt: Date.now(),
  };
  // 超量时按时间淘汰最旧的记录
  const entries = Object.entries(store);
  if (entries.length > MAX_ENTRIES) {
    entries.sort((a, b) => (a[1].savedAt || 0) - (b[1].savedAt || 0));
    for (const [key] of entries.slice(0, entries.length - MAX_ENTRIES)) {
      delete store[key];
    }
  }
  writeStore(store);
}

export function clearFillOptionsCache(accountKey, projectIndex) {
  const store = readStore();
  delete store[`${accountKey}|${projectIndex}`];
  writeStore(store);
}
