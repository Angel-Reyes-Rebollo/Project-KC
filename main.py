"""
main.py — Punto de entrada del bot.
- Usa data.json igual que el original (sin SQLite)
- Backup automático cada 1 hora a GitHub (data.json + catalogo.json)
- Servidor web para Render Web Service
- Toda la lógica de comandos vive en cogs/
"""

import base64
import asyncio
import json
import os
import threading
import time
from datetime import datetime

import aiohttp
import discord
import requests
import schedule
from aiohttp import web
from discord.ext import commands

import config

# ─────────────────────────────────────────
# ARCHIVOS DE DATOS
# ─────────────────────────────────────────
CATALOG_FILE = "catalogo.json"
DATA_FILE     = "data.json"

# ─────────────────────────────────────────
# CARGAR CATÁLOGO
# ─────────────────────────────────────────
with open(CATALOG_FILE, "r", encoding="utf-8") as f:
    catalog_data = json.load(f)

catalog_cards = catalog_data.get("cards", [])
catalog_by_id = {card["id"]: card for card in catalog_cards}

cards_catalog: dict = {}
for card in catalog_cards:
    rarity = card.get("rareza", "N")
    cards_catalog.setdefault(rarity, []).append(card)

# ─────────────────────────────────────────
# CARGAR / GUARDAR data.json
# ─────────────────────────────────────────
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
    user_inventories    = user_data.get("inventories", {})
    user_balances       = user_data.get("balances", {})
    user_rob_penalties  = user_data.get("rob_penalties", {})
    user_completed_floors = user_data.get("completed_floors", {})
else:
    user_inventories      = {}
    user_balances         = {}
    user_rob_penalties    = {}
    user_completed_floors = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "inventories":      user_inventories,
            "balances":         user_balances,
            "rob_penalties":    user_rob_penalties,
            "completed_floors": user_completed_floors,
        }, f, ensure_ascii=False, indent=4)

# ─────────────────────────────────────────
# INICIALIZAR BOT
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

bot.paused = False

# Datos accesibles desde los cogs vía bot.*
bot.catalog_cards       = catalog_cards
bot.catalog_by_id       = catalog_by_id
bot.cards_catalog       = cards_catalog
bot.user_inventories    = user_inventories
bot.user_balances       = user_balances
bot.user_rob_penalties  = user_rob_penalties
bot.user_completed_floors = user_completed_floors
bot.save_data           = save_data
bot.DATA_FILE           = DATA_FILE
bot.CATALOG_FILE        = CATALOG_FILE

# Registrar bot en utils para que los cogs usen get_balance(), add_balance(), etc.
from cogs import utils as _utils
_utils.set_bot(bot)

# ─────────────────────────────────────────
# CHECK GLOBAL DE PAUSA
# ─────────────────────────────────────────
@bot.check
async def global_commands_check(ctx):
    allowed = ["pausa", "continuar", "reanudar"]
    if not bot.paused:
        return True
    if ctx.author.guild_permissions.administrator:
        return True
    if ctx.command and ctx.command.name in allowed:
        return True
    embed = discord.Embed(
        title="❌ Bot Pausado por Mantenimiento",
        description="Solo los administradores pueden usar comandos ahora mismo.",
        color=discord.Color.red(),
    )
    if ctx.guild:
        await ctx.send(embed=embed)
    return False

# ─────────────────────────────────────────
# SISTEMA DE BACKUP A GITHUB (igual que el original)
# ─────────────────────────────────────────
GITHUB_TOKEN  = config.GITHUB_TOKEN
REPO_OWNER    = "CosmicDragneel21"
REPO_NAME     = "Project-KC"
BACKUP_BRANCH = "backup-auto"

