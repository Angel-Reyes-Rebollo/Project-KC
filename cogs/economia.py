"""
cogs/economia.py — Comandos de economía y gemas.

Comandos: !trabajar, !diaria, !casino, !pesca, !minar, !rob
"""

import asyncio
import random
import time

import discord
from discord.ext import commands

from cogs.utils import (
    COOLDOWN_CASINO, COOLDOWN_DIARIA, COOLDOWN_MINAR,
    COOLDOWN_PESCA, COOLDOWN_ROB, COOLDOWN_TRABAJAR,
    add_balance, format_cooldown, format_gems,
    get_balance, has_rob_penalty, get_rob_penalty_time,
    set_rob_penalty, get_inventory, save_data,
)
from database import db


class Economia(commands.Cog):
    """Comandos de economía: trabajo, recompensas diarias, minijuegos de gemas."""

    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # !trabajar
    # ─────────────────────────────────────────
    @commands.command()
    async def trabajar(self, ctx):
        """Trabaja para ganar entre 20 y 40 gemas (cooldown 4 horas)."""
        user_id = ctx.author.id
        remaining = db.check_cooldown(user_id, "trabajar", COOLDOWN_TRABAJAR)
        if remaining > 0:
            await ctx.send(f"💼 Ya trabajaste recientemente. Vuelve en **{format_cooldown(remaining)}**.")
            return

        db.set_cooldown(user_id, "trabajar")
        reward = random.randint(20, 40)
        add_balance(user_id, reward)

        jobs = [
            "repartiste pizzas 🍕",
            "vendiste limonada 🍋",
            "cuidaste un jardín 🌱",
            "lavaste carros 🚗",
            "diste clases de música 🎵",
        ]
        embed = discord.Embed(
            title="💼 ¡Trabajo completado!",
            description=f"{ctx.author.mention} {random.choice(jobs)} y ganó **{format_gems(reward)}**.",
            color=discord.Color.green(),
        )
        embed.add_field(name="💰 Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo trabajo en {format_cooldown(COOLDOWN_TRABAJAR)}")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !diaria
    # ─────────────────────────────────────────
    @commands.command()
    async def diaria(self, ctx):
        """Reclama tu recompensa diaria de 80 gemas (cooldown 24 horas)."""
        user_id = ctx.author.id
        remaining = db.check_cooldown(user_id, "diaria", COOLDOWN_DIARIA)
        if remaining > 0:
            await ctx.send(f"🎁 Ya reclamaste tu diaria. Vuelve en **{format_cooldown(remaining)}**.")
            return

        db.set_cooldown(user_id, "diaria")
        reward = 80
        add_balance(user_id, reward)

        embed = discord.Embed(
            title="🎁 ¡Recompensa Diaria!",
            description=f"{ctx.author.mention} ha reclamado sus **{format_gems(reward)}** diarios.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="💰 Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text="Vuelve mañana para tu próxima recompensa")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !casino (tragaperras)
    # ─────────────────────────────────────────
    @commands.command()
    async def casino(self, ctx):
        """Juega a la tragaperras y gana entre 25 y 50 gemas (cooldown 1 hora)."""
        user_id = ctx.author.id
        remaining = db.check_cooldown(user_id, "casino", COOLDOWN_CASINO)
        if remaining > 0:
            await ctx.send(f"🎰 Debes esperar **{format_cooldown(remaining)}** para volver al casino.")
            return

        db.set_cooldown(user_id, "casino")

        SYMBOLS = ["🍒", "🍋", "7️⃣", "💰", "💎", "⭐"]
        result = [random.choice(SYMBOLS) for _ in range(3)]
        is_jackpot = result[0] == result[1] == result[2]
        has_pair = result[0] == result[1] or result[1] == result[2] or result[0] == result[2]

        if is_jackpot:
            reward = 50
            title, color = "🎉 ¡JACKPOT!", discord.Color.gold()
            desc = "¡Tres iguales! Recompensa máxima."
        elif has_pair:
            reward = random.randint(35, 49)
            title, color = "🎰 ¡Casi!", discord.Color.orange()
            desc = "Dos iguales. ¡Casi lo logras!"
        else:
            reward = random.randint(25, 34)
            title, color = "🎰 Girando...", discord.Color.blue()
            desc = "Participación premiada."

        add_balance(user_id, reward)

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.add_field(name="Tragaperras", value=f"**{' | '.join(result)}**", inline=False)
        embed.add_field(name="🎁 Recompensa", value=format_gems(reward), inline=True)
        embed.add_field(name="💰 Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo casino en {format_cooldown(COOLDOWN_CASINO)}")
        await ctx.send(f"{ctx.author.mention} tiró de la palanca...", embed=embed)

    # ─────────────────────────────────────────
    # !pesca
    # ─────────────────────────────────────────
    @commands.command()
    async def pesca(self, ctx):
        """Minijuego de pesca: 70% éxito, gana 15-25 gemas (cooldown 2 horas)."""
        user_id = ctx.author.id
        remaining = db.check_cooldown(user_id, "pesca", COOLDOWN_PESCA)
        if remaining > 0:
            await ctx.send(f"🎣 ¡Aún no pican! Espera **{format_cooldown(remaining)}**.")
            return

        db.set_cooldown(user_id, "pesca")
        msg = await ctx.send("🎣 **Lanzando la caña...** esperando que piquen...")
        await asyncio.sleep(2)

        if random.random() < 0.30:
            fails = [
                "¡El pez era demasiado rápido! 😭",
                "¡Tu sedal se rompió! 💢",
                "Solo sacaste una bota vieja. 🥾",
                "Un pájaro se llevó tu carnada. 🐦",
            ]
            await msg.edit(content=f"🎣 **¡Oh no!** {random.choice(fails)}\nPróxima pesca en {format_cooldown(COOLDOWN_PESCA)}")
        else:
            winnings = random.randint(15, 25)
            add_balance(user_id, winnings)
            successes = [
                f"¡Sacaste un salmón gigante! +{format_gems(winnings)} 🐟",
                f"¡Pescaste una trucha brillante! +{format_gems(winnings)} ✨",
                f"¡Un pez dorado cayó en tu red! +{format_gems(winnings)} 🎣",
            ]
            await msg.edit(
                content=f"🎉 **¡Felicidades!** {random.choice(successes)}\n"
                        f"💰 Balance: {format_gems(get_balance(user_id))}\n"
                        f"⏰ Próxima pesca: {format_cooldown(COOLDOWN_PESCA)}"
            )

    # ─────────────────────────────────────────
    # !minar
    # ─────────────────────────────────────────
    @commands.command()
    async def minar(self, ctx):
        """Mina gemas: 1% = 40 gemas, 99% = 1 gema (cooldown 1 minuto)."""
        user_id = ctx.author.id
        remaining = db.check_cooldown(user_id, "minar", COOLDOWN_MINAR)
        if remaining > 0:
            await ctx.send(f"⛏️ Espera **{format_cooldown(remaining)}** antes de minar.")
            return

        db.set_cooldown(user_id, "minar")

        if random.random() <= 0.01:
            reward = 40
            add_balance(user_id, reward)
            embed = discord.Embed(
                title="💎 ¡VETA DE CRISTAL RARO!",
                description=f"{ctx.author.mention} encontró **{format_gems(reward)}**!",
                color=discord.Color.green(),
            )
            embed.add_field(name="Ganancia", value=f"+{format_gems(reward)}", inline=True)
        else:
            reward = 1
            add_balance(user_id, reward)
            fails = [
                "Solo encontraste grava.",
                "La roca era muy dura, pero tienes 1 gema por el esfuerzo.",
                "Tu pico se rompió, pero hay una pequeña gema.",
            ]
            embed = discord.Embed(
                title="⛏️ Intento Fallido...",
                description=f"{ctx.author.mention}, {random.choice(fails)}",
                color=discord.Color.red(),
            )
            embed.add_field(name="Consuelo", value=f"+{format_gems(reward)}", inline=True)

        embed.add_field(name="Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo minar en {format_cooldown(COOLDOWN_MINAR)}")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !rob
    # ─────────────────────────────────────────
    @commands.command()
    async def rob(self, ctx, member: discord.Member = None):
        """Intenta robar gemas a otro usuario (cooldown 30 minutos)."""
        user_id = ctx.author.id

        if member is None:
            await ctx.send("❌ Debes mencionar a quien quieres robar. Ej: `!rob @usuario`")
            return
        if member.id == user_id:
            await ctx.send("❌ No puedes robarte a ti mismo.")
            return
        if member.bot:
            await ctx.send("❌ No puedes robar a un bot.")
            return

        # Verificar penalización
        if has_rob_penalty(user_id):
            remaining = get_rob_penalty_time(user_id) - time.time()
            await ctx.send(f"🚨 Estás bajo vigilancia policial. Espera **{format_cooldown(remaining)}**.")
            return

        # Verificar cooldown
        remaining = db.check_cooldown(user_id, "rob", COOLDOWN_ROB)
        if remaining > 0:
            await ctx.send(f"🦹 Ya intentaste robar recientemente. Espera **{format_cooldown(remaining)}**.")
            return

        victim_balance = get_balance(member.id)
        if victim_balance < 10:
            await ctx.send(f"❌ {member.mention} no tiene suficientes gemas para robar.")
            return

        db.set_cooldown(user_id, "rob")

        # 40% éxito, 60% fracaso
        if random.random() < 0.40:
            stolen = random.randint(10, min(50, victim_balance))
            add_balance(member.id, -stolen)
            add_balance(user_id, stolen)
            embed = discord.Embed(
                title="🦹 ¡Robo Exitoso!",
                description=f"{ctx.author.mention} le robó **{format_gems(stolen)}** a {member.mention}.",
                color=discord.Color.dark_red(),
            )
            embed.add_field(name="Tu balance", value=format_gems(get_balance(user_id)), inline=True)
        else:
            # Penalización: 15 minutos
            penalty_duration = 15 * 60
            set_rob_penalty(user_id, time.time() + penalty_duration)
            fine = random.randint(5, 20)
            add_balance(user_id, -min(fine, get_balance(user_id)))
            embed = discord.Embed(
                title="🚨 ¡Te Atraparon!",
                description=f"{ctx.author.mention} fue capturado intentando robar a {member.mention}.",
                color=discord.Color.red(),
            )
            embed.add_field(name="Multa", value=f"-{format_gems(fine)}", inline=True)
            embed.add_field(name="Penalización", value=format_cooldown(penalty_duration), inline=True)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Economia(bot))
