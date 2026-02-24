import { Link } from "react-router-dom";

export default function NoAccess() {
  return (
    <div style={{ padding: 20, fontFamily: "Arial" }}>
      <h1>Sin acceso</h1>
      <p>No tenés permisos para ver esta página.</p>
      <Link to="/">Volver</Link>
    </div>
  );
}
