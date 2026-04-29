import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth, useAccessToken } from "@/contexts/AuthContext";

/** Misma URL que SolicitudesPage (barra final evita 301 y pérdida de Authorization). */
const API_SOLICITUDES = "/api/purchases/solicitudes/";

/** Estados con flujo cerrado (no cuentan como “en progreso”). */
const ESTADOS_RESUELTOS = new Set(["FINALIZADO", "COMPRA_RECHAZADA"]);

interface ComprasResumenPedidos {
  total: number;
  enProgreso: number;
  resueltos: number;
}

function calcularResumenSolicitudes(items: { estado: string }[]): ComprasResumenPedidos {
  let enProgreso = 0;
  let resueltos = 0;
  for (const s of items) {
    if (ESTADOS_RESUELTOS.has(s.estado)) resueltos += 1;
    else enProgreso += 1;
  }
  return { total: items.length, enProgreso, resueltos };
}

export function HomePage() {
  const { user } = useAuth();
  const token = useAccessToken();
  const [stockCritico, setStockCritico] = useState<number | null>(null);
  const [comprasResumen, setComprasResumen] = useState<ComprasResumenPedidos | null>(null);
  const [comprasResumenFallo, setComprasResumenFallo] = useState(false);

  const isFuncionario = user?.role === "FUNCIONARIO";
  const isCompras = user?.role === "COMPRAS";

  useEffect(() => {
    if (!token || isFuncionario) return;
    fetch("/api/products/estadisticas/", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setStockCritico(data.productos_stock_critico))
      .catch(() => setStockCritico(0));
  }, [token, isFuncionario]);

  useEffect(() => {
    if (!token || !isCompras) {
      setComprasResumen(null);
      setComprasResumenFallo(false);
      return;
    }
    setComprasResumen(null);
    setComprasResumenFallo(false);
    fetch(API_SOLICITUDES, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        const list = Array.isArray(data) ? data : data.results ?? [];
        setComprasResumen(calcularResumenSolicitudes(list));
      })
      .catch(() => {
        setComprasResumenFallo(true);
        setComprasResumen(null);
      });
  }, [token, isCompras]);

  const canSeeDashboard = ["COMPRAS", "GERENCIA", "CONTABLE", "ADMINISTRADOR"].includes(user?.role ?? "");

  const mostrarNumeroCompras = (valor: keyof ComprasResumenPedidos) => {
    if (comprasResumenFallo) return "—";
    if (comprasResumen === null) return "—";
    return comprasResumen[valor];
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold text-gray-800">
        Bienvenido, {user?.first_name || user?.username}
      </h2>

      {isCompras && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
            <h3 className="text-sm font-medium text-gray-500 uppercase">Total de pedidos</h3>
            <p className="mt-2 text-2xl font-bold text-blue-700">{mostrarNumeroCompras("total")}</p>
            <p className="mt-1 text-xs text-gray-500">Solicitudes de insumo visibles para su área.</p>
            <Link to="/solicitudes" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              Ver solicitudes →
            </Link>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-amber-500">
            <h3 className="text-sm font-medium text-gray-500 uppercase">En progreso</h3>
            <p className="mt-2 text-2xl font-bold text-amber-700">{mostrarNumeroCompras("enProgreso")}</p>
            <p className="mt-1 text-xs text-gray-500">Solicitado, en revisión o compra aceptada (pendiente de cierre).</p>
            <Link to="/solicitudes" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              Ver solicitudes →
            </Link>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-emerald-600">
            <h3 className="text-sm font-medium text-gray-500 uppercase">Resueltos</h3>
            <p className="mt-2 text-2xl font-bold text-emerald-700">{mostrarNumeroCompras("resueltos")}</p>
            <p className="mt-1 text-xs text-gray-500">Finalizadas o compra rechazada.</p>
            <Link to="/solicitudes" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              Ver solicitudes →
            </Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {!isFuncionario && (
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500">
            <h3 className="text-sm font-medium text-gray-500 uppercase">Productos con stock crítico</h3>
            <p className="mt-2 text-2xl font-bold text-red-700">
              {stockCritico !== null ? stockCritico : "—"}
            </p>
            <Link to="/products" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              Ver catálogo de productos →
            </Link>
          </div>
        )}
        {isFuncionario && (
          <>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-gray-300">
              <h3 className="text-sm font-medium text-gray-500 uppercase">Catálogo</h3>
              <p className="mt-2 text-gray-600 text-sm">Consulte insumos disponibles para sus solicitudes.</p>
              <Link to="/products" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
                Ver catálogo de productos →
              </Link>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-gray-300">
              <h3 className="text-sm font-medium text-gray-500 uppercase">Solicitudes</h3>
              <p className="mt-2 text-gray-600 text-sm">Consulte y gestione sus solicitudes de compra.</p>
              <Link to="/solicitudes" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
                Ver solicitudes →
              </Link>
            </div>
          </>
        )}
        {canSeeDashboard && (
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
            <h3 className="text-sm font-medium text-gray-500 uppercase">Dashboard</h3>
            <p className="mt-2 text-gray-600 text-sm">Métricas de solicitudes, aprobación e insumos más solicitados.</p>
            <Link to="/dashboard" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              Ir al dashboard →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
