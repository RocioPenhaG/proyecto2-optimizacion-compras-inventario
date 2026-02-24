import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useState } from "react";
import { apiFetch } from "../auth";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const roles = (user?.roles || []).map((r) => String(r).toLowerCase());
  const isAdmin = user?.is_staff === true || roles.includes("admin");
  const isCompras = roles.includes("compras");

  const [ping, setPing] = useState(null);
  const [pingErr, setPingErr] = useState("");

  function handleLogout() {
    logout();
    nav("/login", { replace: true });
  }

  async function probarPing() {
    setPing(null);
    setPingErr("");
    try {
      const res = await apiFetch("/api/compras/ping/");
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.detail || "No autorizado / Error");
      }

      setPing(data);
    } catch (e) {
      setPingErr(String(e));
    }
  }

  return (
    <div style={{ padding: 20, fontFamily: "Arial" }}>
      <h1>Dashboard</h1>

      <p>
        Logueado como: <b>{user?.username}</b>
      </p>
      <p>
        Roles: <b>{(user?.roles || []).join(", ") || "Sin rol"}</b>
      </p>

      <div style={{ margin: "16px 0", display: "flex", gap: 10, flexWrap: "wrap" }}>
        <Link to="/">Inicio</Link>

        {(isCompras || isAdmin) && (
          <Link to="/compras">Módulo Compras</Link>
        )}

        {isAdmin && <Link to="/admin-compras">Admin Compras</Link>}


        {isAdmin && (
          <Link to="/admin">Administración</Link>
        )}
      </div>

      <hr style={{ margin: "16px 0" }} />

      <h2>Pruebas</h2>
      <button onClick={probarPing}>
        Probar ping COMPRAS (backend)
      </button>

      {pingErr && <p style={{ color: "red" }}>Error: {pingErr}</p>}
      {ping && <pre>{JSON.stringify(ping, null, 2)}</pre>}

      <hr style={{ margin: "16px 0" }} />

      <h2>Usuario</h2>
      <pre>{JSON.stringify(user, null, 2)}</pre>

      <button onClick={handleLogout}>Cerrar sesión</button>
    </div>
  );
}
