#!/usr/bin/env python3
"""
Script para gestionar migraciones de base de datos con Alembic.
"""
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from alembic.config import Config
from alembic import command
from app.core.config import settings

def get_alembic_config():
    """Obtener configuración de Alembic."""
    alembic_cfg = Config(str(root_dir / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return alembic_cfg

def create_migration(message: str):
    """Crear nueva migración."""
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, autogenerate=True, message=message)
    print(f"Migración creada: {message}")

def run_migrations():
    """Ejecutar migraciones pendientes."""
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")
    print("Migraciones ejecutadas exitosamente")

def rollback_migration():
    """Rollback de la última migración."""
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, "-1")
    print("Rollback ejecutado exitosamente")

def show_history():
    """Mostrar historial de migraciones."""
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg)

def show_current():
    """Mostrar migración actual."""
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python migrate.py create 'message'  # Crear migración")
        print("  python migrate.py upgrade            # Ejecutar migraciones")
        print("  python migrate.py downgrade          # Rollback")
        print("  python migrate.py history            # Ver historial")
        print("  python migrate.py current            # Ver actual")
        sys.exit(1)

    action = sys.argv[1]

    if action == "create":
        if len(sys.argv) < 3:
            print("Error: Se requiere un mensaje para la migración")
            sys.exit(1)
        message = sys.argv[2]
        create_migration(message)
    elif action == "upgrade":
        run_migrations()
    elif action == "downgrade":
        rollback_migration()
    elif action == "history":
        show_history()
    elif action == "current":
        show_current()
    else:
        print(f"Acción desconocida: {action}")
        sys.exit(1)