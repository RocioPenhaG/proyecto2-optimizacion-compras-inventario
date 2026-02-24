import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../auth";

function fmtDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString(); // usa tu formato local
}

export default function Compras() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [titulo, setTitulo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [loading, setLoading] = useState(false);

  // selección para administrar items
  const [selected, setSelected] = useState(null); // solicitud seleccionada
  const [itemsList, setItemsList] = useState([]);
  const [itemDesc, setItemDesc] = useState("");
  const [itemCant, setItemCant] = useState("1");
  const [itemPrecio, setItemPrecio] = useState("0");

  const selectedId = selected?.id;

  const [flujo, setFlujo] = useState(null);
  const [me, setMe] = useState(null);
  const isAdmin = me?.roles?.includes("Admin") || me?.roles?.includes("ADMIN");
  const isCompras = me?.roles?.includes("Compras");


  async function cargarFlujo() {
    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch("/api/compras/flujo/");
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al cargar flujo");
      setFlujo(data);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function cargarMe() {
    try {
      const res = await apiFetch("/api/me/");
      const data = await res.json();
      if (res.ok) setMe(data);
    } catch {}
  }



  async function cargar() {
    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch("/api/compras/solicitudes/");
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al listar");
      setItems(data);

      // si tengo una seleccionada, refrescar referencia
      if (selectedId) {
        const fresh = data.find((x) => x.id === selectedId) || null;
        setSelected(fresh);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function crear(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch("/api/compras/solicitudes/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ titulo, descripcion }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al crear");
      setTitulo("");
      setDescripcion("");
      await cargar();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function aprobar(id) {
  setErr("");
  setLoading(true);
  try {
    const res = await apiFetch(`/api/compras/solicitudes/${id}/aprobar/`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Error al aprobar");
    await cargar();
  } catch (e) {
    setErr(String(e));
  } finally {
    setLoading(false);
  }
}

  async function rechazar(id) {
    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${id}/rechazar/`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al rechazar");
      await cargar();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function enviar(id) {
    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${id}/enviar/`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al enviar");
      await cargar();
      // refrescar items panel si está abierto
      if (selectedId === id) await cargarItems(id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function cargarItems(id) {
    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${id}/items/`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al listar items");
      setItemsList(data);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function agregarItem(e) {
    e.preventDefault();
    if (!selectedId) return;

    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${selectedId}/items/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          descripcion: itemDesc,
          cantidad: itemCant,
          precio_estimado: itemPrecio,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Error al agregar item");

      setItemDesc("");
      setItemCant("1");
      setItemPrecio("0");

      await cargarItems(selectedId);
      await cargar(); // para refrescar total_estimado/items si lo estás mostrando
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function borrarItem(itemId) {
    if (!selectedId) return;

    setErr("");
    setLoading(true);
    try {
      const res = await apiFetch(`/api/compras/solicitudes/${selectedId}/items/${itemId}/`, {
        method: "DELETE",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Error al borrar item");

      await cargarItems(selectedId);
      await cargar();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  function seleccionarSolicitud(s) {
    setSelected(s);
    setItemsList([]);
    if (s?.id) cargarItems(s.id);
  }

  const selectedEstado = selected?.estado;

  const totalItems = useMemo(() => {
    let t = 0;
    for (const it of itemsList) {
      const c = Number(it.cantidad || 0);
      const p = Number(it.precio_estimado || 0);
      t += c * p;
    }
    return t;
  }, [itemsList]);

  useEffect(() => {
    cargar();
    cargarMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ padding: 20, fontFamily: "Arial", maxWidth: 1100 }}>
      <h1>Módulo Compras</h1>

      <div style={{ margin: "10px 0" }}>
        <button onClick={cargarFlujo} disabled={loading}>
          Ver flujo de estados
        </button>
      </div>

      {flujo && (
        <div style={{ border: "1px solid #ccc", padding: 12, marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Flujo de estados</h3>
          {Object.entries(flujo.transiciones || {}).map(([estado, next]) => (
            <div key={estado}>
              <b>{estado}</b> {"→"} {next.length ? next.join(" / ") : "(sin transiciones)"}
            </div>
          ))}
        </div>
      )}


      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
        {/* Crear solicitud */}
        <div style={{ minWidth: 320, flex: 1 }}>
          <h2>Nueva solicitud</h2>
          <form onSubmit={crear}>
            <div style={{ marginBottom: 10 }}>
              <label>Título</label>
              <input
                style={{ width: "100%", padding: 8 }}
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                required
              />
            </div>

            <div style={{ marginBottom: 10 }}>
              <label>Descripción</label>
              <textarea
                style={{ width: "100%", padding: 8, minHeight: 80 }}
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
              />
            </div>

            <button type="submit" disabled={loading}>Crear</button>{" "}
            <button type="button" onClick={cargar} disabled={loading}>Refrescar</button>
          </form>

          {err && <p style={{ color: "red" }}>Error: {err}</p>}
        </div>

        {/* Tabla solicitudes */}
        <div style={{ flex: 2, minWidth: 600 }}>
          <h2>Solicitudes</h2>
          {loading && <p>Cargando...</p>}

          <table border="1" cellPadding="8" style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Título</th>
                <th>Estado</th>
                <th>Solicitante</th>
                <th>Creado</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} style={{ background: selectedId === s.id ? "#f3f3f3" : "transparent" }}>
                  <td>{s.id}</td>
                  <td>{s.titulo}</td>
                  <td>{s.estado}</td>
                  <td>{s.solicitante_username}</td>
                  <td>{fmtDate(s.created_at)}</td>
                 <td style={{ whiteSpace: "nowrap" }}>
                  <button onClick={() => seleccionarSolicitud(s)} disabled={loading}>
                    Items
                  </button>{" "}

                  {/* COMPRAS → enviar */}
                  {isCompras && s.estado === "BORRADOR" && (
                    <button onClick={() => enviar(s.id)} disabled={loading}>
                      Enviar
                    </button>
                  )}

                  {/* ADMIN → aprobar / rechazar */}
                  {isAdmin && s.estado === "ENVIADA" && (
                    <>
                      <button
                        onClick={() => aprobar(s.id)}
                        disabled={loading}
                        style={{ marginLeft: 4 }}
                      >
                        Aprobar
                      </button>
                      <button
                        onClick={() => rechazar(s.id)}
                        disabled={loading}
                        style={{ marginLeft: 4 }}
                      >
                        Rechazar
                      </button>
                    </>
                  )}
                </td>

              </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan="6">Sin registros</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Panel Items */}
      {selected && (
        <div style={{ marginTop: 20 }}>
          <h2>
            Items de Solicitud #{selected.id} — {selected.titulo} ({selected.estado})
          </h2>

          {selectedEstado !== "BORRADOR" && (
            <p style={{ marginTop: 0 }}>
              Esta solicitud está <b>{selectedEstado}</b>. No se pueden agregar/borrar items.
            </p>
          )}

          {/* Form agregar item */}
          <form onSubmit={agregarItem} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}>
            <div style={{ flex: 2, minWidth: 220 }}>
              <label>Descripción</label>
              <input
                style={{ width: "100%", padding: 8 }}
                value={itemDesc}
                onChange={(e) => setItemDesc(e.target.value)}
                required
                disabled={loading || selectedEstado !== "BORRADOR"}
              />
            </div>

            <div style={{ width: 140 }}>
              <label>Cantidad</label>
              <input
                style={{ width: "100%", padding: 8 }}
                value={itemCant}
                onChange={(e) => setItemCant(e.target.value)}
                required
                disabled={loading || selectedEstado !== "BORRADOR"}
              />
            </div>

            <div style={{ width: 160 }}>
              <label>Precio estimado</label>
              <input
                style={{ width: "100%", padding: 8 }}
                value={itemPrecio}
                onChange={(e) => setItemPrecio(e.target.value)}
                required
                disabled={loading || selectedEstado !== "BORRADOR"}
              />
            </div>

            <button type="submit" disabled={loading || selectedEstado !== "BORRADOR"}>
              Agregar item
            </button>

            <button type="button" onClick={() => cargarItems(selected.id)} disabled={loading}>
              Refrescar items
            </button>
          </form>

          {/* Tabla items */}
          <div style={{ marginTop: 12 }}>
            <table border="1" cellPadding="8" style={{ borderCollapse: "collapse", width: "100%" }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Descripción</th>
                  <th>Cantidad</th>
                  <th>Precio</th>
                  <th>Subtotal</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {itemsList.map((it) => {
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
                      <td>
                        <button
                          onClick={() => borrarItem(it.id)}
                          disabled={loading || selectedEstado !== "BORRADOR"}
                        >
                          Borrar
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {itemsList.length === 0 && (
                  <tr>
                    <td colSpan="6">Sin items</td>
                  </tr>
                )}
              </tbody>
            </table>

            <p style={{ marginTop: 10 }}>
              <b>Total estimado:</b> {totalItems}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
