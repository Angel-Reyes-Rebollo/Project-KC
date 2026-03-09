"""
main.py — Punto de entrada del bot. Solo inicialización.
Toda la lógica vive en cogs/.

- Web Service compatible con Render (abre puerto HTTP)
- Restore automático desde GitHub al arrancar
- Backup automático a GitHub cada 1 hora
"""

import asyncio
import base64
import json
import os
import time

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands, tasks

import config
from database import db, set_catalog


# ─────────────────────────────────────────
# RESTORE: descarga bot_data.db desde GitHub si no existe localmente
# Protege contra reinicios de Render que borran el filesystem
# ─────────────────────────────────────────
async def restore_from_github():
    if os.path.exists("bot_data.db"):
        print("✅ bot_data.db encontrado localmente, no se necesita restaurar.")
        return

    token  = getattr(config, "GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))
    repo   = getattr(config, "GITHUB_REPO",  os.getenv("GITHUB_REPO", ""))
    branch = getattr(config, "BACKUP_BRANCH", os.getenv("BACKUP_BRANCH", "backup-data"))

    if not token or not repo:
        print("⚠️  Sin credenciales GitHub — arrancando con base de datos vacía.")
        return

    print("🔄 bot_data.db no encontrado — restaurando desde GitHub...")
    url = f"https://api.github.com/repos/{repo}/contents/backups/bot_data.db?ref={branch}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as r:
                if r.status == 404:
                    print("⚠️  No existe backup en GitHub todavía — arrancando limpio.")
                    return
                if r.status != 200:
                    print(f"⚠️  Error GitHub {r.status} al restaurar backup.")
                    return
                data = await r.json()
                content = base64.b64decode(data["content"])
                with open("bot_data.db", "wb") as f:
                    f.write(content)
                print("✅ Base de datos restaurada correctamente desde GitHub.")
    except Exception as e:
        print(f"❌ Error al restaurar backup: {e}")


# Ejecutar restore ANTES de inicializar la DB
asyncio.run(restore_from_github())


# ─────────────────────────────────────────
# Cargar catálogo de cartas
# ─────────────────────────────────────────
with open("catalogo.json", "r", encoding="utf-8") as f:
    catalog_data = json.load(f)

catalog_cards = catalog_data.get("cards", [])
catalog_by_id = {card["id"]: card for card in catalog_cards}

cards_catalog: dict[str, list] = {}
for card in catalog_cards:
    rarity = card.get("rareza", "N")
    cards_catalog.setdefault(rarity, []).append(card)

set_catalog(catalog_by_id)


# ─────────────────────────────────────────
# Inicializar base de datos SQLite
# ─────────────────────────────────────────
db.init()

# SOLO LA PRIMERA VEZ: cambia a True para migrar data.json → SQLite
# Luego vuelve a False
MIGRATE = False
if MIGRATE:
    db.migrate_from_json("data.json")


# ─────────────────────────────────────────
# Inicializar bot
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

bot.paused = False
bot.catalog_cards = catalog_cards
bot.catalog_by_id = catalog_by_id
bot.cards_catalog = cards_catalog


# ─────────────────────────────────────────
# SERVIDOR WEB (requerido por Render Web Service)
# Uptime Robot hace ping aquí para mantener el bot activo
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
# BACKUP AUTOMÁTICO cada 1 hora
# ─────────────────────────────────────────
@tasks.loop(hours=1)
async def auto_backup():
    token  = getattr(config, "GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))
    repo   = getattr(config, "GITHUB_REPO",  os.getenv("GITHUB_REPO", ""))
    branch = getattr(config, "BACKUP_BRANCH", os.getenv("BACKUP_BRANCH", "backup-data"))

    if not token or not repo:
        print("⚠️  Backup omitido: sin credenciales GitHub.")
        return

    if not os.path.exists("bot_data.db"):
        print("⚠️  Backup omitido: bot_data.db no existe.")
        return

    print("🔄 Ejecutando backup automático...")
    try:
        with open("bot_data.db", "rb") as f:
            content = base64.b64encode(f.read()).decode()

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"https://api.github.com/repos/{repo}/contents/backups/bot_data.db"

        async with aiohttp.ClientSession() as session:
            # Obtener SHA del archivo existente (necesario para actualizarlo en GitHub)
            async with session.get(f"{url}?ref={branch}", headers=headers) as r:
                existing = await r.json() if r.status == 200 else {}

            timestamp = time.strftime("%Y-%m-%d %H:%M UTC")
            payload = {
                "message": f"Backup automático {timestamp}",
                "content": content,
                "branch": branch,
            }
            if existing.get("sha"):
                payload["sha"] = existing["sha"]

            async with session.put(url, headers=headers, json=payload) as r:
                if r.status in (200, 201):
                    print(f"✅ Backup completado — {timestamp}")
                else:
                    text = await r.text()
                    print(f"❌ Error en backup {r.status}: {text}")

    except Exception as e:
        print(f"❌ Error en backup automático: {e}")


@auto_backup.before_loop
async def before_backup():
    await bot.wait_until_ready()


# ─────────────────────────────────────────
# Lista de cogs
# ─────────────────────────────────────────
COGS = [
    "cogs.economia",      # !trabajar, !diaria, !casino, !pesca, !minar, !rob
    "cogs.gacha",         # !gacha, !gacha_comprar, !inventario, !vender, !album
    "cogs.juegos",        # !blackjack, !ruleta, !adivina, !encuentra_gema
    "cogs.duelos",        # !dueloamistoso, !duelohonor, !aceptar_duelo, etc.
    "cogs.intercambio",   # !intercambio, !cancelar_intercambio
    "cogs.recompensas",   # !recompensa_tiempo, !recibir_recompensa, !eleccion
    "cogs.admin",         # !dargemas, !darcarta, !clear, !interfaz, !pausa, !backup_now
    "cogs.utilidades",    # !ayuda, !espera, !rates, !status, !menu_principal
]


# ─────────────────────────────────────────
# Eventos
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ {bot.user} está listo!")
    print(f"🗄️  Base de datos: {db._path}")
    print(f"📚 Catálogo: {len(catalog_cards)} cartas cargadas")
    print(f"🎮 Cogs: {', '.join(c.split('.')[1] for c in COGS)}")
    print(f"🔄 Backup automático activo — cada 1 hora → GitHub")
    auto_backup.start()


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
# Arrancar
# ─────────────────────────────────────────
async def main():
    await start_web_server()  # Abre el puerto HTTP para Render
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
