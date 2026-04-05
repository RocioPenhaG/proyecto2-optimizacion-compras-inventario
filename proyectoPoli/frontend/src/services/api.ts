const API_BASE = "/api";

export interface LoginResponse {
  access: string;
  refresh: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch (err) {
    throw new Error(
      "No se pudo conectar al servidor. ¿Está el backend en marcha en http://localhost:8000?"
    );
  }
  if (!res.ok) {
    const contentType = res.headers.get("content-type");
    let message = `Error al iniciar sesión (${res.status})`;
    if (contentType?.includes("application/json")) {
      const data = await res.json().catch(() => ({}));
      const detail = data.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.join(" ");
      else if (detail && typeof detail === "object") message = JSON.stringify(detail);
      else if (data.non_field_errors?.length) message = data.non_field_errors.join(" ");
      else if (data.username?.length) message = data.username.join(" ");
      else if (data.password?.length) message = data.password.join(" ");
    } else {
      const text = await res.text();
      if (text.length > 0) {
        const snippet = text.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);
        if (snippet) message += ": " + snippet;
      }
    }
    throw new Error(message);
  }
  return res.json();
}

export async function refreshToken(refresh: string): Promise<{ access: string }> {
  const res = await fetch(`${API_BASE}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) throw new Error("Sesión expirada");
  return res.json();
}

export async function getMe(accessToken: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error("No autorizado");
  return res.json();
}
