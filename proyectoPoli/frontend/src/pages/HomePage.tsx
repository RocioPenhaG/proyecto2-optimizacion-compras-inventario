import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useAccessToken } from "@/contexts/AuthContext";

export function HomePage() {
  const { user } = useAuth();
  const token = useAccessToken();
  const [stockCritico, setStockCritico] = useState<number | null>(null);

  const isFuncionario = user?.role === "FUNCIONARIO";

  useEffect(() => {
    if (!token || isFuncionario) return;
    fetch("/api/products/estadisticas/", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setStockCritico(data.productos_stock_critico))
      .catch(() => setStockCritico(0));
  }, [token, isFuncionario]);

  const canSeeDashboard = ["COMPRAS", "GERENCIA", "CONTABLE", "ADMINISTRADOR"].includes(user?.role ?? "");

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold text-gray-800">
        Bienvenido, {user?.first_name || user?.username}
      </h2>

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
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-gray-300">
            <h3 className="text-sm font-medium text-gray-500 uppercase">Catálogo</h3>
            <p className="mt-2 text-gray-600 text-sm">Consulte insumos disponibles para sus solicitudes.</p>
            <Link to="/products" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              Ver catálogo de productos →
            </Link>
          </div>
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
