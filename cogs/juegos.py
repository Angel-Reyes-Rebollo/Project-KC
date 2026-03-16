"""
cogs/juegos.py — Minijuegos de casino y habilidad.

Comandos: !blackjack, !pedir, !quedarse, !rendirse, !cancelar_bj,
          !ruleta, !adivina, !encuentra_gema
"""

import asyncio
import random
import time

import discord
from discord.ext import commands, tasks

from cogs.utils import (
    APUESTA_MINIMA_BJ, APUESTA_MAXIMA_BJ,
    COOLDOWN_ADIVINA, COOLDOWN_BLACKJACK,
    COOLDOWN_ENCUENTRA_GEMA, COOLDOWN_RULETA,
    add_balance, check_cooldown, format_cooldown,
    format_gems, get_balance, set_cooldown,
)


# ─────────────────────────────────────────
# BLACKJACK
# ─────────────────────────────────────────
class BlackjackGame:
    PAYOUT = {"facil": 1.2, "normal": 1.5, "dificil": 1.7}
    DIFF_INFO = {
        "facil":   {"name": "Fácil",   "multiplier": "1.2x", "color": discord.Color.green()},
        "normal":  {"name": "Normal",  "multiplier": "1.5x", "color": discord.Color.blue()},
        "dificil": {"name": "Difícil", "multiplier": "1.7x", "color": discord.Color.red()},
    }

    def __init__(self, bet: int, difficulty: str):
        self.bet = bet
        self.difficulty = difficulty
        self.deck = self._new_deck()
        self.player_hand: list[str] = []
        self.dealer_hand: list[str] = []
        self.game_over = False
        self.result = None

    def _new_deck(self):
        suits = ["♠️", "♥️", "♦️", "♣️"]
        values = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
        deck = [f"{v}{s}" for s in suits for v in values]
        random.shuffle(deck)
        return deck

    def deal(self):
        if len(self.deck) < 10:
            self.deck = self._new_deck()
        return self.deck.pop()

    def hand_value(self, hand: list[str]) -> int:
        value, aces = 0, 0
        for card in hand:
            v = card[:-2]
            if v in ("J", "Q", "K"): value += 10
            elif v == "A": value += 11; aces += 1
            else: value += int(v)
        while value > 21 and aces:
            value -= 10; aces -= 1
        return value

    def is_blackjack(self, hand):
        return len(hand) == 2 and self.hand_value(hand) == 21

    def determine_winner(self):
        pv = self.hand_value(self.player_hand)
        dv = self.hand_value(self.dealer_hand)
        pb = self.is_blackjack(self.player_hand)
        db_ = self.is_blackjack(self.dealer_hand)
        if db_: return "dealer_blackjack"
        if pb: return "player_blackjack"
        if pv > 21: return "player_bust"
        if dv > 21: return "dealer_bust"
        if dv >= pv: return "dealer_wins"
        return "player_wins"

    @property
    def info(self): return self.DIFF_INFO.get(self.difficulty, self.DIFF_INFO["normal"])


# ─────────────────────────────────────────
# RULETA
# ─────────────────────────────────────────
RULETA_ROJOS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def ruleta_color(n: int) -> str:
    if n == 0: return "Verde"
    return "Rojo" if n in RULETA_ROJOS else "Negro"

def ruleta_color_emoji(n: int) -> str:
    if n == 0: return "🟢 Verde"
    return "🔴 Rojo" if n in RULETA_ROJOS else "⚫ Negro"


# ─────────────────────────────────────────
# ENCUENTRA GEMA — Views
# ─────────────────────────────────────────
active_gem_games: dict = {}


