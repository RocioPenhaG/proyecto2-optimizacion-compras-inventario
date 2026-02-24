import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function LoginPage() {
  const { user, login } = useAuth();
  const nav = useNavigate();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (user) nav("/", { replace: true });
  }, [user, nav]);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    try {
      await login(username, password);
      nav("/", { replace: true });
    } catch (e) {
      setErr(e.message || "Error");
    }
  }

  return (
    <div style={{ padding: 20, maxWidth: 360, fontFamily: "Arial" }}>
      <h1>Login</h1>
      {err && <p style={{ color: "red" }}>{err}</p>}

      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: 10 }}>
          <label>Usuario</label>
          <input
            style={{ width: "100%", padding: 8 }}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>

        <div style={{ marginBottom: 10 }}>
          <label>Contraseña</label>
          <input
            style={{ width: "100%", padding: 8 }}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button style={{ padding: 10, width: "100%" }} type="submit">
          Entrar
        </button>
      </form>
    </div>
  );
}
