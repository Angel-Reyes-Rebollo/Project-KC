"""
migrate.py — Script de migración de data.json a SQLite.

Ejecuta este script UNA SOLA VEZ antes de iniciar el bot con el nuevo sistema:
    python migrate.py

Puedes ejecutarlo con el bot apagado. No modifica data.json original.
Crea bot_data.db en el mismo directorio.
"""

import json
import sys
from pathlib import Path


def run():
    try:
        from database import db, set_catalog
    except ImportError:
        print("❌ No se encontró database.py. Asegúrate de que esté en el mismo directorio.")
        sys.exit(1)

    # Cargar catálogo para hidratar correctamente
    catalog_path = Path("catalogo.json")
    if catalog_path.exists():
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)
        catalog_by_id = {card["id"]: card for card in catalog_data.get("cards", [])}
        set_catalog(catalog_by_id)
        print(f"📚 Catálogo cargado: {len(catalog_by_id)} cartas")
    else:
        print("⚠️  catalogo.json no encontrado. Continuando sin catálogo.")

    db.init()
    db.migrate_from_json("data.json")

    print("\n✅ ¡Migración lista! Ahora puedes iniciar el bot con el nuevo sistema.")
    print("   El archivo bot_data.db contiene todos tus datos.")
    print("   Puedes hacer backup de bot_data.db igual que hacías con data.json.")


if __name__ == "__main__":
    run()