class Ronda1View(discord.ui.View):
    def __init__(self, user_id, game_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.game_id = game_id
        self.winner = random.choice(["A", "B", "C"])

    async def _handle(self, interaction, choice):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No es tu juego.", ephemeral=True)
            return
        for item in self.children: item.disabled = True
        if choice == self.winner:
            active_gem_games[self.game_id]["won_r1"] = True
            embed = discord.Embed(title="🎉 ¡Primera Ronda Ganada!",
                description=f"La gema estaba en **{self.winner}**.\n¿Cobras o doblas?",
                color=discord.Color.green())
            embed.add_field(name="💰 Cobrar", value="40-80 gemas", inline=True)
            embed.add_field(name="🎲 Doblar", value="100-160 o 15-30 consolación", inline=True)
            await interaction.response.edit_message(embed=embed, view=Ronda1DecisionView(self.user_id, self.game_id))
        else:
            if self.game_id in active_gem_games: del active_gem_games[self.game_id]
            embed = discord.Embed(title="❌ Perdiste",
                description=f"La gema estaba en **{self.winner}**.", color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary, emoji="🔵")
    async def a(self, i, b): await self._handle(i, "A")
    @discord.ui.button(label="B", style=discord.ButtonStyle.primary, emoji="🟢")
    async def b(self, i, b): await self._handle(i, "B")
    @discord.ui.button(label="C", style=discord.ButtonStyle.primary, emoji="🔴")
    async def c(self, i, b): await self._handle(i, "C")


class Ronda1DecisionView(discord.ui.View):
    def __init__(self, user_id, game_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.game_id = game_id

    @discord.ui.button(label="💰 Cobrar Ahora", style=discord.ButtonStyle.success)
    async def cobrar(self, interaction, button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No es tu juego.", ephemeral=True); return
        for item in self.children: item.disabled = True
        reward = random.randint(40, 80)
        add_balance(self.user_id, reward)
        if self.game_id in active_gem_games: del active_gem_games[self.game_id]
        embed = discord.Embed(title="💰 ¡Cobrado!", description=f"Ganaste **{format_gems(reward)}**.", color=discord.Color.gold())
        embed.add_field(name="Balance", value=format_gems(get_balance(self.user_id)))
        await interaction.response.edit_message(embed=embed, view=self); self.stop()

    @discord.ui.button(label="🎲 Doblar", style=discord.ButtonStyle.danger)
    async def doblar(self, interaction, button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No es tu juego.", ephemeral=True); return
        for item in self.children: item.disabled = True
        embed = discord.Embed(title="🎲 Ronda 2 — ¡Todo o Nada!",
            description="Elige A, B o C.\n✅ Acierto: 100-160💎 | ❌ Fallo: 15-30💎 consolación",
            color=discord.Color.purple())
        await interaction.response.edit_message(embed=embed, view=Ronda2View(self.user_id, self.game_id))


class Ronda2View(discord.ui.View):
    def __init__(self, user_id, game_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.game_id = game_id
        self.winner = random.choice(["A", "B", "C"])

    async def _handle(self, interaction, choice):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No es tu juego.", ephemeral=True); return
        for item in self.children: item.disabled = True
        if choice == self.winner:
            reward = random.randint(100, 160)
            add_balance(self.user_id, reward)
            embed = discord.Embed(title="🎉 ¡Doble Victoria!", color=discord.Color.green())
            embed.add_field(name="Premio", value=format_gems(reward))
        else:
            consolation = random.randint(15, 30)
            add_balance(self.user_id, consolation)
            embed = discord.Embed(title="😅 Premio de Consolación", color=discord.Color.orange())
            embed.add_field(name="Consolación", value=format_gems(consolation))
        if self.game_id in active_gem_games: del active_gem_games[self.game_id]
        embed.add_field(name="Balance", value=format_gems(get_balance(self.user_id)))
        await interaction.response.edit_message(embed=embed, view=self); self.stop()

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary, emoji="🔵")
    async def a(self, i, b): await self._handle(i, "A")
    @discord.ui.button(label="B", style=discord.ButtonStyle.primary, emoji="🟢")
    async def b(self, i, b): await self._handle(i, "B")
    @discord.ui.button(label="C", style=discord.ButtonStyle.primary, emoji="🔴")
    async def c(self, i, b): await self._handle(i, "C")


# ─────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────
class Juegos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_bj: dict[int, dict] = {}
        self.cleanup_bj.start()

    def cog_unload(self):
        self.cleanup_bj.cancel()

    @tasks.loop(minutes=10)
    async def cleanup_bj(self):
        """Limpia partidas de blackjack que llevan más de 10 minutos activas."""
        now = time.time()
        expired = [uid for uid, data in self.active_bj.items() if now - data["started"] > 600]
        for uid in expired:
            del self.active_bj[uid]

    # ──────────────── BLACKJACK ────────────────

    @commands.command()
    async def blackjack(self, ctx, apuesta: int = None, dificultad: str = None):
        """Inicia un juego de blackjack. Uso: !blackjack <apuesta> <facil|normal|dificil>"""
        user_id = ctx.author.id

        if user_id in self.active_bj:
            await ctx.send("❌ Ya tienes una partida activa. Usa `!cancelar_bj` para cancelarla.")
            return

        if apuesta is None or dificultad is None:
            embed = discord.Embed(title="♠️ BLACKJACK — Ayuda", color=discord.Color.dark_blue())
            embed.add_field(name="Apuesta", value=f"Mínimo: {format_gems(APUESTA_MINIMA_BJ)}\nMáximo: {format_gems(APUESTA_MAXIMA_BJ)}", inline=False)
            embed.add_field(name="Dificultades", value="• `facil` → 1.2x\n• `normal` → 1.5x\n• `dificil` → 1.7x", inline=False)
            embed.add_field(name="Comandos", value="`!pedir` `!quedarse` `!rendirse` `!cancelar_bj`", inline=False)
            embed.add_field(name="Reglas especiales", value="Empate → Dealer gana | Dealer BJ → Dealer gana siempre", inline=False)
            await ctx.send(embed=embed)
            return

        if dificultad not in ("facil", "normal", "dificil"):
            await ctx.send("❌ Dificultad inválida. Usa `facil`, `normal` o `dificil`.")
            return

        if not (APUESTA_MINIMA_BJ <= apuesta <= APUESTA_MAXIMA_BJ):
            await ctx.send(f"❌ Apuesta fuera de rango ({format_gems(APUESTA_MINIMA_BJ)} - {format_gems(APUESTA_MAXIMA_BJ)}).")
            return

        remaining = check_cooldown(user_id, "blackjack", COOLDOWN_BLACKJACK)
        if remaining > 0:
            await ctx.send(f"⏰ Espera **{format_cooldown(remaining)}** para jugar blackjack.")
            return

        balance = get_balance(user_id)
        if balance < apuesta:
            await ctx.send(f"❌ No tienes suficientes gemas. Tienes {format_gems(balance)}.")
            return

        add_balance(user_id, -apuesta)
        set_cooldown(user_id, "blackjack")

        game = BlackjackGame(apuesta, dificultad)
        game.player_hand = [game.deal(), game.deal()]
        game.dealer_hand = [game.deal(), game.deal()]
        self.active_bj[user_id] = {"game": game, "started": time.time()}

        # Comprobar blackjack inmediato
        pb = game.is_blackjack(game.player_hand)
        db_ = game.is_blackjack(game.dealer_hand)

        if db_:
            del self.active_bj[user_id]
            embed = discord.Embed(title="😱 Dealer BLACKJACK — Pierdes", color=discord.Color.red())
            embed.add_field(name="Dealer", value=" ".join(game.dealer_hand))
            embed.add_field(name="Tus cartas", value=" ".join(game.player_hand))
            await ctx.send(embed=embed); return

        if pb:
            win = int(apuesta * game.PAYOUT[dificultad])
            add_balance(user_id, win)
            del self.active_bj[user_id]
            embed = discord.Embed(title="🎉 ¡BLACKJACK! Ganaste", color=discord.Color.green())
            embed.add_field(name="Ganancia", value=format_gems(win))
            await ctx.send(embed=embed); return

        info = game.info
        embed = discord.Embed(title=f"♠️ BLACKJACK — {info['name']}", color=info["color"],
            description=f"Apuesta: {format_gems(apuesta)} | Mult: {info['multiplier']}")
        embed.add_field(name="Dealer", value=f"{game.dealer_hand[0]} ??")
        embed.add_field(name=f"Tu mano ({game.hand_value(game.player_hand)})", value=" ".join(game.player_hand))
        embed.add_field(name="Comandos", value="`!pedir` `!quedarse` `!rendirse` `!cancelar_bj`", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def pedir(self, ctx):
        """Pide una carta en tu partida de blackjack activa."""
        user_id = ctx.author.id
        if user_id not in self.active_bj:
            await ctx.send("❌ No tienes partida activa. Usa `!blackjack` para iniciar."); return
        game = self.active_bj[user_id]["game"]
        game.player_hand.append(game.deal())
        pv = game.hand_value(game.player_hand)
        if pv > 21:
            del self.active_bj[user_id]
            embed = discord.Embed(title="💀 ¡Te pasaste de 21!", color=discord.Color.red(),
                description=f"Tus cartas suman **{pv}**. Perdiste {format_gems(game.bet)}.")
            embed.add_field(name="Dealer", value=" ".join(game.dealer_hand))
            await ctx.send(embed=embed); return
        info = game.info
        embed = discord.Embed(title=f"♠️ BLACKJACK — {info['name']}", color=info["color"])
        embed.add_field(name="Dealer", value=f"{game.dealer_hand[0]} ??")
        embed.add_field(name=f"Tu mano ({pv})", value=" ".join(game.player_hand))
        await ctx.send(embed=embed)

    @commands.command()
    async def quedarse(self, ctx):
        """Plántate y revela el resultado del blackjack."""
        user_id = ctx.author.id
        if user_id not in self.active_bj:
            await ctx.send("❌ No tienes partida activa."); return
        game = self.active_bj[user_id]["game"]
        while game.hand_value(game.dealer_hand) < 17:
            game.dealer_hand.append(game.deal())
        result = game.determine_winner()
        del self.active_bj[user_id]

        pv = game.hand_value(game.player_hand)
        dv = game.hand_value(game.dealer_hand)
        info = game.info

        if result in ("player_wins", "player_blackjack", "dealer_bust"):
            win = int(game.bet * game.PAYOUT[game.difficulty])
            add_balance(user_id, win)
            embed = discord.Embed(title="🎉 ¡Ganaste!", color=discord.Color.green(),
                description=f"Ganaste **{format_gems(win)}**.")
        else:
            embed = discord.Embed(title="😔 Perdiste", color=discord.Color.red(),
                description=f"Perdiste **{format_gems(game.bet)}**.")

        embed.add_field(name=f"Dealer ({dv})", value=" ".join(game.dealer_hand))
        embed.add_field(name=f"Tú ({pv})", value=" ".join(game.player_hand))
        embed.add_field(name="Balance", value=format_gems(get_balance(user_id)))
        await ctx.send(embed=embed)

    @commands.command()
    async def rendirse(self, ctx):
        """Ríndete y recupera la mitad de tu apuesta."""
        user_id = ctx.author.id
        if user_id not in self.active_bj:
            await ctx.send("❌ No tienes partida activa."); return
        game = self.active_bj[user_id]["game"]
        del self.active_bj[user_id]
        refund = game.bet // 2
        add_balance(user_id, refund)
        await ctx.send(f"🏳️ Te rendiste. Se te devolvieron **{format_gems(refund)}**.")

    @commands.command()
    async def cancelar_bj(self, ctx):
        """Cancela tu partida de blackjack activa (sin devolver la apuesta)."""
        user_id = ctx.author.id
        if user_id in self.active_bj:
            del self.active_bj[user_id]
            await ctx.send("🗑️ Partida cancelada. Perdiste tu apuesta.")
        else:
            await ctx.send("❌ No tienes partida activa.")

    # ──────────────── RULETA ────────────────

    @commands.command()
    async def ruleta(self, ctx, apuesta: int = None, numero: int = None):
        """Juega a la ruleta. Uso: !ruleta <apuesta> <número 0-36>"""
        user_id = ctx.author.id

        if apuesta is None or numero is None:
            embed = discord.Embed(title="🎰 RULETA — Ayuda", color=discord.Color.gold())
            embed.add_field(name="Uso", value="`!ruleta <apuesta> <número>`", inline=False)
            embed.add_field(name="Apuesta máxima", value="200 💎", inline=True)
            embed.add_field(name="Números", value="0 al 36", inline=True)
            embed.add_field(name="Premios", value="Color correcto: 1.25x | Número exacto: 1.5x", inline=False)
            await ctx.send(embed=embed); return

        if not (1 <= apuesta <= 200):
            await ctx.send("❌ La apuesta debe ser entre 1 y 200 gemas."); return
        if not (0 <= numero <= 36):
            await ctx.send("❌ El número debe estar entre 0 y 36."); return

        remaining = check_cooldown(user_id, "ruleta", COOLDOWN_RULETA)
        if remaining > 0:
            await ctx.send(f"⏰ Espera **{format_cooldown(remaining)}** para jugar ruleta."); return

        balance = get_balance(user_id)
        if balance < apuesta:
            await ctx.send(f"❌ No tienes {format_gems(apuesta)}. Tienes {format_gems(balance)}."); return

        add_balance(user_id, -apuesta)
        set_cooldown(user_id, "ruleta")

        ganador = random.randint(0, 36)
        color_elegido = ruleta_color(numero)
        color_ganador = ruleta_color(ganador)

        if numero == ganador:
            ganancia = int(apuesta * 1.5)
            add_balance(user_id, ganancia)
            embed = discord.Embed(title="🎉 ¡GANASTE por número exacto!", color=discord.Color.green())
            embed.add_field(name="Ganancia", value=f"+{format_gems(ganancia)} (1.5x)", inline=True)
        elif color_elegido == color_ganador:
            ganancia = int(apuesta * 1.25)
            add_balance(user_id, ganancia)
            embed = discord.Embed(title="🎉 ¡GANASTE por color!", color=discord.Color.green())
            embed.add_field(name="Ganancia", value=f"+{format_gems(ganancia)} (1.25x)", inline=True)
        else:
            embed = discord.Embed(title="😅 Perdiste en la ruleta", color=discord.Color.red())
            embed.add_field(name="Pérdida", value=f"-{format_gems(apuesta)}", inline=True)

        embed.add_field(name="Tu número", value=f"{numero} ({color_elegido})", inline=True)
        embed.add_field(name="Número ganador", value=f"{ganador} ({ruleta_color_emoji(ganador)})", inline=True)
        embed.add_field(name="Balance", value=format_gems(get_balance(user_id)), inline=True)
        await ctx.send(embed=embed)

    # ──────────────── ADIVINA ────────────────

    @commands.command()
    async def adivina(self, ctx):
        """Adivina un número del 1 al 10 en 3 intentos (cooldown 1 hora)."""
        user_id = ctx.author.id
        remaining = check_cooldown(user_id, "adivina", COOLDOWN_ADIVINA)
        if remaining > 0:
            await ctx.send(f"🎯 Espera **{format_cooldown(remaining)}** para volver a jugar."); return

        secreto = random.randint(1, 10)
        intentos = 3
        await ctx.send(f"🎯 **¡Adivina el número!**\n{ctx.author.mention}, entre 1 y 10. Tienes {intentos} intentos.")

        def check(m): return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        set_cooldown(user_id, "adivina")
        while intentos > 0:
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
                intento = int(msg.content)
                if intento == secreto:
                    reward = random.randint(20, 50)
                    add_balance(user_id, reward)
                    await ctx.send(f"🎉 **¡Correcto!** Era {secreto}. Ganaste **{format_gems(reward)}**!")
                    return
                elif intento < secreto:
                    intentos -= 1
                    await ctx.send(f"📈 Más alto. {intentos} intentos restantes." if intentos else f"📈 Era {secreto}. ¡Se acabaron los intentos!")
                else:
                    intentos -= 1
                    await ctx.send(f"📉 Más bajo. {intentos} intentos restantes." if intentos else f"📉 Era {secreto}. ¡Se acabaron los intentos!")
            except asyncio.TimeoutError:
                await ctx.send("⏰ Tiempo agotado."); return

        await ctx.send(f"😢 El número era **{secreto}**. ¡Suerte la próxima!")

    # ──────────────── ENCUENTRA GEMA ────────────────

    @commands.command()
    async def encuentra_gema(self, ctx):
        """Juego interactivo de dos rondas para encontrar gemas (cooldown 2 horas)."""
        user_id = ctx.author.id
        remaining = check_cooldown(user_id, "encuentra_gema", COOLDOWN_ENCUENTRA_GEMA)
        if remaining > 0:
            await ctx.send(f"💎 Espera **{format_cooldown(remaining)}** para buscar gemas."); return

        set_cooldown(user_id, "encuentra_gema")
        game_id = f"{user_id}_{int(time.time())}"
        active_gem_games[game_id] = {"user_id": user_id, "won_r1": False}

        embed = discord.Embed(title="💎 Encuentra la Gema Escondida", color=discord.Color.blue(),
            description="Elige **A, B o C**.\n✅ Ronda 1: cobra (40-80) o dobla\n🎲 Ronda 2: 100-160 o consolación (15-30)")
        embed.set_footer(text="60 segundos por decisión")

        view = Ronda1View(user_id, game_id)
        message = await ctx.send(embed=embed, view=view)

        async def on_timeout():
            if game_id in active_gem_games:
                del active_gem_games[game_id]
            for item in view.children: item.disabled = True
            try: await message.edit(content="⏰ Tiempo agotado.", view=view)
            except: pass
        view.on_timeout = on_timeout


async def setup(bot):
    await bot.add_cog(Juegos(bot))
