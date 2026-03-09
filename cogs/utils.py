"""
cogs/utils.py — Funciones auxiliares y constantes compartidas entre todos los cogs.

NO es un Cog de discord.py. Es un módulo Python normal que los demás importan.
Uso: from cogs.utils import format_gems, get_rarity_emoji, COOLDOWN_GACHA, ...
"""

import time
import discord
from database import db

# ─────────────────────────────────────────
# CONSTANTES DE COOLDOWNS (segundos)
# ─────────────────────────────────────────
COOLDOWN_DIARIA          = 24 * 3600   # 24 horas
COOLDOWN_GACHA           = 4  * 3600   # 4 horas
COOLDOWN_TRABAJAR        = 4  * 3600   # 4 horas
COOLDOWN_ADIVINA         = 1  * 3600   # 1 hora
COOLDOWN_ROB             = 30 * 60     # 30 minutos
COOLDOWN_CASINO          = 1  * 3600   # 1 hora
COOLDOWN_PESCA           = 2  * 3600   # 2 horas
COOLDOWN_MINAR           = 60          # 1 minuto
COOLDOWN_ENCUENTRA_GEMA  = 2  * 3600   # 2 horas
COOLDOWN_BLACKJACK       = 15 * 60     # 15 minutos
COOLDOWN_RULETA          = 5  * 60     # 5 minutos
COOLDOWN_JEFE_VICTORIA   = 7  * 24 * 3600  # 7 días
COOLDOWN_JEFE_DERROTA    = 3  * 60     # 3 minutos

# Apuestas blackjack
APUESTA_MINIMA_BJ = 150
APUESTA_MAXIMA_BJ = 2000

# Probabilidades gacha (mutables por !modificar_rates)
rarity_probabilities = {
    "G":   0.0033,
    "SP":  0.0067,
    "UR":  0.0117,
    "SSR": 0.0680,
    "R":   0.1046,
    "N":   0.8057,
}

# ─────────────────────────────────────────
# FORMATEO
# ─────────────────────────────────────────

def format_gems(amount: int) -> str:
    return f"{amount:,} 💎"


def format_cooldown(seconds: float) -> str:
    """Convierte segundos a formato legible. Ej: 1h 30m 5s"""
    if seconds <= 0:
        return "**✅ ¡LISTO!**"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if secs:    parts.append(f"{secs}s")
    return " ".join(parts) if parts else "< 1s"


# ─────────────────────────────────────────
# RAREZA
# ─────────────────────────────────────────

RARITY_EMOJIS = {
    "E":   "🎉",
    "M":   "✨",
    "G":   "🌌",
    "F":   "🎭",
    "SP":  "🎀",
    "UR":  "💫",
    "SSR": "🔥",
    "R":   "⭐",
    "N":   "🔹",
}

RARITY_COLORS = {
    "E":   0xFFD700,
    "M":   0x9B59B6,
    "G":   0x6C5CE7,
    "F":   0x1ABC9C,
    "SP":  0xFF69B4,
    "UR":  0x3498DB,
    "SSR": 0xE74C3C,
    "R":   0xF1C40F,
    "N":   0x3498DB,
}

RARITY_ORDER = {"G": 0, "SP": 1, "UR": 2, "SSR": 3, "R": 4, "N": 5}


def get_rarity_emoji(rarity: str) -> str:
    return RARITY_EMOJIS.get(rarity, "📄")


def get_rarity_color(rarity: str) -> int:
    return RARITY_COLORS.get(rarity, 0x000000)


# ─────────────────────────────────────────
# WRAPPERS DE BASE DE DATOS
# (compatibilidad con el código que aún usa estas funciones directamente)
# ─────────────────────────────────────────

def get_inventory(user_id) -> list[dict]:
    return db.get_inventory(user_id)


def add_to_inventory(user_id, card: dict):
    """Agrega una carta al inventario. Recibe el dict completo."""
    db.add_card(user_id, card["id"])


def remove_from_inventory_by_index(user_id, index: int) -> dict | None:
    """Elimina la carta en la posición `index` del inventario y la devuelve."""
    inv = db.get_inventory(user_id)
    if 0 <= index < len(inv):
        card = inv[index]
        db.remove_card(user_id, card["id"])
        return card
    return None


def remove_card_by_id(user_id, card_id: str) -> bool:
    """Elimina una copia de la carta con ese ID. Devuelve True si se pudo."""
    return db.remove_card(user_id, card_id)


def get_balance(user_id) -> int:
    return db.get_balance(user_id)


def add_balance(user_id, amount: int) -> int:
    return db.add_balance(user_id, amount)


def has_rob_penalty(user_id) -> bool:
    return db.has_rob_penalty(user_id)


def get_rob_penalty_time(user_id) -> float:
    return db.get_rob_penalty_end(user_id)


def set_rob_penalty(user_id, end_ts: float):
    db.set_rob_penalty(user_id, end_ts)


def get_completed_floors(user_id) -> list[int]:
    return db.get_completed_floors(user_id)


def save_data():
    """No-op: SQLite guarda automáticamente. Mantenida para compatibilidad."""
    pass


# ─────────────────────────────────────────
# CHECK GLOBAL DE PAUSA
# (se registra en main.py mediante bot.add_check)
# ─────────────────────────────────────────

def make_global_pause_check(bot):
    """Devuelve una función de check que bloquea comandos si bot.paused=True."""

    async def global_commands_check(ctx):
        allowed = ["pausa", "continuar", "reanudar"]
        if not bot.paused:
            return True
        if ctx.author.guild_permissions.administrator:
            return True
        if ctx.command and ctx.command.name in allowed:
            return True
        embed = discord.Embed(
            title="❌ Bot en Mantenimiento",
            description="El bot está pausado. Solo admins pueden usar comandos.",
            color=discord.Color.red(),
        )
        if ctx.guild:
            await ctx.send(embed=embed)
        return False

    return global_commands_check


# ─────────────────────────────────────────
# UTILIDAD: invocar comando desde botón/modal
# ─────────────────────────────────────────

async def invoke_command_from_interaction(bot, interaction: discord.Interaction, command_name: str, args=None):
    """Simula la ejecución de un comando desde un botón o modal."""
    try:
        if interaction.response.is_done():
            await interaction.followup.defer(ephemeral=False)
        else:
            await interaction.response.defer(ephemeral=False)
    except Exception as e:
        print(f"Advertencia defer: {e}")

    class SimulatedMessage(discord.Message):
        def __init__(self, interaction, content, author, bot):
            self.id = interaction.message.id if interaction.message else 0
            self.channel = interaction.channel
            self.guild = interaction.guild
            self.author = author
            self.content = content
            self.attachments = []
            self.embeds = []
            self.flags = discord.MessageFlags()
            self._state = bot._connection
            self._client = bot

    content = f"!{command_name}"
    if args:
        content += " " + (" ".join(map(str, args)) if isinstance(args, list) else str(args))

    msg = SimulatedMessage(interaction, content, interaction.user, bot)
    ctx = await bot.get_context(msg)

    if not ctx.command:
        await interaction.followup.send(f"❌ Comando `!{command_name}` no encontrado.", ephemeral=True)
        return

    ctx.send = interaction.followup.send
    try:
        await bot.invoke(ctx)
    except commands.CommandOnCooldown as e:
        await interaction.followup.send(f"⏰ Espera {e.retry_after:.0f}s.", ephemeral=True)
    except Exception as e:
        print(f"Error invocando {command_name}: {e}")
        await interaction.followup.send(f"❌ Error al ejecutar `!{command_name}`.", ephemeral=True)
