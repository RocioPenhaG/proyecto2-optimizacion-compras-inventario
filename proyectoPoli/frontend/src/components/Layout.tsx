import { Outlet, NavLink } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center h-14">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-blue-600">Segupak</h1>
            <nav className="hidden md:flex gap-4">
              <NavLink 
                to="/" 
                data-testid="nav-inicio"
                className={({ isActive }) => `text-sm font-medium ${isActive ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}`}
                end
              >
                Inicio
              </NavLink>
              <NavLink 
                to="/products" 
                data-testid="nav-productos"
                className={({ isActive }) => `text-sm font-medium ${isActive ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Productos
              </NavLink>
              {user?.role !== "FUNCIONARIO" && (
                <NavLink
                  to="/inventory"
                  data-testid="nav-inventario"
                  className={({ isActive }) =>
                    `text-sm font-medium ${isActive ? "text-blue-600" : "text-gray-600 hover:text-gray-900"}`
                  }
                >
                  Inventario
                </NavLink>
              )}
              <NavLink 
                to="/solicitudes" 
                data-testid="nav-solicitudes"
                className={({ isActive }) => `text-sm font-medium ${isActive ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Solicitudes
              </NavLink>
              {(user?.role === "COMPRAS" || user?.role === "GERENCIA" || user?.role === "CONTABLE" || user?.role === "ADMINISTRADOR") && (
                <>
                  <NavLink
                    to="/dashboard"
                    data-testid="nav-dashboard"
                    className={({ isActive }) => `text-sm font-medium ${isActive ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}`}
                  >
                    Dashboard
                  </NavLink>
                </>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">
              {user?.first_name || user?.username} ({user?.role})
            </span>
            <button
              type="button"
              onClick={logout}
              data-testid="btn-logout"
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full min-w-0 flex-grow">
        <Outlet />
      </main>
    </div>
  );
}
