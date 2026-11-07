const TOKEN_KEY = "fitness_token";
const USER_KEY = "fitness_user";

export function getToken() { return sessionStorage.getItem(TOKEN_KEY) || ""; }
export function setAuth(token, user) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearAuth() { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY); }
export function getCachedUser() {
  try { return JSON.parse(sessionStorage.getItem(USER_KEY) || "null"); } catch { return null; }
}

export async function api(path, { method = "GET", body, formData } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";

  const resp = await fetch(path, {
    method,
    headers,
    body: formData ? formData : (body ? JSON.stringify(body) : undefined),
  });

  if (resp.status === 401) {
    clearAuth();
    location.hash = "#/login";
    throw new Error("登录已过期，请重新登录");
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `请求失败(${resp.status})`);
  }
  return data;
}

export async function uploadFile(file, kind = "image") {
  const fd = new FormData();
  fd.append("file", file);
  const ep = kind === "video" ? "video" : kind === "avatar" ? "avatar" : "image";
  return api(`/api/upload/${ep}`, { method: "POST", formData: fd });
}
