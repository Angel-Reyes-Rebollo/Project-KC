"""
cogs/duelos.py — Sistema de duelos PvP entre usuarios.

INSTRUCCIONES DE MIGRACIÓN desde main.py:
  1. Copia estas clases directamente:
     - DuelAcceptView         (línea ~3134)
     - DuelCardSelectionAmistosoView (línea ~3226)
     - DuelCardSelectionHonorView    (busca la clase similar para honor)
  2. Copia estas funciones:
     - iniciar_seleccion_cartas_amistoso
     - iniciar_seleccion_cartas_honor
     - quitarcarta_from_inventory  → reemplazar por: db.remove_card(user_id, card_id)
  3. Copia los comandos:
     - !dueloamistoso  (línea ~3738)
     - !duelohonor
     - !aceptar_duelo
     - !rechazar_duelo
     - !cancelar_duelo
  4. Cambios a hacer:
     - @bot.command() → @commands.command()
     - quitarcarta_from_inventory(uid, cid) → db.remove_card(uid, cid)
     - Mover pending_duels como atributo del Cog: self.pending_duels = {}

Estructura base:
"""

import random
import time

import discord
from discord.ext import commands

from cogs.utils import (
    add_to_inventory, format_gems, get_inventory,
    get_rarity_color, get_rarity_emoji, RARITY_ORDER,
)
from database import db

# Atributos para duelos
DUEL_ATTRIBUTES = {
    "Evasion": "👻 Evasion", "Fuerza": "💥 Fuerza",
    "Reacción": "🌀 Reacción", "Defensa": "🛡️ Defensa",
    "Velocidad": "💨 Velocidad", "IQ": "🧠 IQ",
    "Carisma": "✨ Carisma", "Precisión": "🎯 Precisión",
    "Energia": "⚡ Energia", "Suerte": "🍀 Suerte",
}


class Duelos(commands.Cog):
    """Sistema de duelos PvP."""

    def __init__(self, bot):
        self.bot = bot
        self.pending_duels: dict = {}

    @commands.command()
    async def dueloamistoso(self, ctx, member: discord.Member = None):
        """Reta a otro usuario a un duelo amistoso de 3 rondas."""
        if member is None:
            await ctx.send("❌ Menciona a un usuario. Ej: `!dueloamistoso @usuario`"); return
        if member.id == ctx.author.id:
            await ctx.send("❌ No puedes retarte a ti mismo."); return
        if member.bot:
            await ctx.send("❌ No puedes retar a un bot."); return

        author_inv = get_inventory(ctx.author.id)
        member_inv = get_inventory(member.id)
        if len(author_inv) < 3:
            await ctx.send("❌ Necesitas al menos 3 cartas para un duelo amistoso."); return
        if len(member_inv) < 3:
            await ctx.send(f"❌ {member.mention} necesita al menos 3 cartas."); return

        # AQUÍ: pega DuelAcceptView y la lógica del duelo desde main.py
        embed = discord.Embed(
            title="⚔️ Duelo Amistoso",
            description=f"{ctx.author.mention} reta a {member.mention}.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Tipo", value="Amistoso (3 rondas)", inline=True)
        embed.add_field(name="Estado", value="⚠️ Migración pendiente — ver instrucciones en el archivo", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def cancelar_duelo(self, ctx):
        """Cancela cualquier duelo pendiente tuyo."""
        to_delete = [did for did, d in self.pending_duels.items()
                     if d.get("challenger", {}).id == ctx.author.id
                     or d.get("challenged", {}).id == ctx.author.id]
        for did in to_delete:
            del self.pending_duels[did]
        if to_delete:
            await ctx.send("✅ Duelos pendientes cancelados.")
        else:
            await ctx.send("❌ No tienes duelos pendientes.")

    @commands.command()
    async def jefe_semanal(self, ctx):
        """Desafía al jefe semanal con una de tus cartas."""
        # AQUÍ: pega el comando !jefe_semanal completo desde main.py (línea ~6816)
        # Los cambios necesarios son mínimos: solo reemplazar referencias globales
        # user_last_jefe[user_id] → db.check_cooldown / db.set_cooldown
        await ctx.send("⚠️ Comando en migración — pega el código desde main.py.")

    @commands.command()
    async def eleccion_jefe(self, ctx, numero: int = None):
        """Selecciona tu carta para el jefe semanal."""
        await ctx.send("⚠️ Comando en migración — pega el código desde main.py.")

    @commands.command()
    async def cancelar_jefe(self, ctx):
        """Cancela tu desafío al jefe semanal."""
        await ctx.send("⚠️ Comando en migración — pega el código desde main.py.")


async def setup(bot):
    await bot.add_cog(Duelos(bot))
