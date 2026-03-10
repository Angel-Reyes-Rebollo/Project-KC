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
    set_rob_penalty,
)


class Economia(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.last_trabajar: dict = {}
        self.last_diaria:   dict = {}
        self.last_casino:   dict = {}
        self.last_pesca:    dict = {}
        self.last_minar:    dict = {}
        self.last_rob:      dict = {}

    @commands.command()
    async def trabajar(self, ctx):
        user_id = ctx.author.id
        now = time.time()
        if user_id in self.last_trabajar and now - self.last_trabajar[user_id] < COOLDOWN_TRABAJAR:
            remaining = COOLDOWN_TRABAJAR - (now - self.last_trabajar[user_id])
            await ctx.send(f"💼 Ya trabajaste recientemente. Vuelve en **{format_cooldown(remaining)}**.")
            return
        self.last_trabajar[user_id] = now
        reward = random.randint(20, 40)
        add_balance(user_id, reward)
        jobs = ["repartiste pizzas 🍕","vendiste limonada 🍋","cuidaste un jardín 🌱","lavaste carros 🚗","diste clases de música 🎵"]
        embed = discord.Embed(title="💼 ¡Trabajo completado!", description=f"{ctx.author.mention} {random.choice(jobs)} y ganó **{format_gems(reward)}**.", color=discord.Color.green())
        embed.add_field(name="💰 Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo trabajo en {format_cooldown(COOLDOWN_TRABAJAR)}")
        await ctx.send(embed=embed)

    @commands.command()
    async def diaria(self, ctx):
        user_id = ctx.author.id
        now = time.time()
        if user_id in self.last_diaria and now - self.last_diaria[user_id] < COOLDOWN_DIARIA:
            remaining = COOLDOWN_DIARIA - (now - self.last_diaria[user_id])
            await ctx.send(f"🎁 Ya reclamaste tu diaria. Vuelve en **{format_cooldown(remaining)}**.")
            return
        self.last_diaria[user_id] = now
        reward = 80
        add_balance(user_id, reward)
        embed = discord.Embed(title="🎁 ¡Recompensa Diaria!", description=f"{ctx.author.mention} ha reclamado sus **{format_gems(reward)}** diarios.", color=discord.Color.gold())
        embed.add_field(name="💰 Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text="Vuelve mañana para tu próxima recompensa")
        await ctx.send(embed=embed)

    @commands.command()
    async def casino(self, ctx):
        user_id = ctx.author.id
        now = time.time()
        if user_id in self.last_casino and now - self.last_casino[user_id] < COOLDOWN_CASINO:
            remaining = COOLDOWN_CASINO - (now - self.last_casino[user_id])
            await ctx.send(f"🎰 Debes esperar **{format_cooldown(remaining)}** para volver al casino.")
            return
        self.last_casino[user_id] = now
        SYMBOLS = ["🍒","🍋","7️⃣","💰","💎","⭐"]
        result = [random.choice(SYMBOLS) for _ in range(3)]
        is_jackpot = result[0] == result[1] == result[2]
        has_pair = result[0]==result[1] or result[1]==result[2] or result[0]==result[2]
        if is_jackpot:
            reward, title, color, desc = 50, "🎉 ¡JACKPOT!", discord.Color.gold(), "¡Tres iguales! Recompensa máxima."
        elif has_pair:
            reward, title, color, desc = random.randint(35,49), "🎰 ¡Casi!", discord.Color.orange(), "Dos iguales."
        else:
            reward, title, color, desc = random.randint(25,34), "🎰 Girando...", discord.Color.blue(), "Participación premiada."
        add_balance(user_id, reward)
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.add_field(name="Tragaperras", value=f"**{' | '.join(result)}**", inline=False)
        embed.add_field(name="🎁 Recompensa", value=format_gems(reward), inline=True)
        embed.add_field(name="💰 Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo casino en {format_cooldown(COOLDOWN_CASINO)}")
        await ctx.send(f"{ctx.author.mention} tiró de la palanca...", embed=embed)

    @commands.command()
    async def pesca(self, ctx):
        user_id = ctx.author.id
        now = time.time()
        if user_id in self.last_pesca and now - self.last_pesca[user_id] < COOLDOWN_PESCA:
            remaining = COOLDOWN_PESCA - (now - self.last_pesca[user_id])
            await ctx.send(f"🎣 ¡Aún no pican! Espera **{format_cooldown(remaining)}**.")
            return
        self.last_pesca[user_id] = now
        msg = await ctx.send("🎣 **Lanzando la caña...** esperando que piquen...")
        await asyncio.sleep(2)
        if random.random() < 0.30:
            fails = ["¡El pez era demasiado rápido! 😭","¡Tu sedal se rompió! 💢","Solo sacaste una bota vieja. 🥾","Un pájaro se llevó tu carnada. 🐦"]
            await msg.edit(content=f"🎣 **¡Oh no!** {random.choice(fails)}\nPróxima pesca en {format_cooldown(COOLDOWN_PESCA)}")
        else:
            winnings = random.randint(15, 25)
            add_balance(user_id, winnings)
            successes = [f"¡Sacaste un salmón gigante! +{format_gems(winnings)} 🐟",f"¡Pescaste una trucha brillante! +{format_gems(winnings)} ✨",f"¡Un pez dorado cayó en tu red! +{format_gems(winnings)} 🎣"]
            await msg.edit(content=f"🎉 **¡Felicidades!** {random.choice(successes)}\n💰 Balance: {format_gems(get_balance(user_id))}\n⏰ Próxima pesca: {format_cooldown(COOLDOWN_PESCA)}")

    @commands.command()
    async def minar(self, ctx):
        user_id = ctx.author.id
        now = time.time()
        if user_id in self.last_minar and now - self.last_minar[user_id] < COOLDOWN_MINAR:
            remaining = COOLDOWN_MINAR - (now - self.last_minar[user_id])
            await ctx.send(f"⛏️ Espera **{format_cooldown(remaining)}** antes de minar.")
            return
        self.last_minar[user_id] = now
        if random.random() <= 0.01:
            reward = 40
            add_balance(user_id, reward)
            embed = discord.Embed(title="💎 ¡VETA DE CRISTAL RARO!", description=f"{ctx.author.mention} encontró **{format_gems(reward)}**!", color=discord.Color.green())
            embed.add_field(name="Ganancia", value=f"+{format_gems(reward)}", inline=True)
        else:
            reward = 1
            add_balance(user_id, reward)
            fails = ["Solo encontraste grava.","La roca era muy dura, pero tienes 1 gema.","Tu pico se rompió, pero hay una pequeña gema."]
            embed = discord.Embed(title="⛏️ Intento Fallido...", description=f"{ctx.author.mention}, {random.choice(fails)}", color=discord.Color.red())
            embed.add_field(name="Consuelo", value=f"+{format_gems(reward)}", inline=True)
        embed.add_field(name="Balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo minar en {format_cooldown(COOLDOWN_MINAR)}")
        await ctx.send(embed=embed)

    @commands.command()
    async def rob(self, ctx, member: discord.Member = None):
        user_id = ctx.author.id
        now = time.time()
        if member is None:
            await ctx.send("❌ Menciona a quien quieres robar. Ej: `!rob @usuario`"); return
        if member.id == user_id:
            await ctx.send("❌ No puedes robarte a ti mismo."); return
        if member.bot:
            await ctx.send("❌ No puedes robar a un bot."); return
        if has_rob_penalty(user_id):
            remaining = get_rob_penalty_time(user_id) - now
            await ctx.send(f"🚨 Estás bajo vigilancia policial. Espera **{format_cooldown(remaining)}**."); return
        if user_id in self.last_rob and now - self.last_rob[user_id] < COOLDOWN_ROB:
            remaining = COOLDOWN_ROB - (now - self.last_rob[user_id])
            await ctx.send(f"🦹 Ya intentaste robar. Espera **{format_cooldown(remaining)}**."); return
        victim_balance = get_balance(member.id)
        if victim_balance < 10:
            await ctx.send(f"❌ {member.mention} no tiene suficientes gemas para robar."); return
        self.last_rob[user_id] = now
        if random.random() < 0.40:
            stolen = random.randint(10, min(50, victim_balance))
            add_balance(member.id, -stolen)
            add_balance(user_id, stolen)
            embed = discord.Embed(title="🦹 ¡Robo Exitoso!", description=f"{ctx.author.mention} le robó **{format_gems(stolen)}** a {member.mention}.", color=discord.Color.dark_red())
            embed.add_field(name="Tu balance", value=format_gems(get_balance(user_id)), inline=True)
        else:
            penalty_duration = 15 * 60
            set_rob_penalty(user_id, now + penalty_duration)
            fine = random.randint(5, 20)
            add_balance(user_id, -min(fine, get_balance(user_id)))
            embed = discord.Embed(title="🚨 ¡Te Atraparon!", description=f"{ctx.author.mention} fue capturado intentando robar a {member.mention}.", color=discord.Color.red())
            embed.add_field(name="Multa", value=f"-{format_gems(fine)}", inline=True)
            embed.add_field(name="Penalización", value=format_cooldown(penalty_duration), inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Economia(bot))
