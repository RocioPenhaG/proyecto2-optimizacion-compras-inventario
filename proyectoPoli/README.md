# Sistema de gestión de compras e inventarios — Segupak S.A.

Proyecto TFG: plataforma web interna para optimizar el proceso de compras internas y control de inventarios.

## Requisitos

- Python 3.11+
- Node.js 18+
- Docker y Docker Compose
- Git

## Estructura

```
proyectoPol/
├── backend/     # Django + DRF
├── frontend/    # React + TypeScript + Tailwind
└── docker-compose.yml
```

## Levantar servicios (PostgreSQL y Redis)

Desde la **raíz del proyecto** (donde está `docker-compose.yml`):

docker compose up -d


## Backend (Django)

La base de datos debe estar corriendo antes levantar el servidor. Orden recomendado:

```bash
docker compose up -d db

cd backend
source venv/bin/activate

python manage.py runserver

### Usuarios de prueba por rol (Release 1)

Para probar el módulo de solicitudes de compra con distintos roles (Funcionario, Compras, Gerencia, Contable, Administrador)

Se crean estos usuarios (todos con la misma contraseña por defecto `segupak123`):

| Usuario       | Rol                 | Uso típico                          |
|---------------|---------------------|-------------------------------------|
| `funcionario` | Funcionario         | Crear y ver sus propias solicitudes |
| `compras`     | Área de Compras     | Ver todas las solicitudes, crear pedidos de insumos, cambiar estado del flujo |
| `gerencia`    | Gerencia            | Aprobar o rechazar solicitudes      |
| `contable`    | Área Contable       | Ver todas las solicitudes, crear pedidos de insumos; sin aprobar/revisar |
## Frontend (React)

```bash
cd frontend
npm install
npm run dev
```