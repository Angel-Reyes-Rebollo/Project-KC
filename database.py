"""
database.py — Capa de persistencia SQLite para el bot de Discord.

Reemplaza el sistema de data.json con una base de datos SQLite.
Ventajas sobre JSON:
  - Escrituras atómicas por fila (no reescribe todo el archivo)
  - Inventario normalizado: solo guarda card_id + quantity
  - Cooldowns persistentes: sobreviven reinicios del bot
  - Operaciones O(1) por índice en lugar de O(n) sobre listas
  - El archivo .db se puede hacer backup igual que el .json

Uso:
    from database import db
    db.init()  # llamar una vez al iniciar el bot

    db.get_balance(user_id)
    db.add_balance(user_id, amount)
    db.get_inventory(user_id)          -> list[dict]  (objetos de carta completos, hidratados desde el catálogo)
    db.add_card(user_id, card_id)
    db.remove_card(user_id, card_id)   -> bool
    db.get_cooldown(user_id, command)  -> float (timestamp, 0 si no existe)
    db.set_cooldown(user_id, command, timestamp)
    db.get_rob_penalty(user_id)        -> float (timestamp fin de penalización)
    db.set_rob_penalty(user_id, end_ts)
    db.get_completed_floors(user_id)   -> list[int]
    db.add_completed_floor(user_id, floor)
"""

import json
import sqlite3
import threading
import time
from pathlib import Path


DB_FILE = "bot_data.db"

# El catálogo se pasa desde main.py al inicializar.
# Mapa: card_id -> dict con todos los datos de la carta
_card_catalog: dict[str, dict] = {}


def set_catalog(catalog: dict[str, dict]):
    """Recibe el mapa card_id→carta desde main.py."""
    global _card_catalog
    _card_catalog = catalog


