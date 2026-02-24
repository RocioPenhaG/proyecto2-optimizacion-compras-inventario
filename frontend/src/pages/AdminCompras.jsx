import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { apiFetch } from "../auth";
import { useAuth } from "../AuthContext";

function fmtDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

export default function AdminCompras() {
  const { user, loading } = useAuth();

  const roles = (user?.roles || []).map((r) => String(r).toLowerCase());
  const isAdmin = user?.is_staff === true || roles.includes("admin");

  const [estadoFiltro, setEstadoFiltro] = useState("ENVIADA");
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [expandedId, setExpandedId] = useState(null);

  async function cargar(estado = estadoFiltro) {
    setErr("");
    setBusy(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/?estado=${encodeURIComponent(estado)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al listar");
      setRows(data);

      // si el expandido ya no está en la lista, cerrar
      if (expandedId && !data.some((x) => x.id === expandedId)) {
        setExpandedId(null);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function aprobar(id) {
    setErr("");
    setBusy(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${id}/aprobar/`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al aprobar");
      await cargar(estadoFiltro);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function rechazar(id) {
    setErr("");
    setBusy(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${id}/rechazar/`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al rechazar");
      await cargar(estadoFiltro);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  function toggleExpand(id) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  useEffect(() => {
    if (isAdmin) cargar("ENVIADA");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) cargar(estadoFiltro);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estadoFiltro]);

  if (loading) return <div style={{ padding: 20 }}>Cargando...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/no-access" replace />;

  return (
    <div style={{ padding: 20, fontFamily: "Arial", maxWidth: 1150 }}>
      <h1>ADMIN · Solicitudes de Compras</h1>

      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <label>
          Estado:&nbsp;
          <select
            value={estadoFiltro}
            onChange={(e) => setEstadoFiltro(e.target.value)}
            disabled={busy}
          >
            <option value="ENVIADA">ENVIADA</option>
            <option value="APROBADA">APROBADA</option>
            <option value="RECHAZADA">RECHAZADA</option>
            <option value="BORRADOR">BORRADOR</option>
          </select>
        </label>

        <button onClick={() => cargar(estadoFiltro)} disabled={busy}>
          Refrescar
        </button>

        {busy && <span>Cargando...</span>}
      </div>

      {err && <p style={{ color: "red" }}>Error: {err}</p>}

      <table
        border="1"
        cellPadding="8"
        style={{ borderCollapse: "collapse", width: "100%", marginTop: 12 }}
      >
        <thead>
          <tr>
            <th>ID</th>
            <th>Solicitante</th>
            <th>Creado</th>
            <th>Items</th>
            <th>Total estimado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const isExpanded = expandedId === s.id;
            const items = s.items || [];
            const puedeAccionar = s.estado === "ENVIADA"; // solo ahí aprueba/rechaza

            return (
              <tbody key={s.id}>
                <tr style={{ background: isExpanded ? "#f3f3f3" : "transparent" }}>
                  <td>{s.id}</td>
                  <td>{s.solicitante_username}</td>
                  <td>{fmtDate(s.created_at)}</td>
                  <td>{items.length}</td>
                  <td>{s.total_estimado ?? 0}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button onClick={() => toggleExpand(s.id)} disabled={busy}>
                      {isExpanded ? "Ocultar" : "Ver"} detalle
                    </button>

                    {puedeAccionar && (
                      <>
                        {" "}
                        <button onClick={() => aprobar(s.id)} disabled={busy}>
                          Aprobar
                        </button>{" "}
                        <button onClick={() => rechazar(s.id)} disabled={busy}>
                          Rechazar
                        </button>
                      </>
                    )}
                  </td>
                </tr>

                {isExpanded && (
                  <tr>
                    <td colSpan="6">
                      <div style={{ padding: 8 }}>
                        <h3 style={{ margin: "0 0 8px 0" }}>
                          Detalle de Solicitud #{s.id} ({s.estado})
                        </h3>

                        <div style={{ marginBottom: 10 }}>
                          <div><b>Solicitante:</b> {s.solicitante_username}</div>
                          <div><b>Creado:</b> {fmtDate(s.created_at)}</div>

                          {s.estado === "APROBADA" && (
                            <div style={{ marginTop: 6 }}>
                              <div><b>Aprobado por:</b> {s.aprobado_por_username || "-"}</div>
                              <div><b>Aprobado el:</b> {fmtDate(s.aprobado_at)}</div>
                            </div>
                          )}

                          {s.estado === "RECHAZADA" && (
                            <div style={{ marginTop: 6 }}>
                              <div><b>Rechazado por:</b> {s.rechazado_por_username || "-"}</div>
                              <div><b>Rechazado el:</b> {fmtDate(s.rechazado_at)}</div>
                            </div>
                          )}
                        </div>


                        {items.length === 0 ? (
                          <p>Sin items.</p>
                        ) : (
                          <table
                            border="1"
                            cellPadding="6"
                            style={{ borderCollapse: "collapse", width: "100%" }}
                          >
                            <thead>
                              <tr>
                                <th>ID</th>
                                <th>Descripción</th>
                                <th>Cantidad</th>
                                <th>Precio</th>
                                <th>Subtotal</th>
                              </tr>
                            </thead>
                            <tbody>
                              {items.map((it) => {
                                const c = Number(it.cantidad || 0);
                                const p = Number(it.precio_estimado || 0);
                                const sub = c * p;
                                return (
                                  <tr key={it.id}>
                                    <td>{it.id}</td>
                                    <td>{it.descripcion}</td>
                                    <td>{it.cantidad}</td>
                                    <td>{it.precio_estimado}</td>
                                    <td>{sub}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        )}

                        <p style={{ marginTop: 10 }}>
                          <b>Total estimado:</b> {s.total_estimado ?? 0}
                        </p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            );
          })}

          {rows.length === 0 && (
            <tr>
              <td colSpan="6">No hay solicitudes en estado {estadoFiltro}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
