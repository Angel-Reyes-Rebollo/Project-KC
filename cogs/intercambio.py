"""
cogs/intercambio.py — Sistema de intercambio entre usuarios.

Este cog contiene el código de intercambio tal como estaba en main.py.
Los sistemas de Views (AcceptRejectView, TradeSelectionView, FinalTradeView)
se mueven aquí directamente desde main.py sin cambios de lógica.

INSTRUCCIONES:
  1. Copia desde main.py las siguientes clases y pégalas en este archivo:
     - AcceptRejectView  (línea ~1529)
     - TradeSelectionView (línea ~1597)
     - FinalTradeView     (línea ~1539 segunda definición)
  2. Copia el comando !intercambio y !cancelar_intercambio
  3. Reemplaza los llamados a funciones antiguas por los de cogs.utils:
     - get_inventory(...)         → ya disponible
     - add_to_inventory(...)      → ya disponible
     - remove_from_inventory_by_index(...) → ya disponible
  4. Cambia @bot.command() por @commands.command() dentro de la clase
  5. Agrega la función setup(bot) al final

Estructura base del cog:
"""

import discord
from discord.ext import commands
from discord.ui import Button, View

from cogs.utils import (
    add_to_inventory, format_gems, get_balance,
    get_inventory, get_rarity_color, get_rarity_emoji,
    remove_from_inventory_by_index,
)

# Estado compartido de intercambios pendientes
pending_trades: dict = {}


class Intercambio(commands.Cog):
    """Sistema de intercambio de cartas entre usuarios."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def intercambio(self, ctx, member: discord.Member = None):
        """Inicia un intercambio con otro usuario. Uso: !intercambio @usuario"""
        if member is None:
            await ctx.send("❌ Debes mencionar a un usuario. Ej: `!intercambio @usuario`")
            return
        if member.id == ctx.author.id:
            await ctx.send("❌ No puedes intercambiar contigo mismo.")
            return
        if member.bot:
            await ctx.send("❌ No puedes intercambiar con un bot.")
            return

        # Verificar inventarios
        inv_author = get_inventory(ctx.author.id)
        inv_member = get_inventory(member.id)
        if not inv_author:
            await ctx.send("❌ No tienes cartas para intercambiar.")
            return
        if not inv_member:
            await ctx.send(f"❌ {member.mention} no tiene cartas para intercambiar.")
            return

        trade_id = f"{ctx.author.id}_{member.id}_{int(__import__('time').time())}"
        pending_trades[trade_id] = {
            "inviter": ctx.author,
            "invited": member,
            "user1_cards": [],
            "user2_cards": [],
            "user1_confirmed": False,
            "user2_confirmed": False,
            "accepted": False,
        }

        embed = discord.Embed(
            title="🔄 Solicitud de Intercambio",
            description=f"{ctx.author.mention} quiere intercambiar cartas con {member.mention}.",
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Expira en 5 minutos")

        # AQUÍ: pega el AcceptRejectView que tenías en main.py
        # y pásale trade_id, ctx.author, member
        # Ejemplo simplificado mientras migras:
        await ctx.send(embed=embed)
        await ctx.send(
            "⚠️ **Migración pendiente:** Pega el código de `AcceptRejectView` aquí.\n"
            "Ver instrucciones al inicio de `cogs/intercambio.py`."
        )

    @commands.command()
    async def cancelar_intercambio(self, ctx):
        """Cancela cualquier intercambio pendiente tuyo."""
        to_delete = [tid for tid, t in pending_trades.items()
                     if t["inviter"].id == ctx.author.id or t["invited"].id == ctx.author.id]
        for tid in to_delete:
            del pending_trades[tid]
        if to_delete:
            await ctx.send("✅ Tus intercambios pendientes fueron cancelados.")
        else:
            await ctx.send("❌ No tienes intercambios pendientes.")


async def setup(bot):
    await bot.add_cog(Intercambio(bot))