def create_github_backup():
    """Sube data.json y catalogo.json a GitHub con timestamp."""
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN no configurado — omitiendo backup")
        return

    try:
        print("🔄 Iniciando backup automático...")

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data_content = f.read()
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            catalog_content = f.read()

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_files = {
            f"backup_{timestamp}_data.json":     data_content,
            f"backup_{timestamp}_catalogo.json": catalog_content,
        }

        success_count = 0
        for filename, content in backup_files.items():
            try:
                content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
                url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/backups/{filename}"
                payload = {
                    "message": f"🤖 Backup automático — {timestamp}",
                    "content": content_b64,
                    "branch":  BACKUP_BRANCH,
                }
                r = requests.put(url, headers=headers, json=payload, timeout=30)
                if r.status_code in (200, 201):
                    print(f"✅ Backup creado: {filename}")
                    success_count += 1
                else:
                    print(f"❌ Error backup {filename}: {r.json().get('message', r.status_code)}")
            except Exception as e:
                print(f"❌ Error subiendo {filename}: {e}")

        print(f"📊 Backup completado: {success_count}/2 archivos")

    except Exception as e:
        print(f"❌ Error en backup automático: {e}")


def run_scheduled_backups():
    """Hilo que ejecuta el backup cada 1 hora."""
    schedule.every(1).hours.do(create_github_backup)
    print("🕒 Sistema de backup iniciado (cada 1 hora)")
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            print(f"❌ Error en programador de backup: {e}")
            time.sleep(60)

# Iniciar hilo de backups
try:
    backup_thread = threading.Thread(target=run_scheduled_backups, daemon=True)
    backup_thread.start()
    print("✅ Backup automático iniciado (cada 1 hora → GitHub)")
except Exception as e:
    print(f"❌ No se pudo iniciar el sistema de backup: {e}")

# Exponer la función para !backup_now desde admin.py
bot.create_github_backup = create_github_backup

# ─────────────────────────────────────────
# SERVIDOR WEB (requerido por Render Web Service)
# La URL del servicio sirve como endpoint para Uptime Robot
# ─────────────────────────────────────────
async def health_check(request):
    return web.Response(text="✅ Bot activo", content_type="text/plain")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Servidor web escuchando en puerto {port}")

# ─────────────────────────────────────────
# LISTA DE COGS
# ─────────────────────────────────────────
COGS = [
    "cogs.economia",       # !trabajar, !diaria, !casino, !pesca, !minar, !rob
    "cogs.gacha_banners",  # !gacha <anime>, !gacha_comprar <anime>, !banners, !banner_info
    "cogs.gacha",          # !inventario, !vender, !vender_mayoreo, !vender_rareza, !album
    "cogs.juegos",      # !blackjack, !ruleta, !adivina, !encuentra_gema
    "cogs.duelos",      # !dueloamistoso, !duelohonor, !cancelar_duelo
    "cogs.intercambio", # !intercambio, !cancelar_intercambio
    "cogs.recompensas", # !recompensa_tiempo, !recibir_recompensa, !eleccion
    "cogs.admin",       # !dargemas, !darcarta, !clear, !interfaz, !pausa, !backup_now
    "cogs.utilidades",  # !ayuda, !espera, !rates, !status, !menu_principal
]

# ─────────────────────────────────────────
# EVENTOS
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ {bot.user} está listo!")
    print(f"📚 Catálogo: {len(catalog_cards)} cartas")
    print(f"👥 Usuarios en data.json: {len(user_inventories)}")
    print(f"🎮 Cogs: {', '.join(c.split('.')[1] for c in COGS)}")
    print(f"🔄 Backup automático: cada 1 hora → GitHub ({REPO_OWNER}/{REPO_NAME})")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permisos para usar este comando.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ No se encontró al usuario mencionado.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argumento inválido. Revisa el uso del comando con `!ayuda`.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"❌ Error no manejado en {ctx.command}: {error}")

# ─────────────────────────────────────────
# ARRANCAR
# ─────────────────────────────────────────
async def main():
    await start_web_server()
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✅ Cog cargado: {cog}")
            except Exception as e:
                print(f"  ❌ Error cargando {cog}: {e}")
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
