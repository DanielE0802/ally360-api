
# Ally360 – Backend ERP

Este es el backend del sistema ERP **Ally360**, desarrollado en **FastAPI + MySQL**, orientado a pequeñas y medianas empresas colombianas. El sistema permite gestionar inventario, ventas, compras, facturación electrónica y puntos de venta.

---

## ⚙️ Tecnologías utilizadas

- Python 3.11+
- FastAPI
- MySQL
- SQLAlchemy
- JWT (python-jose)
- Docker & Docker Compose

---

## 🧪 Estructura del proyecto

```
app/
├── api/              # Rutas organizadas por versión y entidad
├── core/             # Configuraciones y utilidades centrales
├── models/           # Modelos SQLAlchemy
├── schemas/          # Esquemas Pydantic
├── services/         # Lógica de negocio
├── dependencies/     # Dependencias compartidas (JWT, DB)
└── main.py           # Entrada principal de la app
```

---

## 🚀 Ejecución local con Docker

1. Copia el archivo de entorno:

```bash
cp .env.example .env
```

2. Levanta el proyecto:

```bash
docker-compose up --build
```

3. Accede a la API:
- Documentación Swagger: http://localhost:8000/docs
- Documentación ReDoc: http://localhost:8000/redoc

---

## 🔐 Autenticación

La autenticación se realiza con **JWT**. Los endpoints protegidos requieren el envío del token en el header:

```
Authorization: Bearer <token>
```

---

## 📦 Módulos actuales del MVP

- Gestión de empresas y usuarios
- Inventario y productos configurables
- Puntos de venta (POS)
- Compras y proveedores
- Ventas, pagos y facturación (base)
- Soporte multitenant con roles

---

## 📄 Licencia

Proyecto privado bajo desarrollo. Todos los derechos reservados © Ally360.
