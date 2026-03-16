"""
cogs/gacha.py — Sistema de gacha y gestión de cartas.

Comandos: !gacha, !gacha_comprar, !inventario, !vender, !vender_mayoreo,
          !vender_rareza, !album, !mostrar, !inventario_personal
"""

import os
import random

import discord
from discord.ext import commands
from discord.ui import Button, View

from cogs.utils import (
    COOLDOWN_GACHA,
    add_balance, add_to_inventory, check_cooldown, format_cooldown, format_gems,
    get_balance, get_inventory, get_rarity_color, get_rarity_emoji,
    remove_card_by_id, remove_from_inventory_by_index, rarity_probabilities,
    set_cooldown,
)


# Orden de rareza de mayor a menor (E es la más alta)
RARITY_SORT_INV = {"E": 0, "M": 1, "F": 2, "G": 3, "SP": 4, "UR": 5, "SSR": 6, "R": 7, "N": 8}

STAT_EMOJIS = {
    "Evasion": "👻", "Evasión": "👻",
    "Fuerza": "💥",
    "Reaccion": "🌀", "Reacción": "🌀",
    "Defensa": "🛡️",
    "Velocidad": "💨",
    "IQ": "🧠",
    "Carisma": "✨",
    "Precision": "🎯", "Precisión": "🎯",
    "Energia": "⚡", "Energía": "⚡",
    "Suerte": "🍀",
}

# Barras de stats (10 niveles visuales)
def stat_bar(value: int, max_val: int = 100) -> str:
    filled = round((value / max_val) * 10)
    filled = max(0, min(10, filled))
    return "█" * filled + "░" * (10 - filled)


def build_inventory_embed(card: dict, index: int, total: int, total_all: int,
                           count: int, balance: int, owner_name: str) -> discord.Embed:
    """Construye el embed enriquecido de una carta del inventario."""
    rarity = card.get("rareza", "N")
    emoji = get_rarity_emoji(rarity)
    color = get_rarity_color(rarity)

    # Título con rareza destacada
    embed = discord.Embed(
        title=f"{emoji} {card['nombre']}",
        description=f"**Rareza:** {emoji} `{rarity}`  •  **Valor:** {format_gems(card.get('valor', 0))}",
        color=color,
    )

    # Stats con barras visuales
    stats = card.get("stats", {})
    if stats:
        stats_lines = []
        for stat, val in stats.items():
            stat_emoji = STAT_EMOJIS.get(stat, "•")
            bar = stat_bar(val)
            stats_lines.append(f"{stat_emoji} **{stat}** `{val:>3}` {bar}")
        embed.add_field(
            name="📊 Stats",
            value="\n".join(stats_lines),
            inline=False,
        )

    # Info extra
    if card.get("descripcion"):
        embed.add_field(name="📖 Descripción", value=card["descripcion"], inline=False)

    # Copias en inventario
    if count > 1:
        embed.add_field(name="📦 Copias", value=f"x{count}", inline=True)

    embed.add_field(name="💎 Balance", value=format_gems(balance), inline=True)

    embed.set_footer(
        text=f"Carta {index + 1} / {total} únicas  •  {total_all} total  •  {owner_name}"
    )
    return embed