class Database:
    """Wrapper thread-safe sobre SQLite con check_same_thread=False."""

    def __init__(self, db_path: str = DB_FILE):
        self._path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

    def _conn(self) -> sqlite3.Connection:
        """Retorna una conexión por hilo (thread-local)."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                self._path,
                check_same_thread=False,
                timeout=10,
                isolation_level=None,  # autocommit
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    # ------------------------------------------------------------------
    # Inicialización del esquema
    # ------------------------------------------------------------------
    def init(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS balances (
                user_id     TEXT PRIMARY KEY,
                gems        INTEGER NOT NULL DEFAULT 0
            );

            -- Inventario normalizado: una fila por carta por usuario.
            -- Permite duplicados (varias copias) con quantity > 1.
            CREATE TABLE IF NOT EXISTS inventory (
                user_id     TEXT NOT NULL,
                card_id     TEXT NOT NULL,
                quantity    INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, card_id)
            );

            -- Cooldowns de comandos. command es el nombre del comando (!gacha, !trabajar, etc.)
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id     TEXT NOT NULL,
                command     TEXT NOT NULL,
                last_used   REAL NOT NULL,
                PRIMARY KEY (user_id, command)
            );

            -- Penalizaciones del rob
            CREATE TABLE IF NOT EXISTS rob_penalties (
                user_id     TEXT PRIMARY KEY,
                penalty_end REAL NOT NULL
            );

            -- Pisos completados de la torre
            CREATE TABLE IF NOT EXISTS completed_floors (
                user_id     TEXT NOT NULL,
                floor       INTEGER NOT NULL,
                PRIMARY KEY (user_id, floor)
            );
        """)
        print("✅ Base de datos SQLite inicializada correctamente.")

    # ------------------------------------------------------------------
    # Migración desde data.json (ejecutar una sola vez)
    # ------------------------------------------------------------------
    def migrate_from_json(self, json_path: str = "data.json"):
        """
        Migra datos del data.json antiguo a SQLite.
        Ejecutar una única vez, luego puedes borrar data.json o renombrarlo.
        """
        path = Path(json_path)
        if not path.exists():
            print(f"⚠️  No se encontró {json_path}, no hay nada que migrar.")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        conn = self._conn()
        migrated_users = 0
        migrated_cards = 0
        skipped_cards = 0

        # Balances
        for uid, gems in data.get("balances", {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO balances (user_id, gems) VALUES (?, ?)",
                (uid, int(gems)),
            )

        # Inventarios: el JSON antiguo guarda el objeto completo de cada carta.
        # Aquí solo guardamos el card_id y la cantidad.
        for uid, cards in data.get("inventories", {}).items():
            migrated_users += 1
            # Contar duplicados
            count: dict[str, int] = {}
            for card in cards:
                cid = card.get("id")
                if cid:
                    count[cid] = count.get(cid, 0) + 1
                else:
                    skipped_cards += 1

            for cid, qty in count.items():
                conn.execute(
                    """INSERT INTO inventory (user_id, card_id, quantity)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity""",
                    (uid, cid, qty),
                )
                migrated_cards += 1

        # Penalizaciones de rob
        for uid, end_ts in data.get("rob_penalties", {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO rob_penalties (user_id, penalty_end) VALUES (?, ?)",
                (uid, float(end_ts)),
            )

        # Pisos completados
        for uid, floors in data.get("completed_floors", {}).items():
            for floor in floors:
                conn.execute(
                    "INSERT OR IGNORE INTO completed_floors (user_id, floor) VALUES (?, ?)",
                    (uid, int(floor)),
                )

        print(
            f"✅ Migración completada: {migrated_users} usuarios, "
            f"{migrated_cards} tipos de carta migrados, {skipped_cards} cartas sin ID ignoradas."
        )
        print("💡 Puedes renombrar data.json a data.json.bak y eliminar el código de migración.")

    # ------------------------------------------------------------------
    # Balances / Gemas
    # ------------------------------------------------------------------
    def get_balance(self, user_id) -> int:
        uid = str(user_id)
        row = self._conn().execute(
            "SELECT gems FROM balances WHERE user_id = ?", (uid,)
        ).fetchone()
        return row[0] if row else 0

    def add_balance(self, user_id, amount: int) -> int:
        """Suma `amount` al balance (puede ser negativo). Retorna el nuevo balance."""
        uid = str(user_id)
        conn = self._conn()
        conn.execute(
            """INSERT INTO balances (user_id, gems) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET gems = gems + excluded.gems""",
            (uid, amount),
        )
        return self.get_balance(uid)

    def set_balance(self, user_id, amount: int):
        uid = str(user_id)
        self._conn().execute(
            "INSERT OR REPLACE INTO balances (user_id, gems) VALUES (?, ?)",
            (uid, max(0, amount)),
        )

    # ------------------------------------------------------------------
    # Inventario
    # ------------------------------------------------------------------
    def _hydrate(self, card_id: str, quantity: int) -> list[dict]:
        """
        Dado un card_id y quantity, devuelve `quantity` copias del dict de la carta.
        Si la carta no está en el catálogo, devuelve un placeholder.
        """
        card = _card_catalog.get(card_id)
        if card is None:
            # Carta no encontrada en catálogo (carta eliminada del catálogo pero
            # aún en inventario de alguien)
            card = {
                "id": card_id,
                "nombre": f"[Carta desconocida: {card_id}]",
                "rareza": "N",
                "valor": 0,
                "stock": "Unlimited",
                "max_per_user": 1,
                "imagen": "images/placeholder.png",
                "descripcion": "Esta carta ya no existe en el catálogo.",
                "stats": {},
            }
        return [card.copy() for _ in range(quantity)]

    def get_inventory(self, user_id) -> list[dict]:
        """
        Retorna la lista completa de cartas del usuario (con duplicados si tiene
        quantity > 1), igual que antes — compatible con el resto del código.
        """
        uid = str(user_id)
        rows = self._conn().execute(
            "SELECT card_id, quantity FROM inventory WHERE user_id = ? ORDER BY card_id",
            (uid,),
        ).fetchall()
        result = []
        for card_id, qty in rows:
            result.extend(self._hydrate(card_id, qty))
        return result

    def get_inventory_summary(self, user_id) -> dict[str, int]:
        """Retorna {card_id: quantity} sin hidratar. Útil para consultas rápidas."""
        uid = str(user_id)
        rows = self._conn().execute(
            "SELECT card_id, quantity FROM inventory WHERE user_id = ?", (uid,)
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def add_card(self, user_id, card_id: str, quantity: int = 1):
        """Añade una carta al inventario del usuario."""
        uid = str(user_id)
        self._conn().execute(
            """INSERT INTO inventory (user_id, card_id, quantity)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity""",
            (uid, card_id, quantity),
        )

    def remove_card(self, user_id, card_id: str, quantity: int = 1) -> bool:
        """
        Elimina `quantity` copias de una carta del inventario.
        Retorna True si se pudo eliminar, False si no tenía suficientes copias.
        """
        uid = str(user_id)
        conn = self._conn()
        row = conn.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND card_id = ?",
            (uid, card_id),
        ).fetchone()
        if not row or row[0] < quantity:
            return False
        new_qty = row[0] - quantity
        if new_qty == 0:
            conn.execute(
                "DELETE FROM inventory WHERE user_id = ? AND card_id = ?",
                (uid, card_id),
            )
        else:
            conn.execute(
                "UPDATE inventory SET quantity = ? WHERE user_id = ? AND card_id = ?",
                (new_qty, uid, card_id),
            )
        return True

    def has_card(self, user_id, card_id: str) -> bool:
        uid = str(user_id)
        row = self._conn().execute(
            "SELECT 1 FROM inventory WHERE user_id = ? AND card_id = ? AND quantity > 0",
            (uid, card_id),
        ).fetchone()
        return row is not None

    def clear_inventory(self, user_id):
        self._conn().execute(
            "DELETE FROM inventory WHERE user_id = ?", (str(user_id),)
        )

    # ------------------------------------------------------------------
    # Cooldowns
    # ------------------------------------------------------------------
    def get_cooldown(self, user_id, command: str) -> float:
        """Retorna el timestamp del último uso del comando. 0 si nunca lo usó."""
        uid = str(user_id)
        row = self._conn().execute(
            "SELECT last_used FROM cooldowns WHERE user_id = ? AND command = ?",
            (uid, command),
        ).fetchone()
        return row[0] if row else 0.0

    def set_cooldown(self, user_id, command: str, timestamp: float = None):
        """Registra el momento de uso de un comando (default: ahora)."""
        uid = str(user_id)
        ts = timestamp if timestamp is not None else time.time()
        self._conn().execute(
            """INSERT OR REPLACE INTO cooldowns (user_id, command, last_used)
               VALUES (?, ?, ?)""",
            (uid, command, ts),
        )

    def check_cooldown(self, user_id, command: str, duration: float) -> float:
        """
        Verifica si el cooldown expiró.
        Retorna 0 si puede usar el comando.
        Retorna el tiempo restante en segundos si aún está en cooldown.
        """
        last = self.get_cooldown(user_id, command)
        elapsed = time.time() - last
        remaining = duration - elapsed
        return max(0.0, remaining)

    # ------------------------------------------------------------------
    # Penalizaciones de Robo
    # ------------------------------------------------------------------
    def has_rob_penalty(self, user_id) -> bool:
        uid = str(user_id)
        row = self._conn().execute(
            "SELECT penalty_end FROM rob_penalties WHERE user_id = ?", (uid,)
        ).fetchone()
        if not row:
            return False
        return row[0] > time.time()

    def get_rob_penalty_end(self, user_id) -> float:
        uid = str(user_id)
        row = self._conn().execute(
            "SELECT penalty_end FROM rob_penalties WHERE user_id = ?", (uid,)
        ).fetchone()
        return row[0] if row else 0.0

    def set_rob_penalty(self, user_id, end_timestamp: float):
        uid = str(user_id)
        self._conn().execute(
            "INSERT OR REPLACE INTO rob_penalties (user_id, penalty_end) VALUES (?, ?)",
            (uid, end_timestamp),
        )

    # ------------------------------------------------------------------
    # Pisos completados
    # ------------------------------------------------------------------
    def get_completed_floors(self, user_id) -> list[int]:
        uid = str(user_id)
        rows = self._conn().execute(
            "SELECT floor FROM completed_floors WHERE user_id = ? ORDER BY floor",
            (uid,),
        ).fetchall()
        return [r[0] for r in rows]

    def add_completed_floor(self, user_id, floor: int):
        uid = str(user_id)
        self._conn().execute(
            "INSERT OR IGNORE INTO completed_floors (user_id, floor) VALUES (?, ?)",
            (uid, floor),
        )

    # ------------------------------------------------------------------
    # Admin / Utilidades
    # ------------------------------------------------------------------
    def reset_user(self, user_id):
        """Elimina todos los datos de un usuario (admin reset)."""
        uid = str(user_id)
        conn = self._conn()
        conn.execute("DELETE FROM balances WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM inventory WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM cooldowns WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM rob_penalties WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM completed_floors WHERE user_id = ?", (uid,))

    def get_top_balances(self, limit: int = 10) -> list[tuple[str, int]]:
        """Retorna los top N usuarios por balance [(user_id, gems), ...]"""
        rows = self._conn().execute(
            "SELECT user_id, gems FROM balances ORDER BY gems DESC LIMIT ?", (limit,)
        ).fetchall()
        return rows

    def get_top_inventories(self, limit: int = 10) -> list[tuple[str, int]]:
        """Retorna los top N usuarios por cantidad total de cartas [(user_id, total), ...]"""
        rows = self._conn().execute(
            """SELECT user_id, SUM(quantity) as total
               FROM inventory GROUP BY user_id
               ORDER BY total DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return rows


# Instancia global — importar esto desde main.py
db = Database()
