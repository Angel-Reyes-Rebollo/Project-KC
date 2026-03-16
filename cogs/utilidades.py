"""
cogs/utilidades.py — Comandos de información y utilidad general.

Comandos: !ayuda, !espera (!cd), !rates, !status, !menu_principal, !top
"""

import discord
from discord.ext import commands
from discord.ui import View

from cogs.utils import (
    COOLDOWN_ADIVINA, COOLDOWN_BLACKJACK, COOLDOWN_CASINO,
    COOLDOWN_DIARIA, COOLDOWN_ENCUENTRA_GEMA, COOLDOWN_GACHA,
    COOLDOWN_MINAR, COOLDOWN_PESCA, COOLDOWN_ROB, COOLDOWN_RULETA,
    COOLDOWN_TRABAJAR, check_cooldown, format_cooldown, format_gems,
    get_balance, get_rarity_emoji, invoke_command_from_interaction,
    rarity_probabilities,
)


class Utilidades(commands.Cog):
    """Comandos informativos y de utilidad."""

    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # !espera / !cd
    # ─────────────────────────────────────────
    @commands.command(aliases=["cd"])
    async def espera(self, ctx):
        """Muestra el tiempo restante de todos tus cooldowns."""
        user_id = ctx.author.id
        cooldowns = [
            ("🎲 Gacha",           "gacha",          COOLDOWN_GACHA),
            ("💼 Trabajar",        "trabajar",        COOLDOWN_TRABAJAR),
            ("🎁 Diaria",          "diaria",          COOLDOWN_DIARIA),
            ("🎯 Adivina",         "adivina",         COOLDOWN_ADIVINA),
            ("🦹 Robo",            "rob",             COOLDOWN_ROB),
            ("🎰 Casino",          "casino",          COOLDOWN_CASINO),
            ("🎣 Pesca",           "pesca",           COOLDOWN_PESCA),
            ("⛏️ Minar",           "minar",           COOLDOWN_MINAR),
            ("💎 Encuentra Gema",  "encuentra_gema",  COOLDOWN_ENCUENTRA_GEMA),
            ("♠️ Blackjack",       "blackjack",       COOLDOWN_BLACKJACK),
            ("🎰 Ruleta",          "ruleta",          COOLDOWN_RULETA),
        ]
        lines = []
        for name, cmd, duration in cooldowns:
            remaining = check_cooldown(user_id, cmd, duration)
            status = "**✅ ¡LISTO!**" if remaining <= 0 else format_cooldown(remaining)
            lines.append(f"• **{name}:** {status}")

        embed = discord.Embed(
            title=f"⏰ Cooldowns de {ctx.author.display_name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="¡Usa los comandos cuando estén listos!")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !rates
    # ─────────────────────────────────────────
    @commands.command()
    async def rates(self, ctx):
        """Muestra las probabilidades actuales del gacha."""
        embed = discord.Embed(title="🎰 Probabilidades del Gacha", color=discord.Color.blue())
        for rarity, prob in sorted(rarity_probabilities.items(), key=lambda x: x[1]):
            embed.add_field(
                name=f"{get_rarity_emoji(rarity)} {rarity}",
                value=f"{prob*100:.2f}%",
                inline=True,
            )
        embed.add_field(name="Total", value=f"{sum(rarity_probabilities.values())*100:.2f}%", inline=False)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !status
    # ─────────────────────────────────────────
    @commands.command()
    async def status(self, ctx):
        """Muestra el estado del bot."""
        embed = discord.Embed(title="📊 Estado del Bot", color=discord.Color.green())
        embed.add_field(name="🤖 Bot", value=f"{self.bot.user}", inline=True)
        embed.add_field(name="🗄️ Base de datos", value="SQLite ✅", inline=True)
        embed.add_field(name="📚 Catálogo", value=f"{len(self.bot.catalog_cards)} cartas", inline=True)
        embed.add_field(name="⏸️ Modo", value="Mantenimiento" if self.bot.paused else "Normal ✅", inline=True)
        embed.add_field(name="🏓 Latencia", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !top
    # ─────────────────────────────────────────
    @commands.command()
    async def top(self, ctx):
        """Muestra el ranking de usuarios con más gemas."""
        balances = self.bot.user_balances
        top_users = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
        embed = discord.Embed(title="🏆 Top 10 — Más Ricos", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, gems) in enumerate(top_users):
            try:
                user = await self.bot.fetch_user(int(uid))
                name = user.display_name
            except Exception:
                name = f"Usuario desconocido"
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{medal} {name} — {format_gems(gems)}")
        embed.description = "\n".join(lines) if lines else "No hay datos todavía."
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !ayuda
    # ─────────────────────────────────────────
    @commands.command()
    async def ayuda(self, ctx):
        """Muestra todos los comandos con descripción y uso, por categorías."""
        es_admin = ctx.author.guild_permissions.administrator

        paginas = []

        # ── Página 1: Gacha & Banners ──
        e = discord.Embed(title="🎲 Gacha & Banners", color=discord.Color.gold())
        e.add_field(name="`!gacha`",
            value="Tirada gratuita del pool general. Cooldown: **4h**.", inline=False)
        e.add_field(name="`!gacha <anime>`",
            value="Tirada gratuita filtrada a un banner.\n"
                  "Ej: `!gacha haikyuu` `!gacha bluelock` `!gacha jjk` `!gacha mha` `!gacha sl` `!gacha aot`",
            inline=False)
        e.add_field(name="`!gacha_comprar <cantidad>`",
            value="Compra tiradas del pool general.\n"
                  "Cantidades: `1` = 50💎 | `5` = 225💎 | `10` = 400💎\n"
                  "Ej: `!gacha_comprar 5`",
            inline=False)
        e.add_field(name="`!gacha_comprar <anime> <cantidad>`",
            value="Compra tiradas filtradas a un banner.\n"
                  "Ej: `!gacha_comprar bluelock 10`",
            inline=False)
        e.add_field(name="`!banners`",
            value="Muestra todos los banners disponibles con su imagen.", inline=False)
        e.add_field(name="`!banner_info <anime>`",
            value="Detalla las cartas de un banner por rareza con probabilidades.\n"
                  "Ej: `!banner_info aot`",
            inline=False)
        paginas.append(e)

        # ── Página 2: Economía ──
        e = discord.Embed(title="💰 Economía", color=discord.Color.green())
        e.add_field(name="`!trabajar`",
            value="Trabaja para ganar entre 20–40💎. Cooldown: **4h**.", inline=False)
        e.add_field(name="`!diaria`",
            value="Reclama tu recompensa diaria de **80💎**. Cooldown: **24h**.", inline=False)
        e.add_field(name="`!casino`",
            value="Gira el tragaperras y gana gemas. Cooldown: **1h**.", inline=False)
        e.add_field(name="`!pesca`",
            value="Lanza la caña y espera a que piquen. Cooldown: **2h**.", inline=False)
        e.add_field(name="`!minar`",
            value="Pica roca en busca de gemas. Cooldown: **1 minuto**.\n"
                  "1% de chance de veta especial (+40💎).",
            inline=False)
        e.add_field(name="`!rob @usuario`",
            value="Intenta robar gemas a otro usuario. Cooldown: **30min**.\n"
                  "60% de fallar y recibir multa + penalización de 15min.",
            inline=False)
        paginas.append(e)

        # ── Página 3: Inventario ──
        e = discord.Embed(title="📦 Inventario & Cartas", color=discord.Color.blue())
        e.add_field(name="`!inventario`",
            value="Muestra tu colección en carrusel con imagen y stats de cada carta.",
            inline=False)
        e.add_field(name="`!vender`",
            value="Vende cartas de tu inventario una por una con carrusel.\n"
                  "Navega con ⬅️ ➡️ y pulsa 💰 Vender en la que quieras.",
            inline=False)
        e.add_field(name="`!vender_rareza <rareza>`",
            value="Vende TODAS las cartas de una rareza de golpe.\n"
                  "Ej: `!vender_rareza N` `!vender_rareza R` `!vender_rareza SSR`",
            inline=False)
        paginas.append(e)

        # ── Página 4: Minijuegos ──
        e = discord.Embed(title="🎮 Minijuegos", color=discord.Color.purple())
        e.add_field(name="`!blackjack <apuesta> <dificultad>`",
            value="Juega al blackjack apostando gemas. Cooldown: **15min**.\n"
                  "Apuesta: 150💎 mín — 2,000💎 máx.\n"
                  "Dificultades: `facil` `normal` `dificil`\n"
                  "Ej: `!blackjack 300 normal`\n"
                  "Durante la partida: `!pedir` `!quedarse` `!rendirse`",
            inline=False)
        e.add_field(name="`!ruleta`",
            value="Apuesta en la ruleta. Cooldown: **5min**.", inline=False)
        e.add_field(name="`!adivina`",
            value="Adivina un número y gana gemas. Cooldown: **1h**.", inline=False)
        e.add_field(name="`!encuentra_gema`",
            value="Encuentra la gema escondida entre las opciones. Cooldown: **2h**.",
            inline=False)
        paginas.append(e)

        # ── Página 5: Duelos & Intercambio ──
        e = discord.Embed(title="⚔️ Duelos & 🔄 Intercambio", color=discord.Color.red())
        e.add_field(name="`!dueloamistoso @usuario`",
            value="Reta a otro jugador a un duelo amistoso de 3 rondas.\n"
                  "Necesitas al menos 3 cartas.", inline=False)
        e.add_field(name="`!cancelar_duelo`",
            value="Cancela cualquier duelo pendiente tuyo.", inline=False)
        e.add_field(name="`!intercambio @usuario`",
            value="Propone un intercambio de cartas con otro jugador.\n"
                  "Ambos deben tener cartas en su inventario.",
            inline=False)
        e.add_field(name="`!cancelar_intercambio`",
            value="Cancela cualquier intercambio pendiente tuyo.", inline=False)
        paginas.append(e)

        # ── Página 6: Recompensas ──
        e = discord.Embed(title="🎁 Recompensas & Eventos", color=discord.Color.orange())
        e.add_field(name="`!recibir_recompensa`",
            value="Reclama la carta de la recompensa temporal activa.\n"
                  "Solo una vez por usuario por evento.",
            inline=False)
        e.add_field(name="`!estado_recompensa`",
            value="Muestra si hay una recompensa activa y cuánto tiempo queda.",
            inline=False)
        e.add_field(name="`!recibir_gemas`",
            value="Reclama la recompensa fija de gemas si está activa.",
            inline=False)
        e.add_field(name="`!eleccion_recompensa <A o B>`",
            value="Vota en la elección global para recibir una de dos cartas.\n"
                  "Ej: `!eleccion_recompensa A`",
            inline=False)
        paginas.append(e)

        # ── Página 7: Utilidades ──
        e = discord.Embed(title="ℹ️ Utilidades", color=discord.Color.blurple())
        e.add_field(name="`!espera` / `!cd`",
            value="Muestra el tiempo restante de todos tus cooldowns de un vistazo.",
            inline=False)
        e.add_field(name="`!rates`",
            value="Muestra las probabilidades actuales de cada rareza en el gacha.",
            inline=False)
        e.add_field(name="`!status`",
            value="Estado del bot: latencia, cartas en catálogo, modo actual.",
            inline=False)
        e.add_field(name="`!top`",
            value="Ranking de los 10 usuarios con más gemas.", inline=False)
        e.add_field(name="`!menu_principal` / `!menu`",
            value="Abre el menú rápido con botones para los comandos más usados.",
            inline=False)
        paginas.append(e)

        # ── Página 8: Admin (solo si es admin) ──
        if es_admin:
            e = discord.Embed(title="👑 Comandos de Administrador", color=discord.Color.dark_gold())
            e.add_field(name="`!dargemas @usuario <cantidad>`",
                value="Da gemas a un usuario. Ej: `!dargemas @user 500`", inline=False)
            e.add_field(name="`!darcarta @usuario <card_id>`",
                value="Da una carta específica del catálogo a un usuario.", inline=False)
            e.add_field(name="`!pausa` / `!continuar`",
                value="Pausa o reanuda el bot para mantenimiento.", inline=False)
            e.add_field(name="`!clear <cantidad>`",
                value="Elimina mensajes del canal. Ej: `!clear 10`", inline=False)
            e.add_field(name="`!backup_now`",
                value="Fuerza un backup inmediato a GitHub.", inline=False)
            e.add_field(name="`!recompensa_tiempo <card_id> <minutos>`",
                value="Activa una recompensa temporal de carta para todos.\n"
                      "Ej: `!recompensa_tiempo SSR001 60`",
                inline=False)
            e.add_field(name="`!eleccion_carta <id1> <id2>`",
                value="Crea una votación global entre dos cartas.\n"
                      "Ej: `!eleccion_carta UR001 SP005`",
                inline=False)
            e.add_field(name="`!gemas_fijas <cantidad> <horas>`",
                value="Activa recompensa de gemas para todos durante X horas.\n"
                      "Ej: `!gemas_fijas 100 24`",
                inline=False)
            e.add_field(name="`!cancelar_recompensa` / `!cancelar_eleccion` / `!cancelar_gemas_fijas`",
                value="Cancela el evento activo correspondiente.", inline=False)
            e.add_field(name="`!estado_gemas_fijas`",
                value="Muestra el estado de la recompensa de gemas activa.", inline=False)
            paginas.append(e)

        # Numerar páginas
        total = len(paginas)
        for i, p in enumerate(paginas):
            p.set_footer(text=f"Página {i+1}/{total} • Project-KC" + (" | Admin 👑" if es_admin else ""))

        view = AyudaView(paginas, ctx.author.id)
        await ctx.send(embed=paginas[0], view=view)

    # ─────────────────────────────────────────
    # !menu_principal
    # ─────────────────────────────────────────
    @commands.command(aliases=["menu", "gachamenu"])
    async def menu_principal(self, ctx):
        """Muestra el menú rápido con botones interactivos."""
        balance = get_balance(ctx.author.id)
        embed = discord.Embed(
            title="🕹️ Menú Rápido",
            description=f"Hola **{ctx.author.display_name}**! Usa los botones para interactuar sin escribir comandos.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="💎 Tu Balance", value=format_gems(balance), inline=False)

        view = MenuPrincipalView(ctx.author.id, self.bot)
        await ctx.send(embed=embed, view=view)


# ─────────────────────────────────────────
# Vista del menú de ayuda (carrusel por categoría)
# ─────────────────────────────────────────
class AyudaView(View):
    def __init__(self, paginas: list, author_id: int, timeout=180):
        super().__init__(timeout=timeout)
        self.paginas = paginas
        self.author_id = author_id
        self.index = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = (self.index == 0)
        self.next_btn.disabled = (self.index == len(self.paginas) - 1)
        self.counter_btn.label = f"{self.index + 1} / {len(self.paginas)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien usó `!ayuda` puede navegar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.paginas[self.index], view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.gray, disabled=True)
    async def counter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.blurple)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.paginas[self.index], view=self)

    @discord.ui.button(label="❌ Cerrar", style=discord.ButtonStyle.red)
    async def cerrar_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


# ─────────────────────────────────────────
# Vista del menú principal
# ─────────────────────────────────────────
class MenuPrincipalView(View):
    def __init__(self, author_id, bot, timeout=180):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.bot = bot

    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo el autor puede usar estos botones.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 Gacha Gratis", style=discord.ButtonStyle.green, row=0)
    async def gacha_free(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "gacha")

    @discord.ui.button(label="💼 Trabajar", style=discord.ButtonStyle.gray, row=0)
    async def trabajar(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "trabajar")

    @discord.ui.button(label="🎁 Diaria", style=discord.ButtonStyle.red, row=0)
    async def diaria(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "diaria")

    @discord.ui.button(label="🎣 Pesca", style=discord.ButtonStyle.secondary, row=0)
    async def pesca(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "pesca")

    @discord.ui.button(label="📦 Inventario", style=discord.ButtonStyle.primary, row=1)
    async def inventario(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "inventario")

    @discord.ui.button(label="⏰ Cooldowns", style=discord.ButtonStyle.secondary, row=1)
    async def cooldowns(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "espera")

    @discord.ui.button(label="❓ Ayuda", style=discord.ButtonStyle.primary, row=1)
    async def ayuda(self, interaction, button):
        await invoke_command_from_interaction(self.bot, interaction, "ayuda")


async def setup(bot):
    await bot.add_cog(Utilidades(bot))
