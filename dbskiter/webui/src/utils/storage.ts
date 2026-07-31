/**
 * 类型安全的 localStorage 工具
 * 支持 JSON 序列化/反序列化、过期时间
 */

/** 存储前缀，避免全局冲突 */
const PREFIX = 'dbskiter-'

/** 过期时间元数据 key（在原始 key 后追加此后缀） */
const EXPIRY_SUFFIX = '__expiry'

function _prefixKey(key: string): string {
  return key.startsWith(PREFIX) ? key : `${PREFIX}${key}`
}

/**
 * 存储任意值（自动 JSON 序列化）
 */
export function set(key: string, value: unknown): void {
  try {
    localStorage.setItem(_prefixKey(key), JSON.stringify(value))
  } catch {
    // localStorage 可能满或不可用，静默失败
  }
}

/**
 * 读取并反序列化存储值
 * @param defaultVal 当 key 不存在或解析失败时返回的默认值
 */
export function get<T>(key: string, defaultVal?: T): T | undefined {
  try {
    const raw = localStorage.getItem(_prefixKey(key))
    if (raw === null) return defaultVal
    return JSON.parse(raw) as T
  } catch {
    return defaultVal
  }
}

/**
 * 移除指定 key
 */
export function remove(key: string): void {
  try {
    localStorage.removeItem(_prefixKey(key))
    localStorage.removeItem(_prefixKey(key) + EXPIRY_SUFFIX)
  } catch {
    // 静默失败
  }
}

/**
 * 读取字符串（不经过 JSON 解析）
 * 适用于纯文本值，如 token
 */
export function getString(key: string, defaultVal = ''): string {
  try {
    const raw = localStorage.getItem(_prefixKey(key))
    return raw ?? defaultVal
  } catch {
    return defaultVal
  }
}

/**
 * 存储字符串（不经过 JSON 序列化）
 */
export function setString(key: string, value: string): void {
  try {
    localStorage.setItem(_prefixKey(key), value)
  } catch {
    // 静默失败
  }
}

/**
 * 存储带过期时间的值
 * @param key  存储键名
 * @param value 存储值
 * @param ttlMs  过期时间（毫秒），从当前时间开始计算
 */
export function setWithExpiry(key: string, value: unknown, ttlMs: number): void {
  const prefixed = _prefixKey(key)
  try {
    localStorage.setItem(prefixed, JSON.stringify(value))
    localStorage.setItem(prefixed + EXPIRY_SUFFIX, String(Date.now() + ttlMs))
  } catch {
    // 静默失败
  }
}

/**
 * 读取带过期时间的值，过期后自动删除并返回默认值
 */
export function getWithExpiry<T>(key: string, defaultVal?: T): T | undefined {
  const prefixed = _prefixKey(key)
  try {
    const expiry = localStorage.getItem(prefixed + EXPIRY_SUFFIX)
    if (expiry !== null && Date.now() > Number(expiry)) {
      localStorage.removeItem(prefixed)
      localStorage.removeItem(prefixed + EXPIRY_SUFFIX)
      return defaultVal
    }
    const raw = localStorage.getItem(prefixed)
    if (raw === null) return defaultVal
    return JSON.parse(raw) as T
  } catch {
    return defaultVal
  }
}

/**
 * 清除所有以 PREFIX 开头的存储项
 */
export function clearAll(): void {
  try {
    const keysToRemove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith(PREFIX)) {
        keysToRemove.push(k)
      }
    }
    keysToRemove.forEach((k) => {
      localStorage.removeItem(k)
      localStorage.removeItem(k + EXPIRY_SUFFIX)
    })
  } catch {
    // 静默失败
  }
}