import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import NoAccess from "./pages/NoAccess";
import AdminPanel from "./pages/AdminPanel";
import Compras from "./pages/Compras";

import ProtectedRoute from "./ProtectedRoute";
import RequireRole from "./RequireRole";
import AdminCompras from "./pages/AdminCompras";


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin"
        element={
          <RequireRole role="Admin">
            <AdminPanel />
          </RequireRole>
        }
      />

      <Route
        path="/compras"
        element={
          <RequireRole role="Compras">
            <Compras />
          </RequireRole>
        }
      />

      <Route
        path="/admin-compras"
        element={
          <RequireRole role="Admin">
            <AdminCompras />
          </RequireRole>
        }
      />


      <Route path="/no-access" element={<NoAccess />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
