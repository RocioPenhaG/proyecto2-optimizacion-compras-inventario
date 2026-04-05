import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { LoginPage } from "@/pages/LoginPage";
import { HomePage } from "@/pages/HomePage";
import { ProductsPage } from "@/pages/ProductsPage";
import { InventoryPage } from "@/pages/InventoryPage";
import { SolicitudesPage } from "@/pages/SolicitudesPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { Layout } from "@/components/Layout";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">Cargando…</p>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function InventarioSoloNoFuncionario({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user?.role === "FUNCIONARIO") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route
          path="inventory"
          element={
            <InventarioSoloNoFuncionario>
              <InventoryPage />
            </InventarioSoloNoFuncionario>
          }
        />
        <Route path="solicitudes" element={<SolicitudesPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
