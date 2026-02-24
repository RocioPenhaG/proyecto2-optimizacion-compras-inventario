const API = "http://127.0.0.1:8000";

const ACCESS_KEY = "access";
const REFRESH_KEY = "refresh";

export function saveTokens({ access, refresh }) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function getAccess() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefresh() {
  return localStorage.getItem(REFRESH_KEY);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export async function login(username, password) {
  const res = await fetch(`${API}/api/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) throw new Error("Usuario o contraseña incorrectos");

  const data = await res.json(); // {access, refresh}
  saveTokens(data);
  return data;
}

export async function refreshAccess() {
  const refresh = getRefresh();
  if (!refresh) throw new Error("No refresh token");

  const res = await fetch(`${API}/api/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (!res.ok) {
    clearTokens();
    throw new Error("Refresh inválido");
  }

  const data = await res.json(); // {access}
  localStorage.setItem(ACCESS_KEY, data.access);
  return data.access;
}

// Fetch con auto-refresh si da 401
export async function apiFetch(path, options = {}, retry = true) {
  const token = getAccess();

  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (res.status === 401 && retry && getRefresh()) {
    await refreshAccess();
    return apiFetch(path, options, false);
  }

  return res;
}

export async function getMe() {
  const res = await apiFetch("/api/me/");
  if (!res.ok) throw new Error("No autorizado");
  return res.json();
}
