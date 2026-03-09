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
    COOLDOWN_TRABAJAR, format_cooldown, format_gems, get_balance,
    get_rarity_emoji, invoke_command_from_interaction, rarity_probabilities,
)
from database import db


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
            remaining = db.check_cooldown(user_id, cmd, duration)
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
        top_users = db.get_top_balances(10)
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
        """Muestra todos los comandos disponibles."""
        es_admin = ctx.author.guild_permissions.administrator
        embed = discord.Embed(
            title="🎮 COMANDOS — PROJECT-KC",
            description="Lista completa de comandos. Usa `!ayuda` para ver este menú.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="💰 Economía",
            value="`!gacha` `!gacha_comprar` `!trabajar` `!diaria` `!casino` `!pesca` `!minar` `!rob @usuario`",
            inline=False)
        embed.add_field(name="📦 Inventario",
            value="`!inventario` `!vender` `!vender_mayoreo` `!vender_rareza` `!album` `!mostrar`",
            inline=False)
        embed.add_field(name="🎮 Minijuegos",
            value="`!blackjack` `!ruleta` `!adivina` `!encuentra_gema` `!jefe_semanal`",
            inline=False)
        embed.add_field(name="⚔️ Duelos",
            value="`!dueloamistoso @usuario` `!duelohonor @usuario` `!cancelar_duelo`",
            inline=False)
        embed.add_field(name="🔄 Intercambio",
            value="`!intercambio @usuario` `!cancelar_intercambio`",
            inline=False)
        embed.add_field(name="🎁 Recompensas",
            value="`!recibir_recompensa` `!estado_recompensa` `!recibir_gemas`",
            inline=False)
        embed.add_field(name="ℹ️ Utilidades",
            value="`!espera` / `!cd` `!rates` `!status` `!top` `!menu_principal`",
            inline=False)

        if es_admin:
            embed.add_field(name="👑 Admin",
                value="`!pausa` `!continuar` `!interfaz` `!dargemas` `!quitargemas` `!darcarta` "
                      "`!quitarcarta` `!limpiar_inventario` `!reset_data` `!clear` `!backup_now` "
                      "`!modificar_rates` `!recompensa_tiempo` `!eleccion_carta` `!gemas_fijas`",
                inline=False)

        embed.set_footer(text="¡Buena suerte en el gacha!" + (" | Admin 👑" if es_admin else ""))
        await ctx.send(embed=embed)

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