# ─────────────────────────────────────────
# Vista del carrusel de inventario (mejorada)
# ─────────────────────────────────────────
class InventoryView(View):
    def __init__(self, ctx, inventory: list, card_counts: dict,
                 total_cards: int, balance: int, timeout=300):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.author_id = ctx.author.id
        # Ordenar de mayor a menor rareza
        self.inventory = sorted(
            inventory,
            key=lambda c: RARITY_SORT_INV.get(c.get("rareza", "N"), 99)
        )
        self.card_counts = card_counts
        self.total_cards = total_cards
        self.balance = balance
        self.index = 0
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = (self.index == 0)
        self.next_btn.disabled = (self.index == len(self.inventory) - 1)
        self.counter_btn.label = f"{self.index + 1} / {len(self.inventory)}"

    def _build(self):
        card = self.inventory[self.index]
        count = self.card_counts.get(card.get("id"), 1)
        embed = build_inventory_embed(
            card, self.index, len(self.inventory),
            self.total_cards, count, self.balance,
            self.ctx.author.display_name,
        )
        file = None
        image_path = card.get("imagen", "")
        if image_path and os.path.exists(image_path):
            file = discord.File(image_path, filename="carta.png")
            embed.set_image(url="attachment://carta.png")
        return embed, file

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo el dueño puede navegar.", ephemeral=True
            )
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction):
        self._update_buttons()
        embed, file = self._build()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def send(self):
        embed, file = self._build()
        self._update_buttons()
        if file:
            self.message = await self.ctx.send(embed=embed, file=file, view=self)
        else:
            self.message = await self.ctx.send(embed=embed, view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        await self._refresh(interaction)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.gray, disabled=True, row=0)
    async def counter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.blurple, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        await self._refresh(interaction)

    @discord.ui.button(label="🏆 Mejor carta", style=discord.ButtonStyle.green, row=1)
    async def mejor_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = 0
        await self._refresh(interaction)

    @discord.ui.button(label="❌ Cerrar", style=discord.ButtonStyle.red, row=1)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


