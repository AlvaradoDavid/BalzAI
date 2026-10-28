import { NavLink, Route, Routes } from "react-router-dom";
import PaginaMapa from "./paginas/PaginaMapa.jsx";
import PaginaAdmin from "./paginas/PaginaAdmin.jsx";
import PaginaSuperAdmin from "./paginas/PaginaSuperAdmin.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="cabecera">
        <NavLink to="/" className="marca">
          <span className="marca-logo">P</span> Parqueos Cuenca
        </NavLink>
        <nav aria-label="Navegación principal">
          <NavLink to="/" end>
            Mapa
          </NavLink>
          <NavLink to="/admin">Operación Parqueo</NavLink>
          <NavLink to="/superadmin">Control de la App</NavLink>
        </nav>
      </header>
      <main className="contenido">
        <Routes>
          <Route path="/" element={<PaginaMapa />} />
          <Route path="/admin" element={<PaginaAdmin />} />
          <Route path="/superadmin" element={<PaginaSuperAdmin />} />
          <Route path="*" element={<p className="aviso">Página no encontrada.</p>} />
        </Routes>
      </main>
    </div>
  );
}
