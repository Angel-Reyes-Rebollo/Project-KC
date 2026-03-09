"""
cogs/admin.py — Comandos exclusivos de administradores.

Comandos: !pausa, !continuar, !dargemas, !quitargemas, !darcarta,
          !quitarcarta, !limpiar_inventario, !reset_data, !clear,
          !interfaz, !subir_imagen, !modificar_rates, !backup_now,
          !backup_status, !listar_backups, !borrar_backups
"""

import json
import os
import time

import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View

from cogs.utils import (
    add_balance, add_to_inventory, format_gems,
    get_balance, get_inventory, get_rarity_color, get_rarity_emoji,
    rarity_probabilities,
)
from database import db

try:
    import config
    GITHUB_TOKEN = getattr(config, "GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))
    GITHUB_REPO  = getattr(config, "GITHUB_REPO", os.getenv("GITHUB_REPO", ""))
    BACKUP_BRANCH = getattr(config, "BACKUP_BRANCH", "backup-data")
except Exception:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO  = os.getenv("GITHUB_REPO", "")
    BACKUP_BRANCH = "backup-data"


class Admin(commands.Cog):
    """Comandos de administración del bot."""

    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # PAUSA / CONTINUAR
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def pausa(self, ctx):
        """Pausa el bot para mantenimiento."""
        self.bot.paused = True
        embed = discord.Embed(title="⏸️ Bot Pausado",
            description="Modo mantenimiento activado. Solo admins pueden usar comandos.",
            color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(aliases=["reanudar"])
    @commands.has_permissions(administrator=True)
    async def continuar(self, ctx):
        """Reanuda el bot."""
        self.bot.paused = False
        embed = discord.Embed(title="▶️ Bot Reanudado",
            description="Mantenimiento finalizado. ¡Todo funciona normalmente!",
            color=discord.Color.green())
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # GEMAS
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def dargemas(self, ctx, member: discord.Member, cantidad: int):
        """Da gemas a un usuario. Uso: !dargemas @usuario <cantidad>"""
        add_balance(member.id, cantidad)
        await ctx.send(f"✅ Le diste **{format_gems(cantidad)}** a {member.mention}. "
                       f"Nuevo balance: **{format_gems(get_balance(member.id))}**.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quitargemas(self, ctx, member: discord.Member, cantidad: int):
        """Quita gemas a un usuario. Uso: !quitargemas @usuario <cantidad>"""
        current = get_balance(member.id)
        actual = min(cantidad, current)
        add_balance(member.id, -actual)
        await ctx.send(f"✅ Quitaste **{format_gems(actual)}** a {member.mention}. "
                       f"Nuevo balance: **{format_gems(get_balance(member.id))}**.")

    # ─────────────────────────────────────────
    # CARTAS
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def darcarta(self, ctx, member: discord.Member, card_id: str):
        """Regala una carta a un usuario. Uso: !darcarta @usuario <card_id>"""
        card = self.bot.catalog_by_id.get(card_id)
        if not card:
            await ctx.send(f"❌ No se encontró ninguna carta con ID `{card_id}`."); return

        add_to_inventory(member.id, card)
        rarity = card.get("rareza", "N")
        embed = discord.Embed(
            title=f"{get_rarity_emoji(rarity)} {card['nombre']} ({rarity})",
            description=f"Regalada por {ctx.author.mention} a {member.mention}",
            color=get_rarity_color(rarity))

        image_path = card.get("imagen", "")
        if image_path and os.path.exists(image_path):
            file = discord.File(image_path, filename="carta.png")
            embed.set_image(url="attachment://carta.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quitarcarta(self, ctx, member: discord.Member, card_id: str):
        """Quita una carta del inventario de un usuario. Uso: !quitarcarta @usuario <card_id>"""
        if db.remove_card(member.id, card_id):
            await ctx.send(f"✅ Se eliminó la carta `{card_id}` del inventario de {member.mention}.")
        else:
            await ctx.send(f"❌ {member.mention} no tiene la carta `{card_id}`.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def limpiar_inventario(self, ctx, member: discord.Member):
        """Limpia todo el inventario de un usuario."""
        db.clear_inventory(member.id)
        await ctx.send(f"✅ Inventario de {member.mention} limpiado.")

    # ─────────────────────────────────────────
    # RESET
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reset_data(self, ctx):
        """⚠️ Resetea TODOS los datos de usuarios (inventarios, gemas, cooldowns)."""
        view = View(timeout=60)

        async def confirm_cb(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo el admin que ejecutó puede confirmar.", ephemeral=True); return
            # No hay forma fácil de borrar todo en SQLite sin iterar usuarios
            # Borrar tabla por tabla
            conn = db._conn()
            conn.executescript("""
                DELETE FROM balances;
                DELETE FROM inventory;
                DELETE FROM cooldowns;
                DELETE FROM rob_penalties;
                DELETE FROM completed_floors;
            """)
            for item in view.children: item.disabled = True
            await interaction.response.edit_message(content="⚠️ Todos los datos reseteados.", view=view)
            view.stop()

        async def cancel_cb(interaction):
            for item in view.children: item.disabled = True
            await interaction.response.edit_message(content="✅ Reset cancelado.", view=view)
            view.stop()

        confirm_btn = Button(label="⚠️ Confirmar Reset TOTAL", style=discord.ButtonStyle.red)
        cancel_btn = Button(label="❌ Cancelar", style=discord.ButtonStyle.gray)
        confirm_btn.callback = confirm_cb
        cancel_btn.callback = cancel_cb
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        await ctx.send("⚠️ **¿Estás seguro?** Esto borrará TODOS los inventarios, gemas y cooldowns.", view=view)

    # ─────────────────────────────────────────
    # CLEAR mensajes
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, cantidad: int = 10):
        """Borra mensajes del canal. Uso: !clear <cantidad>"""
        cantidad = min(cantidad, 100)
        deleted = await ctx.channel.purge(limit=cantidad + 1)
        msg = await ctx.send(f"🗑️ Se eliminaron **{len(deleted) - 1}** mensajes.")
        await msg.delete(delay=3)

    # ─────────────────────────────────────────
    # MODIFICAR RATES GACHA
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def modificar_rates(self, ctx):
        """Muestra e interfaz para modificar las probabilidades del gacha."""
        embed = discord.Embed(title="🎰 Probabilidades del Gacha",
            description="Probabilidades actuales:", color=discord.Color.blue())
        for rarity, prob in rarity_probabilities.items():
            embed.add_field(name=f"{get_rarity_emoji(rarity)} {rarity}",
                value=f"{prob*100:.2f}%", inline=True)
        embed.add_field(name="Total", value=f"{sum(rarity_probabilities.values())*100:.2f}%", inline=False)

        view = View(timeout=300)
        rarities = ["G", "SP", "UR", "SSR", "R", "N"]

        def make_callback(r):
            async def cb(interaction):
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ Solo admins.", ephemeral=True); return
                modal = ModificarRateModal(r, rarity_probabilities[r])
                await interaction.response.send_modal(modal)
            return cb

        for r in rarities:
            btn = Button(label=f"{r}", style=discord.ButtonStyle.blurple, emoji=get_rarity_emoji(r))
            btn.callback = make_callback(r)
            view.add_item(btn)

        await ctx.send(embed=embed, view=view)

    # ─────────────────────────────────────────
    # INTERFAZ DE CATÁLOGO
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def interfaz(self, ctx):
        """Panel de administración del catálogo de cartas."""
        embed = discord.Embed(title="🛠️ Panel de Administración",
            description="Gestiona el catálogo de cartas:", color=discord.Color.blue())
        embed.add_field(name="➕ Agregar", value="Añade una nueva carta", inline=True)
        embed.add_field(name="🗑️ Eliminar", value="Elimina una carta", inline=True)

        view = View(timeout=300)

        async def agregar_cb(interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Solo admins.", ephemeral=True); return
            modal = AgregarCartaModal(self.bot)
            await interaction.response.send_modal(modal)

        async def eliminar_cb(interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Solo admins.", ephemeral=True); return
            modal = EliminarCartaModal(self.bot)
            await interaction.response.send_modal(modal)

        btn_add = Button(label="➕ Agregar Carta", style=discord.ButtonStyle.green)
        btn_del = Button(label="🗑️ Eliminar Carta", style=discord.ButtonStyle.red)
        btn_add.callback = agregar_cb
        btn_del.callback = eliminar_cb
        view.add_item(btn_add)
        view.add_item(btn_del)
        await ctx.send(embed=embed, view=view)

    # ─────────────────────────────────────────
    # SUBIR IMAGEN
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def subir_imagen(self, ctx, card_id: str):
        """Sube una imagen para una carta. Adjunta la imagen al mensaje."""
        if not ctx.message.attachments:
            await ctx.send("❌ Adjunta una imagen al comando. Ej: `!subir_imagen UR001` (con imagen)"); return

        card = self.bot.catalog_by_id.get(card_id)
        if not card:
            await ctx.send(f"❌ No se encontró la carta `{card_id}`."); return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            await ctx.send("❌ Solo se admiten imágenes PNG, JPG o GIF."); return

        os.makedirs("images", exist_ok=True)
        path = f"images/{card_id}.png"
        await attachment.save(path)
        card["imagen"] = path

        # Actualizar catalogo.json
        catalog_data = {"cards": self.bot.catalog_cards}
        with open("catalogo.json", "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)

        await ctx.send(f"✅ Imagen de **{card['nombre']}** actualizada en `{path}`.")

    # ─────────────────────────────────────────
    # BACKUP GITHUB
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def backup_now(self, ctx):
        """Crea un backup manual inmediato en GitHub."""
        if not GITHUB_TOKEN or not GITHUB_REPO:
            await ctx.send("❌ `GITHUB_TOKEN` y `GITHUB_REPO` deben estar configurados."); return
        await ctx.send("🔄 Creando backup...")
        try:
            await self._push_backup()
            await ctx.send("✅ Backup creado en GitHub exitosamente.")
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def backup_status(self, ctx):
        """Muestra el estado del sistema de backup."""
        embed = discord.Embed(title="📊 Estado del Backup", color=discord.Color.blue())
        embed.add_field(name="GitHub Token", value="✅ Configurado" if GITHUB_TOKEN else "❌ No configurado", inline=True)
        embed.add_field(name="Repositorio", value=GITHUB_REPO or "No configurado", inline=True)
        embed.add_field(name="Rama", value=BACKUP_BRANCH, inline=True)
        await ctx.send(embed=embed)

    async def _push_backup(self):
        """Sube bot_data.db a GitHub como backup."""
        import base64

        if not os.path.exists("bot_data.db"):
            raise FileNotFoundError("No se encontró bot_data.db")

        with open("bot_data.db", "rb") as f:
            content = base64.b64encode(f.read()).decode()

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/backups/bot_data.db"
        timestamp = time.strftime("%Y-%m-%d %H:%M UTC")

        async with aiohttp.ClientSession() as session:
            # Verificar si ya existe para obtener el SHA
            async with session.get(url, headers=headers) as r:
                existing = await r.json() if r.status == 200 else {}

            payload = {
                "message": f"Backup automático {timestamp}",
                "content": content,
                "branch": BACKUP_BRANCH,
            }
            if existing.get("sha"):
                payload["sha"] = existing["sha"]

            async with session.put(url, headers=headers, json=payload) as r:
                if r.status not in (200, 201):
                    text = await r.text()
                    raise Exception(f"GitHub API error {r.status}: {text}")


# ─────────────────────────────────────────
# Modales del catálogo
# ─────────────────────────────────────────
class AgregarCartaModal(discord.ui.Modal, title="➕ Agregar Nueva Carta"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(discord.ui.TextInput(label="ID", placeholder="Ej: UR012"))
        self.add_item(discord.ui.TextInput(label="Nombre", placeholder="Ej: Hinata SSR"))
        self.add_item(discord.ui.TextInput(label="Rareza", placeholder="N, R, SSR, UR, SP, G"))
        self.add_item(discord.ui.TextInput(label="Valor en gemas", placeholder="Ej: 100"))
        self.add_item(discord.ui.TextInput(label="Descripción", style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        cid     = self.children[0].value.strip().upper()
        nombre  = self.children[1].value.strip()
        rareza  = self.children[2].value.strip().upper()
        valor_s = self.children[3].value.strip()
        desc    = self.children[4].value.strip()

        if not valor_s.isdigit():
            await interaction.response.send_message("❌ El valor debe ser un número.", ephemeral=True); return
        if cid in self.bot.catalog_by_id:
            await interaction.response.send_message(f"❌ Ya existe una carta con ID `{cid}`.", ephemeral=True); return

        nueva = {
            "id": cid, "nombre": nombre, "rareza": rareza,
            "valor": int(valor_s), "stock": "Unlimited", "max_per_user": 1000,
            "imagen": f"images/{cid}.png", "descripcion": desc,
            "stats": {s: 50 for s in ["Evasion","Fuerza","Reaccion","Defensa","Velocidad","IQ","Carisma","Precision","Energia","Suerte"]}
        }
        self.bot.catalog_cards.append(nueva)
        self.bot.catalog_by_id[cid] = nueva
        self.bot.cards_catalog.setdefault(rareza, []).append(nueva)

        with open("catalogo.json", "w", encoding="utf-8") as f:
            json.dump({"cards": self.bot.catalog_cards}, f, ensure_ascii=False, indent=2)

        await interaction.response.send_message(f"✅ Carta **{nombre}** ({rareza}) agregada al catálogo.", ephemeral=True)


class EliminarCartaModal(discord.ui.Modal, title="🗑️ Eliminar Carta"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(discord.ui.TextInput(label="ID de la carta", placeholder="Ej: N001"))

    async def on_submit(self, interaction: discord.Interaction):
        cid = self.children[0].value.strip().upper()
        card = self.bot.catalog_by_id.get(cid)
        if not card:
            await interaction.response.send_message(f"❌ No existe carta con ID `{cid}`.", ephemeral=True); return

        rareza = card["rareza"]
        self.bot.catalog_cards[:] = [c for c in self.bot.catalog_cards if c["id"] != cid]
        del self.bot.catalog_by_id[cid]
        if rareza in self.bot.cards_catalog:
            self.bot.cards_catalog[rareza] = [c for c in self.bot.cards_catalog[rareza] if c["id"] != cid]

        with open("catalogo.json", "w", encoding="utf-8") as f:
            json.dump({"cards": self.bot.catalog_cards}, f, ensure_ascii=False, indent=2)

        await interaction.response.send_message(f"✅ Carta `{cid}` eliminada del catálogo.", ephemeral=True)


class ModificarRateModal(discord.ui.Modal, title="🎰 Modificar Rate"):
    def __init__(self, rarity, current_prob):
        super().__init__()
        self.rarity = rarity
        self.add_item(discord.ui.TextInput(
            label=f"Nuevo % para {rarity}",
            placeholder=f"Actual: {current_prob*100:.2f}% — Ej: 1.5",
            default=str(round(current_prob * 100, 4)),
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nuevo = float(self.children[0].value.strip())
            if nuevo < 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Número inválido.", ephemeral=True); return

        rarity_probabilities[self.rarity] = nuevo / 100.0
        total = sum(rarity_probabilities.values()) * 100
        await interaction.response.send_message(
            f"✅ **{self.rarity}** actualizado a **{nuevo:.2f}%**. Total actual: **{total:.2f}%**\n"
            f"{'⚠️ Las probabilidades no suman 100%!' if abs(total - 100) > 0.5 else ''}",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