# ─────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────
class Gacha(commands.Cog):
    """Comandos de gacha e inventario de cartas."""

    def __init__(self, bot):
        self.bot = bot

    def _pull_card(self) -> dict | None:
        """Selecciona una carta aleatoria según las probabilidades configuradas."""
        cards_catalog = self.bot.cards_catalog
        target_rarities = ["G", "SP", "UR", "SSR", "R", "N"]
        available = [(r, rarity_probabilities[r]) for r in target_rarities
                     if r in cards_catalog and cards_catalog[r] and r in rarity_probabilities]
        if not available:
            return None
        rarities, probs = zip(*available)
        # Normalizar probabilidades
        total = sum(probs)
        probs = [p / total for p in probs]
        chosen_rarity = random.choices(rarities, weights=probs, k=1)[0]
        return random.choice(cards_catalog[chosen_rarity])

    async def _send_card_result(self, ctx, card: dict, cost_label: str = "Tirada gratuita"):
        """Envía el embed con la carta obtenida."""
        rarity = card.get("rareza", "N")
        emoji = get_rarity_emoji(rarity)

        embed = discord.Embed(
            title=f"🎲 Resultado del Gacha",
            description=f"**{emoji} {card['nombre']} ({rarity}) {emoji}**",
            color=get_rarity_color(rarity),
        )
        embed.add_field(name="Rareza", value=rarity, inline=True)
        embed.add_field(name="Valor", value=format_gems(card.get("valor", 0)), inline=True)
        embed.add_field(name="Tipo de tirada", value=cost_label, inline=True)
        if card.get("descripcion"):
            embed.add_field(name="Descripción", value=card["descripcion"], inline=False)

        image_path = card.get("imagen", "")
        if image_path and os.path.exists(image_path):
            file = discord.File(image_path, filename="carta.png")
            embed.set_image(url="attachment://carta.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !gacha
    # ─────────────────────────────────────────
    @commands.command(name="gacha_sin_banner", hidden=True)
    async def gacha(self, ctx):
        """[Reemplazado por gacha_banners] Tirada gratuita de gacha (cooldown 4 horas)."""
        user_id = ctx.author.id
        remaining = check_cooldown(user_id, "gacha", COOLDOWN_GACHA)
        if remaining > 0:
            await ctx.send(f"❌ Ya usaste tu tirada gratuita. Espera **{format_cooldown(remaining)}**.")
            return

        card = self._pull_card()
        if not card:
            await ctx.send("❌ No hay cartas disponibles en el catálogo.")
            return

        set_cooldown(user_id, "gacha")
        add_to_inventory(user_id, card)
        await self._send_card_result(ctx, card, "Tirada gratuita")

    # ─────────────────────────────────────────
    # !gacha_comprar
    # ─────────────────────────────────────────
    @commands.command(name="gacha_comprar_sin_banner", hidden=True)
    async def gacha_comprar(self, ctx, cantidad: int = None):
        """[Reemplazado por gacha_banners] Compra tiradas de gacha con gemas."""
        PRICES = {1: 50, 5: 225, 10: 400}

        if cantidad not in PRICES:
            embed = discord.Embed(
                title="🛒 Comprar Tiradas de Gacha",
                description="Elige cuántas tiradas quieres comprar:",
                color=discord.Color.blue(),
            )
            for qty, price in PRICES.items():
                embed.add_field(name=f"{qty} tirada(s)", value=format_gems(price), inline=True)
            embed.set_footer(text="Uso: !gacha_comprar 1 | 5 | 10")
            await ctx.send(embed=embed)
            return

        user_id = ctx.author.id
        cost = PRICES[cantidad]
        balance = get_balance(user_id)

        if balance < cost:
            await ctx.send(f"❌ No tienes suficientes gemas. Necesitas {format_gems(cost)}, tienes {format_gems(balance)}.")
            return

        add_balance(user_id, -cost)
        cards_obtained = []
        for _ in range(cantidad):
            card = self._pull_card()
            if card:
                add_to_inventory(user_id, card)
                cards_obtained.append(card)

        if not cards_obtained:
            await ctx.send("❌ Error al obtener cartas.")
            return

        if cantidad == 1:
            await self._send_card_result(ctx, cards_obtained[0], f"Comprada ({format_gems(cost)})")
        else:
            embed = discord.Embed(
                title=f"🎲 ¡Obtuviste {len(cards_obtained)} cartas!",
                description=f"Gastaste **{format_gems(cost)}**\nBalance restante: **{format_gems(get_balance(user_id))}**",
                color=discord.Color.gold(),
            )
            for card in cards_obtained:
                rarity = card.get("rareza", "N")
                embed.add_field(
                    name=f"{get_rarity_emoji(rarity)} {card['nombre']}",
                    value=f"Rareza: {rarity} | Valor: {format_gems(card.get('valor', 0))}",
                    inline=False,
                )
            await ctx.send(embed=embed)

    # ─────────────────────────────────────────
    # !inventario
    # ─────────────────────────────────────────
    @commands.command()
    async def inventario(self, ctx):
        """Muestra tu inventario ordenado de mayor a menor rareza con stats y carrusel."""
        user_id = ctx.author.id
        inv = get_inventory(user_id)
        balance = get_balance(user_id)

        if not inv:
            await ctx.send("📭 No tienes cartas en tu inventario. Usa `!gacha` para conseguir una.")
            return

        # Cartas únicas + conteo de copias
        seen = set()
        unique_inv = []
        card_counts: dict[str, int] = {}
        for card in inv:
            cid = card.get("id")
            card_counts[cid] = card_counts.get(cid, 0) + 1
            if cid not in seen:
                seen.add(cid)
                unique_inv.append(card)

        # Resumen por rareza ordenado de mayor a menor
        rarity_summary: dict[str, int] = {}
        for card in inv:
            r = card.get("rareza", "N")
            rarity_summary[r] = rarity_summary.get(r, 0) + 1

        rarity_text = " | ".join(
            f"{get_rarity_emoji(r)} {r}: **{c}**"
            for r, c in sorted(rarity_summary.items(),
                                key=lambda x: RARITY_SORT_INV.get(x[0], 99))
        )

        # Embed resumen
        embed = discord.Embed(
            title=f"📦 Inventario de {ctx.author.display_name}",
            description=rarity_text or "Sin cartas",
            color=discord.Color.gold(),
        )
        embed.add_field(name="💎 Gemas", value=format_gems(balance), inline=True)
        embed.add_field(name="🃏 Total cartas", value=str(len(inv)), inline=True)
        embed.add_field(name="✨ Cartas únicas", value=str(len(unique_inv)), inline=True)
        embed.set_footer(text="Las cartas se muestran de mayor a menor rareza — usa ⬅️ ➡️ para navegar")
        await ctx.send(embed=embed)

        # Carrusel
        view = InventoryView(ctx, unique_inv, card_counts, len(inv), balance)
        await view.send()

    # ─────────────────────────────────────────
    # !vender (carrusel)
    # ─────────────────────────────────────────
    @commands.command()
    async def vender(self, ctx):
        """Vende cartas de tu inventario una por una con un carrusel."""
        user_id = ctx.author.id
        inventory = get_inventory(user_id)

        if not inventory:
            await ctx.send("📭 No tienes cartas para vender.")
            return

        index = [0]

        async def send_card_msg(channel, view=None):
            card = inventory[index[0]]
            rarity = card.get("rareza", "N")
            embed = discord.Embed(
                title=f"{get_rarity_emoji(rarity)} {card['nombre']} ({rarity})",
                description=card.get("descripcion", ""),
                color=get_rarity_color(rarity),
            )
            embed.add_field(name="Valor de venta", value=format_gems(card.get("valor", 0)))
            embed.set_footer(text=f"Carta {index[0] + 1} de {len(inventory)}")

            image_path = card.get("imagen", "")
            if image_path and os.path.exists(image_path):
                file = discord.File(image_path, filename="carta.png")
                embed.set_image(url="attachment://carta.png")
                return await channel.send(embed=embed, file=file, view=view)
            return await channel.send(embed=embed, view=view)

        view = View(timeout=180)

        async def prev_cb(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("❌ Solo el dueño puede navegar.", ephemeral=True)
                return
            index[0] = (index[0] - 1) % len(inventory)
            try: await interaction.message.delete()
            except: pass
            await send_card_msg(interaction.channel, view)

        async def next_cb(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("❌ Solo el dueño puede navegar.", ephemeral=True)
                return
            index[0] = (index[0] + 1) % len(inventory)
            try: await interaction.message.delete()
            except: pass
            await send_card_msg(interaction.channel, view)

        async def sell_cb(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("❌ Solo el dueño puede vender.", ephemeral=True)
                return
            card = remove_from_inventory_by_index(user_id, index[0])
            if card:
                value = card.get("valor", 0)
                add_balance(user_id, value)
                confirm = discord.Embed(
                    title=f"💰 ¡Vendiste {card['nombre']}!",
                    description=f"Ganaste {format_gems(value)}.\nNuevo balance: {format_gems(get_balance(user_id))}",
                    color=discord.Color.gold(),
                )
                await interaction.channel.send(embed=confirm)
                try: await interaction.message.delete()
                except: pass
                view.stop()
            else:
                await interaction.response.send_message("❌ No se pudo vender.", ephemeral=True)

        prev_btn = Button(label="⬅️", style=discord.ButtonStyle.blurple)
        next_btn = Button(label="➡️", style=discord.ButtonStyle.blurple)
        sell_btn = Button(label="💰 Vender", style=discord.ButtonStyle.red)
        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        sell_btn.callback = sell_cb
        view.add_item(prev_btn)
        view.add_item(next_btn)
        view.add_item(sell_btn)

        await send_card_msg(ctx, view)

    # ─────────────────────────────────────────
    # !vender_rareza
    # ─────────────────────────────────────────
    @commands.command()
    async def vender_rareza(self, ctx, rareza: str = None):
        """Vende todas las cartas de una rareza. Ej: !vender_rareza N"""
        if not rareza:
            await ctx.send("❌ Indica la rareza. Ej: `!vender_rareza N`")
            return

        rareza = rareza.upper()
        user_id = ctx.author.id
        inventory = get_inventory(user_id)
        to_sell = [c for c in inventory if c.get("rareza") == rareza]

        if not to_sell:
            await ctx.send(f"📭 No tienes cartas de rareza **{rareza}**.")
            return

        total = sum(c.get("valor", 0) for c in to_sell)
        for card in to_sell:
            remove_card_by_id(user_id, card["id"])
        add_balance(user_id, total)

        embed = discord.Embed(
            title=f"💰 Venta de cartas {rareza}",
            description=f"Vendiste **{len(to_sell)} cartas** de rareza **{rareza}**.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Ganancias", value=format_gems(total), inline=True)
        embed.add_field(name="Nuevo balance", value=format_gems(get_balance(user_id)), inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Gacha(bot))
