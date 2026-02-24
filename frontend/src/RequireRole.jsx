import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function RequireRole({ role, children }) {
  const { user, loading } = useAuth();

  if (loading) return <div style={{ padding: 20 }}>Cargando...</div>;
  if (!user) return <Navigate to="/login" replace />;

  const roles = (user.roles || []).map((r) => String(r).toLowerCase());
  const required = String(role).toLowerCase();

  // ADMIN: si es staff, o si tiene un grupo "admin" (cualquier may/min)
  const isAdmin = user.is_staff === true || roles.includes("admin");

  const allowed = roles.includes(required) || isAdmin;

  if (!allowed) return <Navigate to="/no-access" replace />;

  return children;
}
