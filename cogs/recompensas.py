"""
cogs/recompensas.py — Sistema de recompensas temporales y fijas.

Comandos: !recompensa_tiempo, !recibir_recompensa, !estado_recompensa,
          !cancelar_recompensa, !eleccion_carta, !eleccion_recompensa,
          !gemas_fijas, !recibir_gemas, !cancelar_gemas_fijas, !estado_gemas_fijas
"""

import asyncio
import os
import time

import discord
from discord.ext import commands

from cogs.utils import (
    add_balance, add_to_inventory, format_gems,
    get_balance, get_rarity_color, get_rarity_emoji,
)


class Recompensas(commands.Cog):
    """Sistema de recompensas temporales y eventos."""

    def __init__(self, bot):
        self.bot = bot
        # Recompensa de carta temporal
        self.recompensa_activa = None       # dict con carta, inicio, duracion, creador
        self.recompensa_claimers: set = set()
        # Recompensa fija de gemas
        self.gem_reward = {"amount": 0, "expires_at": 0, "claimed": set()}
        # Elección global de cartas
        self.eleccion_activa = None         # dict con card1, card2, votes, claimers
        self.eleccion_claimers: set = set()

    # ─────────────────────────────────────────
    # RECOMPENSA DE CARTA TEMPORAL
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def recompensa_tiempo(self, ctx, card_id: str = None, duracion_minutos: int = 60):
        """Crea una recompensa temporal. Uso: !recompensa_tiempo <card_id> <minutos>"""
        if not card_id:
            await ctx.send("❌ Uso: `!recompensa_tiempo <card_id> <minutos>`"); return

        card = self.bot.catalog_by_id.get(card_id.upper())
        if not card:
            await ctx.send(f"❌ No se encontró carta con ID `{card_id}`."); return

        self.recompensa_activa = {
            "carta": card,
            "inicio": time.time(),
            "duracion": duracion_minutos * 60,
            "creador": ctx.author,
        }
        self.recompensa_claimers.clear()

        rarity = card.get("rareza", "N")
        embed = discord.Embed(title="🎉 ¡RECOMPENSA TEMPORAL ACTIVADA!",
            description=f"{ctx.author.mention} activó una recompensa para todos.",
            color=get_rarity_color(rarity))
        embed.add_field(name=f"{get_rarity_emoji(rarity)} Carta", value=f"**{card['nombre']}** ({rarity})", inline=False)
        embed.add_field(name="⏰ Duración", value=f"{duracion_minutos} minutos", inline=True)
        embed.add_field(name="🎯 Reclamar", value="`!recibir_recompensa`", inline=True)
        embed.add_field(name="⚠️ Límite", value="Una vez por usuario", inline=False)

        image_path = card.get("imagen", "")
        if image_path and os.path.exists(image_path):
            try:
                file = discord.File(image_path, filename="rw.png")
                embed.set_thumbnail(url="attachment://rw.png")
                await ctx.send(embed=embed, file=file)
            except Exception:
                await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed)

        # Finalizar automáticamente
        self.bot.loop.create_task(self._finalizar_recompensa(ctx, duracion_minutos * 60))

    async def _finalizar_recompensa(self, ctx, segundos: float):
        await asyncio.sleep(segundos)
        if self.recompensa_activa:
            nombre = self.recompensa_activa["carta"]["nombre"]
            total = len(self.recompensa_claimers)
            self.recompensa_activa = None
            self.recompensa_claimers.clear()
            embed = discord.Embed(title="⏰ Recompensa Finalizada",
                description=f"La recompensa de **{nombre}** terminó. **{total}** usuarios la reclamaron.",
                color=discord.Color.orange())
            await ctx.send(embed=embed)

    @commands.command()
    async def recibir_recompensa(self, ctx):
        """Reclama la recompensa temporal activa."""
        if not self.recompensa_activa:
            await ctx.send("❌ No hay recompensas activas ahora mismo."); return
        if ctx.author.id in self.recompensa_claimers:
            await ctx.send("⚠️ Ya reclamaste esta recompensa."); return

        elapsed = time.time() - self.recompensa_activa["inicio"]
        remaining = self.recompensa_activa["duracion"] - elapsed
        if remaining <= 0:
            self.recompensa_activa = None
            await ctx.send("⏰ Esta recompensa ya expiró."); return

        carta = self.recompensa_activa["carta"]
        add_to_inventory(ctx.author.id, carta)
        self.recompensa_claimers.add(ctx.author.id)

        rarity = carta.get("rareza", "N")
        embed = discord.Embed(title="🎁 ¡Recompensa Reclamada!",
            description=f"{ctx.author.mention} obtuvo **{carta['nombre']}**",
            color=get_rarity_color(rarity))
        embed.add_field(name="Tiempo restante", value=f"{int(remaining/60)} minutos", inline=True)
        embed.add_field(name="Reclamantes", value=str(len(self.recompensa_claimers)), inline=True)
        await ctx.send(embed=embed)

    @commands.command()
    async def estado_recompensa(self, ctx):
        """Muestra el estado de la recompensa activa."""
        if not self.recompensa_activa:
            await ctx.send("📭 No hay recompensas activas."); return
        carta = self.recompensa_activa["carta"]
        remaining = self.recompensa_activa["duracion"] - (time.time() - self.recompensa_activa["inicio"])
        embed = discord.Embed(title="🎯 Recompensa Activa", color=get_rarity_color(carta.get("rareza","N")))
        embed.add_field(name="Carta", value=f"**{carta['nombre']}** ({carta.get('rareza','N')})")
        embed.add_field(name="Tiempo restante", value=f"{max(0, int(remaining/60))} minutos")
        embed.add_field(name="Reclamantes", value=str(len(self.recompensa_claimers)))
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cancelar_recompensa(self, ctx):
        """Cancela la recompensa activa."""
        if not self.recompensa_activa:
            await ctx.send("❌ No hay recompensa activa."); return
        nombre = self.recompensa_activa["carta"]["nombre"]
        total = len(self.recompensa_claimers)
        self.recompensa_activa = None
        self.recompensa_claimers.clear()
        await ctx.send(f"🗑️ Recompensa de **{nombre}** cancelada. Reclamaron **{total}** usuarios.")

    # ─────────────────────────────────────────
    # RECOMPENSA FIJA DE GEMAS
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def gemas_fijas(self, ctx, cantidad: int = 0, horas: int = 24):
        """Activa una recompensa fija de gemas para todos. Uso: !gemas_fijas <gemas> <horas>"""
        if cantidad <= 0:
            await ctx.send("❌ La cantidad debe ser mayor a 0."); return
        self.gem_reward = {
            "amount": cantidad,
            "expires_at": time.time() + horas * 3600,
            "claimed": set(),
        }
        embed = discord.Embed(title="💎 ¡Recompensa de Gemas Activada!",
            description=f"**{cantidad} gemas** para cada usuario durante **{horas} horas**.",
            color=discord.Color.gold())
        embed.add_field(name="Cómo reclamar", value="`!recibir_gemas`")
        await ctx.send(embed=embed)

    @commands.command()
    async def recibir_gemas(self, ctx):
        """Reclama la recompensa fija de gemas activa."""
        r = self.gem_reward
        if r["amount"] == 0 or time.time() > r["expires_at"]:
            await ctx.send("❌ No hay recompensa de gemas activa."); return
        if ctx.author.id in r["claimed"]:
            await ctx.send("⚠️ Ya reclamaste esta recompensa."); return
        add_balance(ctx.author.id, r["amount"])
        r["claimed"].add(ctx.author.id)
        await ctx.send(f"💎 {ctx.author.mention} reclamó **{format_gems(r['amount'])}**. "
                       f"Nuevo balance: **{format_gems(get_balance(ctx.author.id))}**.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cancelar_gemas_fijas(self, ctx):
        """Cancela la recompensa fija de gemas."""
        if self.gem_reward["amount"] == 0:
            await ctx.send("❌ No hay recompensa activa."); return
        cantidad = self.gem_reward["amount"]
        self.gem_reward = {"amount": 0, "expires_at": 0, "claimed": set()}
        await ctx.send(f"❌ Recompensa de **{format_gems(cantidad)}** cancelada.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def estado_gemas_fijas(self, ctx):
        """Muestra el estado de la recompensa fija de gemas."""
        r = self.gem_reward
        if r["amount"] == 0 or time.time() > r["expires_at"]:
            await ctx.send("❌ No hay recompensa activa."); return
        remaining = int((r["expires_at"] - time.time()) / 60)
        await ctx.send(f"💎 **{format_gems(r['amount'])}** | ⏰ {remaining} min restantes | "
                       f"👥 {len(r['claimed'])} reclamaron")

    # ─────────────────────────────────────────
    # ELECCIÓN GLOBAL DE CARTAS
    # ─────────────────────────────────────────
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def eleccion_carta(self, ctx, card_id1: str = None, card_id2: str = None):
        """Crea una elección global entre dos cartas. Uso: !eleccion_carta <id1> <id2>"""
        if not card_id1 or not card_id2:
            await ctx.send("❌ Uso: `!eleccion_carta <card_id1> <card_id2>`"); return

        c1 = self.bot.catalog_by_id.get(card_id1.upper())
        c2 = self.bot.catalog_by_id.get(card_id2.upper())
        if not c1: await ctx.send(f"❌ Carta `{card_id1}` no encontrada."); return
        if not c2: await ctx.send(f"❌ Carta `{card_id2}` no encontrada."); return

        self.eleccion_activa = {"card1": c1, "card2": c2, "votes1": 0, "votes2": 0}
        self.eleccion_claimers.clear()

        embed = discord.Embed(title="🗳️ ¡ELECCIÓN GLOBAL!",
            description="Vota por la carta que quieres recibir. ¡Solo puedes votar una vez!",
            color=discord.Color.purple())
        embed.add_field(name=f"Opción A: {c1['nombre']}", value=f"Rareza: {c1['rareza']}", inline=True)
        embed.add_field(name=f"Opción B: {c2['nombre']}", value=f"Rareza: {c2['rareza']}", inline=True)
        embed.add_field(name="Cómo votar", value="`!eleccion_recompensa`", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def eleccion_recompensa(self, ctx, opcion: str = None):
        """Vota en la elección global. Uso: !eleccion_recompensa A o B"""
        if not self.eleccion_activa:
            await ctx.send("❌ No hay ninguna elección activa."); return
        if ctx.author.id in self.eleccion_claimers:
            await ctx.send("⚠️ Ya votaste en esta elección."); return
        if opcion not in ("A", "a", "B", "b"):
            await ctx.send("❌ Vota con `A` o `B`. Ej: `!eleccion_recompensa A`"); return

        carta = self.eleccion_activa["card1"] if opcion.upper() == "A" else self.eleccion_activa["card2"]
        add_to_inventory(ctx.author.id, carta)
        self.eleccion_claimers.add(ctx.author.id)
        if opcion.upper() == "A":
            self.eleccion_activa["votes1"] += 1
        else:
            self.eleccion_activa["votes2"] += 1

        await ctx.send(f"✅ {ctx.author.mention} eligió **{carta['nombre']}** y la recibió en su inventario.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cancelar_eleccion(self, ctx):
        """Cancela la elección global activa."""
        if not self.eleccion_activa:
            await ctx.send("❌ No hay elección activa."); return
        v1 = self.eleccion_activa["votes1"]
        v2 = self.eleccion_activa["votes2"]
        self.eleccion_activa = None
        self.eleccion_claimers.clear()
        await ctx.send(f"🗑️ Elección cancelada. Votos — A: {v1} | B: {v2}")


async def setup(bot):
    await bot.add_cog(Recompensas(bot))
