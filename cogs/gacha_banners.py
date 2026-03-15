"""
cogs/gacha_banners.py — Sistema de banners de gacha por anime.

Comandos:
  !gacha <anime>        → Tirada gratuita filtrada al anime (cooldown 4h, mismo que !gacha normal)
  !gacha_comprar <anime> <cantidad> → Tirada de pago filtrada al anime
  !banners              → Muestra todos los banners disponibles con sus cartas
  !banner_info <anime>  → Detalles de un banner específico

Uso:
  !gacha haikyuu
  !gacha solo leveling
  !gacha bluelock
  !gacha mha
  !gacha jjk
  !gacha aot
  !banners

HOW TO INSTALL:
  1. Copia este archivo a tu carpeta cogs/ como gacha_banners.py
  2. En main.py, agrega "cogs.gacha_banners" a la lista COGS
  3. Crea una carpeta banners/ en la raíz del proyecto
  4. Agrega las imágenes de banner: banners/haikyuu.png, banners/solo_leveling.png, etc.
     (Opcional — si no existen, el embed igual funciona sin imagen)
  5. El comando !gacha sin argumento sigue funcionando normalmente en cogs/gacha.py
     Si quieres REEMPLAZAR !gacha con este sistema, comenta el @commands.command() en gacha.py
     y descomenta la sección marcada al final de este archivo.
"""

import os
import random

import discord
from discord.ext import commands

from cogs.utils import (
    COOLDOWN_GACHA,
    add_balance, add_to_inventory, format_cooldown, format_gems,
    get_balance, get_rarity_color, get_rarity_emoji,
    rarity_probabilities, check_cooldown, set_cooldown,
)


# ─────────────────────────────────────────
# CONFIGURACIÓN DE BANNERS
#
# Cada entrada define:
#   "nombre"      → Nombre bonito que aparece en los embeds
#   "aliases"     → Palabras que el usuario puede escribir para seleccionarlo
#   "prefijo_ids" → Qué parte del nombre del personaje / descripción identifica al anime
#                   Se compara contra card["nombre"] y card["descripcion"]
#   "banner_img"  → Ruta local de la imagen del banner (carpeta banners/)
#   "color"       → Color del embed (hex int)
#   "emoji"       → Emoji representativo
#   "descripcion" → Texto corto para !banners
# ─────────────────────────────────────────
BANNERS: dict[str, dict] = {
    "haikyuu": {
        "nombre": "Haikyuu!!",
        "aliases": ["haikyuu", "haikyuu!!", "hq", "voleibol", "volleyball"],
        "personajes": [
            # Los nombres EXACTOS o fragmentos únicos de los personajes del anime.
            # Se hace match parcial (lower) contra card["nombre"].
            # NOTA: Se usa "Yu Nishinoya" y "Yū Nishinoya" exactos para no capturar
            # "Momo Nishimiya" de JJK que tiene fragmento similar.
            "Hinata", "Tsukishima", "Yu Nishinoya", "Yū Nishinoya",
            "Ryūnosuke Tanaka", "Ryunosuke Tanaka", "Tadashi Yamaguchi",
            "Yaku", "Iwaizumi", "Kyōtani", "Kyotani", "Raichi", "Wanima",
            "Koganegawa", "Kuroo", "Sawamura", "Azumane", "Haiba",
            "Oikawa", "Shimizu", "Kozume", "Bokuto", "Ushijima",
            "Aone", "Hoshiumi", "Miya", "Kita", "Kageyama", "Suna",
            "Kunimi", "Akaashi",
        ],
        "banner_img": "banners/haikyuu.png",
        "color": 0xF4A620,   # Naranja Karasuno
        "emoji": "🏐",
        "exclusiones": ["Momo Nishimiya"],  # JJK, no Haikyuu
        "descripcion": "¡Cartas del universo de Haikyuu!! Personajes de Karasuno, Aoba Johsai, Fukurodani y más.",
    },
    "solo_leveling": {
        "nombre": "Solo Leveling",
        "aliases": ["solo leveling", "sololeveling", "sl", "solo", "jinwoo"],
        "personajes": [
            "Sung Jin-Woo", "Lee Joo-hee", "Kang Taeshik", "Kim Sangshik",
            "Yoo Jin-Ho", "Cha Hae-In", "Baek Yoonho", "Choi Jong-In",
            "Igris", "Tank", "Beru", "Bellion", "Sung Il-Hwan",
            "Lennart Niermann", "Thomas Andre", "Ashborn", "Monarca",
            "Antares", "Rakan", "Esil Radiru", "Iron",
            "Min Byung-Gyu", "Song Chi-Yul", "Kim Chul", "Hwang Dongsuk",
            "Woo Jin-Chul", "Tusk",
        ],
        "banner_img": "banners/solo_leveling.png",
        "color": 0x6A0DAD,   # Morado oscuro
        "emoji": "⚔️",
        "descripcion": "Surge del abismo y conviértete en el cazador más poderoso del mundo.",
    },
    "bluelock": {
        "nombre": "Blue Lock",
        "aliases": ["bluelock", "blue lock", "bl", "futbol", "fútbol"],
        "personajes": [
            "Isagi", "Gagamaru", "Naruhaya", "Chigiri", "Kunigami",
            "Bachira", "Niko", "Karasu", "Hiori", "Rin Itoshi",
            "Sae Itoshi", "Shidou", "Barou", "Tokimitsu", "Tsurugi",
            "Aiku", "Kaiser", "Adam Blake", "Julian Loki", "Dada Silva",
            "Raichi", "Wanima",
            "Nagi Seishiro", "Reo Mikage", "Kira Ryūsuke",
        ],
        "banner_img": "banners/bluelock.png",
        "color": 0x1A6EFF,   # Azul Blue Lock
        "emoji": "⚽",
        "descripcion": "El programa que forja al delantero más egoísta del mundo.",
    },
    "mha": {
        "nombre": "My Hero Academia",
        "aliases": ["mha", "my hero", "my hero academia", "bnha", "boku no hero", "academia"],
        "personajes": [
            "Ojiro", "Koda", "Shoji", "Tetsutetsu", "Tsunotori",
            "Kaminari", "Mineta", "Sero", "Jiro", "Hagakure",
            "Mt. Lady", "Kamui Woods", "Edgeshot", "Best Jeanist", "Ryukyu",
            "Midoriya", "Bakugo", "Todoroki", "Toga", "Togata", "Mirio",
            "Takami", "Endeavor", "Mirko", "Dabi", "Shigaraki",
            "All For One", "All Might", "Tokoyami",
        ],
        "banner_img": "banners/mha.png",
        "color": 0x00B300,   # Verde heroico
        "emoji": "🦸",
        "descripcion": "Un mundo donde el 80% de la humanidad tiene poderes. ¿Cuál es tu quirk?",
    },
    "jjk": {
        "nombre": "Jujutsu Kaisen",
        "aliases": ["jjk", "jujutsu", "jujutsu kaisen", "jk", "kaisen"],
        "personajes": [
            "Mai Zenin", "Miwa Kasumi", "Momo Nishimiya", "Junpei",
            "Ijichi", "Yaga", "Kamo Noritoshi", "Panda",
            "Nobara", "Kugisaki", "Mei Mei", "Aoi Todo",
            "Maki Zenin", "Megumi Fushiguro", "Gojo", "Satoru",
            "Sukuna", "Yuta", "Okkotsu", "Mahito", "Geto",
            "Kenjaku", "Toji Fushiguro", "Jogo",
        ],
        "banner_img": "banners/jjk.png",
        "color": 0x9B1FFF,   # Morado maldición
        "emoji": "🌀",
        "descripcion": "Maldiciones, hechiceros y técnicas innatas. ¿Sobrevivirás?",
    },
    "crossover": {
        "nombre": "Crossover — Otros Animes",
        "aliases": ["crossover", "otros", "multi", "especial", "other",
                    "chainsaw man", "bleach", "hxh", "one punch", "tokyo ghoul",
                    "sao", "fma", "spy family", "jojo", "evangelion"],
        "personajes": [
            "Chainsaw Man", "Ichigo Kurosaki", "Hisoka Morow",
            "Saitama", "Ken Kaneki", "Kirito", "Edward Elric",
            "Anya Forger", "Jotaro Kujo", "Asuka Langley",
            "Dang Heng", "Neuvillette",
            "Zuko", "Gaara", "Arthur Morgan", "Juvia",
        ],
        "banner_img": "banners/crossover.png",
        "color": 0x2C3E50,   # Gris oscuro premium
        "emoji": "🌐",
        "descripcion": "Personajes especiales de múltiples universos. Cartas raras y exclusivas.",
    },
    "aot": {
        "nombre": "Attack on Titan",
        "aliases": ["aot", "attack on titan", "shingeki", "snk", "titan", "titanes"],
        "personajes": [
            "Eren", "Falco", "Gabi", "Armin", "Carla",
            "Jean Kirstein", "Historia", "Sasha", "Connie", "Rico",
            "Levi", "Mikasa", "Reiner", "Annie", "Pixis",
            "Kenny", "Erwin", "Hange",
            "Titán Colosal", "Titán Bestia", "Titán Acorazado",
            "Titán Hembra", "Titán Mandíbula", "Titán Martillo",
            "Titán de Ataque",
        ],
        "banner_img": "banners/aot.png",
        "color": 0x8B0000,   # Rojo oscuro
        "emoji": "🗡️",
        "descripcion": "La humanidad al borde de la extinción. Lucha o muere dentro de los muros.",
    },
}

# Raridades que participan en el pool de banners (excluye E = Exclusivas de evento)
BANNER_RARITIES = ["G", "SP", "UR", "SSR", "R", "N"]

# Carpeta donde están los banners
BANNERS_DIR = "banners"


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def resolve_banner(query: str) -> dict | None:
    """Devuelve el dict del banner que coincida con el alias, o None."""
    q = query.strip().lower()
    for key, banner in BANNERS.items():
        if q == key or q in [a.lower() for a in banner["aliases"]]:
            return banner
    return None


def get_banner_cards(banner: dict, cards_catalog: dict) -> dict[str, list]:
    """
    Filtra el catálogo global para devolver solo las cartas del anime del banner,
    agrupadas por rareza.
    Hace match parcial de los nombres de personajes del banner contra card["nombre"].
    Respeta la lista opcional "exclusiones" para evitar falsos positivos.
    """
    personajes = [p.lower() for p in banner["personajes"]]
    exclusiones = [e.lower() for e in banner.get("exclusiones", [])]
    filtered: dict[str, list] = {}

    for rarity in BANNER_RARITIES:
        if rarity not in cards_catalog:
            continue
        pool = []
        for card in cards_catalog[rarity]:
            card_name = card.get("nombre", "").lower()
            # Excluir explícitamente cartas que no pertenecen al banner
            if any(exc in card_name for exc in exclusiones):
                continue
            if any(p in card_name for p in personajes):
                pool.append(card)
        if pool:
            filtered[rarity] = pool

    return filtered


def pull_from_banner(banner_cards: dict[str, list]) -> dict | None:
    """
    Selecciona una carta del pool del banner usando las mismas probabilidades
    globales de rarity_probabilities, pero solo entre las rarezas disponibles
    en el pool del banner.
    """
    available = [
        (r, rarity_probabilities[r])
        for r in BANNER_RARITIES
        if r in banner_cards and banner_cards[r] and r in rarity_probabilities
    ]
    if not available:
        return None

    rarities, probs = zip(*available)
    total = sum(probs)
    normalized = [p / total for p in probs]
    chosen_rarity = random.choices(rarities, weights=normalized, k=1)[0]
    return random.choice(banner_cards[chosen_rarity])


def banner_stats(banner_cards: dict[str, list]) -> str:
    """Resumen de cartas por rareza para mostrar en !banner_info."""
    lines = []
    total = 0
    for r in BANNER_RARITIES:
        if r in banner_cards:
            count = len(banner_cards[r])
            total += count
            prob = rarity_probabilities.get(r, 0) * 100
            lines.append(f"{get_rarity_emoji(r)} **{r}** — {count} cartas ({prob:.2f}%)")
    lines.append(f"\n🃏 **Total en banner:** {total} cartas")
    return "\n".join(lines) if lines else "Sin cartas disponibles."


# ─────────────────────────────────────────
# VISTA DE CONFIRMACIÓN DE RESULTADO
# ─────────────────────────────────────────
class BannerResultView(discord.ui.View):
    """Botones que aparecen tras sacar una carta del banner."""

    def __init__(self, author_id: int, anime_key: str, bot, timeout=60):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.anime_key = anime_key
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo el invocador puede usar estos botones.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🔄 Otra tirada", style=discord.ButtonStyle.green)
    async def otra_tirada(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Simula !gacha_comprar <anime> 1 gastando gemas."""
        await interaction.response.defer()
        # Verificar si tiene gemas para 1 tirada (precio: 50)
        balance = get_balance(self.author_id)
        if balance < 50:
            await interaction.followup.send(
                f"❌ No tienes suficientes gemas. Necesitas **50 💎**, tienes **{format_gems(balance)}**.",
                ephemeral=True,
            )
            return

        banner = BANNERS.get(self.anime_key)
        if not banner:
            await interaction.followup.send("❌ Banner no disponible.", ephemeral=True)
            return

        banner_cards = get_banner_cards(banner, self.bot.cards_catalog)
        card = pull_from_banner(banner_cards)
        if not card:
            await interaction.followup.send("❌ Sin cartas en este banner.", ephemeral=True)
            return

        add_balance(self.author_id, -50)
        add_to_inventory(self.author_id, card)

        rarity = card.get("rareza", "N")
        embed = discord.Embed(
            title=f"{banner['emoji']} Banner {banner['nombre']} — Resultado",
            description=f"**{get_rarity_emoji(rarity)} {card['nombre']} ({rarity})**",
            color=banner["color"],
        )
        embed.add_field(name="Valor", value=format_gems(card.get("valor", 0)), inline=True)
        embed.add_field(name="Costo", value=format_gems(50), inline=True)
        embed.add_field(name="Balance", value=format_gems(get_balance(self.author_id)), inline=True)
        embed.set_footer(text=f"Banner: {banner['nombre']}")

        image_path = card.get("imagen", "")
        if image_path and os.path.exists(image_path):
            file = discord.File(image_path, filename="carta.png")
            embed.set_image(url="attachment://carta.png")
            view = BannerResultView(self.author_id, self.anime_key, self.bot)
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            view = BannerResultView(self.author_id, self.anime_key, self.bot)
            await interaction.followup.send(embed=embed, view=view)

    @discord.ui.button(label="📋 Ver banner", style=discord.ButtonStyle.blurple)
    async def ver_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Muestra la info del banner actual."""
        await interaction.response.defer(ephemeral=True)
        banner = BANNERS.get(self.anime_key)
        if not banner:
            await interaction.followup.send("❌ Banner no encontrado.", ephemeral=True)
            return

        banner_cards = get_banner_cards(banner, self.bot.cards_catalog)
        embed = discord.Embed(
            title=f"{banner['emoji']} {banner['nombre']} — Detalle del Banner",
            description=banner["descripcion"],
            color=banner["color"],
        )
        embed.add_field(name="📊 Cartas disponibles", value=banner_stats(banner_cards), inline=False)
        embed.set_footer(text="Usa !gacha_comprar <anime> 5 para tiradas en paquete")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ─────────────────────────────────────────
# CARRUSEL DE MULTI-TIRADA
# ─────────────────────────────────────────

# Orden de rareza de mayor a menor
RARITY_SORT = {"G": 0, "SP": 1, "UR": 2, "SSR": 3, "R": 4, "N": 5, "E": 6, "M": 7, "F": 8}


def build_stats_text(card: dict) -> str:
    """Formatea los stats de una carta en texto legible."""
    stats = card.get("stats", {})
    if not stats:
        return ""
    stat_emojis = {
        "Evasion": "👻", "Fuerza": "💥", "Reaccion": "🌀", "Reacción": "🌀",
        "Defensa": "🛡️", "Velocidad": "💨", "IQ": "🧠", "Carisma": "✨",
        "Precision": "🎯", "Precisión": "🎯", "Energia": "⚡", "Energía": "⚡",
        "Suerte": "🍀",
    }
    lines = []
    for stat, val in stats.items():
        emoji = stat_emojis.get(stat, "•")
        lines.append(f"{emoji} **{stat}:** {val}")
    return "\n".join(lines)


class MultiPullCarouselView(discord.ui.View):
    """Carrusel de navegación para multi-tiradas del banner."""

    def __init__(self, ctx, cards: list, banner: dict, cost: int, balance_after: int, timeout=300):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.author_id = ctx.author.id
        # Ordenar cartas de mayor a menor rareza
        self.cards = sorted(cards, key=lambda c: RARITY_SORT.get(c.get("rareza", "N"), 99))
        self.banner = banner
        self.cost = cost
        self.balance_after = balance_after
        self.index = 0
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = (self.index == 0)
        self.next_btn.disabled = (self.index == len(self.cards) - 1)
        self.counter_btn.label = f"{self.index + 1} / {len(self.cards)}"

    def _build_embed(self) -> tuple[discord.Embed, discord.File | None]:
        card = self.cards[self.index]
        rarity = card.get("rareza", "N")
        emoji = get_rarity_emoji(rarity)

        embed = discord.Embed(
            title=f"{emoji} {card['nombre']} ({rarity})",
            description=card.get("descripcion", ""),
            color=get_rarity_color(rarity),
        )

        # Info básica
        embed.add_field(name="💎 Valor", value=format_gems(card.get("valor", 0)), inline=True)
        embed.add_field(name="⭐ Rareza", value=f"{emoji} {rarity}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # spacer

        # Stats
        stats_text = build_stats_text(card)
        if stats_text:
            embed.add_field(name="📊 Stats", value=stats_text, inline=False)

        # Footer con resumen del pull
        embed.set_footer(
            text=(
                f"Carta {self.index + 1}/{len(self.cards)} • "
                f"Banner: {self.banner['nombre']} • "
                f"Gasto: {format_gems(self.cost)} • "
                f"Balance: {format_gems(self.balance_after)}"
            )
        )

        # Imagen de la carta
        image_path = card.get("imagen", "")
        file = None
        if image_path and os.path.exists(image_path):
            file = discord.File(image_path, filename="carta.png")
            embed.set_image(url="attachment://carta.png")

        return embed, file

    async def _refresh(self, interaction: discord.Interaction):
        self._update_buttons()
        embed, file = self._build_embed()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien hizo el pull puede navegar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.gray, disabled=True, row=0)
    async def counter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # Solo muestra el contador, no hace nada

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.blurple, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.cards) - 1, self.index + 1)
        await self._refresh(interaction)

    @discord.ui.button(label="🏆 Mejor carta", style=discord.ButtonStyle.green, row=1)
    async def mejor_carta(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Salta directo a la carta de mayor rareza (ya es la primera)."""
        self.index = 0
        await self._refresh(interaction)

    @discord.ui.button(label="❌ Cerrar", style=discord.ButtonStyle.red, row=1)
    async def cerrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def send(self):
        """Envía el carrusel con el primer mensaje."""
        embed, file = self._build_embed()
        self._update_buttons()
        if file:
            self.message = await self.ctx.send(embed=embed, file=file, view=self)
        else:
            self.message = await self.ctx.send(embed=embed, view=self)


# ─────────────────────────────────────────
# COG PRINCIPAL
# ─────────────────────────────────────────
class GachaBanners(commands.Cog):
    """Sistema de gacha por banners de anime."""

    def __init__(self, bot):
        self.bot = bot

    # ─── Helpers internos ───

    async def _send_banner_result(
        self,
        ctx_or_channel,
        card: dict,
        banner: dict,
        anime_key: str,
        cost_label: str,
        author_id: int,
    ):
        """Envía embed con el resultado y los botones de acción."""
        rarity = card.get("rareza", "N")
        emoji = get_rarity_emoji(rarity)

        embed = discord.Embed(
            title=f"{banner['emoji']} Banner {banner['nombre']}",
            description=f"**{emoji} {card['nombre']} ({rarity}) {emoji}**",
            color=banner["color"],
        )
        embed.add_field(name="Rareza", value=f"{get_rarity_emoji(rarity)} {rarity}", inline=True)
        embed.add_field(name="Valor", value=format_gems(card.get("valor", 0)), inline=True)
        embed.add_field(name="Tirada", value=cost_label, inline=True)
        embed.set_footer(text=f"Banner: {banner['nombre']} | Usa '🔄 Otra tirada' para seguir")

        # Imagen del banner como thumbnail (si existe)
        banner_img = banner.get("banner_img", "")
        thumbnail_file = None
        if banner_img and os.path.exists(banner_img):
            thumbnail_file = discord.File(banner_img, filename="banner.png")
            embed.set_thumbnail(url="attachment://banner.png")

        # Imagen de la carta como imagen principal
        card_img = card.get("imagen", "")
        card_file = None
        if card_img and os.path.exists(card_img):
            card_file = discord.File(card_img, filename="carta.png")
            embed.set_image(url="attachment://carta.png")

        view = BannerResultView(author_id, anime_key, self.bot)

        files = [f for f in [thumbnail_file, card_file] if f]
        send = ctx_or_channel.send
        if files:
            await send(embed=embed, files=files, view=view)
        else:
            await send(embed=embed, view=view)

    # ─── !gacha <anime> ───

    @commands.command(name="gacha")
    async def gacha(self, ctx, *, anime: str = None):
        """
        Tirada de gacha. Sin argumento → gacha normal (todas las cartas).
        Con argumento → banner del anime indicado.
        Cooldown compartido: 4 horas.

        Ejemplos:
          !gacha
          !gacha haikyuu
          !gacha solo leveling
          !gacha bluelock
          !gacha mha
          !gacha jjk
          !gacha aot
        """
        user_id = ctx.author.id

        # ── Modo banner ──
        if anime:
            # Si el usuario escribió !gacha bluelock 10 por error, ignorar el número
            parts = anime.strip().split()
            if parts and parts[-1].isdigit():
                anime = " ".join(parts[:-1])
                await ctx.send(
                    f"💡 Tip: Para comprar tiradas usa `!gacha_comprar {anime} {parts[-1]}`.\n"
                    f"Haciendo tirada gratuita del banner **{anime}**..."
                )

            banner = resolve_banner(anime)
            if not banner:
                nombres = ", ".join(f"`{b['aliases'][0]}`" for b in BANNERS.values())
                await ctx.send(
                    f"❌ Banner `{anime}` no encontrado.\n"
                    f"Banners disponibles: {nombres}\n"
                    f"También puedes usar `!banners` para ver todos."
                )
                return

            # Cooldown compartido con el gacha normal
            remaining = check_cooldown(user_id, "gacha", COOLDOWN_GACHA)
            if remaining > 0:
                await ctx.send(
                    f"❌ Ya usaste tu tirada gratuita. Espera **{format_cooldown(remaining)}**."
                )
                return

            banner_cards = get_banner_cards(banner, self.bot.cards_catalog)
            if not banner_cards:
                await ctx.send(
                    f"❌ El banner de **{banner['nombre']}** no tiene cartas disponibles en el catálogo.\n"
                    f"Verifica que los nombres de los personajes están bien escritos."
                )
                return

            set_cooldown(user_id, "gacha")
            card = pull_from_banner(banner_cards)
            if not card:
                await ctx.send("❌ Error al sacar carta del banner.")
                return

            # Encontrar la anime_key para BannerResultView
            anime_key = next(
                (k for k, b in BANNERS.items() if b is banner), "unknown"
            )

            add_to_inventory(user_id, card)
            await self._send_banner_result(
                ctx, card, banner, anime_key, "Tirada gratuita", user_id
            )
            return

        # ── Modo normal (sin banner) — delega al gacha original ──
        # Este bloque asegura que !gacha sin argumento sigue funcionando
        # aunque tengas ambos cogs cargados.
        remaining = check_cooldown(user_id, "gacha", COOLDOWN_GACHA)
        if remaining > 0:
            await ctx.send(
                f"❌ Ya usaste tu tirada gratuita. Espera **{format_cooldown(remaining)}**."
            )
            return

        cards_catalog = self.bot.cards_catalog
        target_rarities = ["G", "SP", "UR", "SSR", "R", "N"]
        available = [
            (r, rarity_probabilities[r])
            for r in target_rarities
            if r in cards_catalog and cards_catalog[r] and r in rarity_probabilities
        ]
        if not available:
            await ctx.send("❌ No hay cartas disponibles en el catálogo.")
            return

        rarities, probs = zip(*available)
        total = sum(probs)
        probs = [p / total for p in probs]
        chosen_rarity = random.choices(rarities, weights=probs, k=1)[0]
        card = random.choice(cards_catalog[chosen_rarity])

        set_cooldown(user_id, "gacha")
        add_to_inventory(user_id, card)

        rarity = card.get("rareza", "N")
        embed = discord.Embed(
            title="🎲 Resultado del Gacha",
            description=f"**{get_rarity_emoji(rarity)} {card['nombre']} ({rarity}) {get_rarity_emoji(rarity)}**",
            color=get_rarity_color(rarity),
        )
        embed.add_field(name="Rareza", value=rarity, inline=True)
        embed.add_field(name="Valor", value=format_gems(card.get("valor", 0)), inline=True)
        embed.add_field(name="Tipo de tirada", value="Tirada gratuita", inline=True)
        if card.get("descripcion"):
            embed.add_field(name="Descripción", value=card["descripcion"], inline=False)
        embed.set_footer(text="Tip: !gacha haikyuu para cartas de un anime específico")

        image_path = card.get("imagen", "")
        if image_path and os.path.exists(image_path):
            file = discord.File(image_path, filename="carta.png")
            embed.set_image(url="attachment://carta.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    # ─── !gacha_comprar <anime> <cantidad> ───

    @commands.command(name="gacha_comprar")
    async def gacha_comprar(self, ctx, *, args: str = None):
        """
        Compra tiradas del banner de un anime específico.
        Precios iguales al gacha normal: 1=50💎 5=225💎 10=400💎

        Ejemplos:
          !gacha_comprar haikyuu 1
          !gacha_comprar solo leveling 5
          !gacha_comprar bluelock 10
          !gacha_comprar mha 1
        """
        PRICES = {1: 50, 5: 225, 10: 400}

        if not args:
            embed = discord.Embed(
                title="🛒 Comprar Tiradas de Banner",
                description=(
                    "Compra tiradas del gacha filtradas a un anime.\n"
                    "**Uso:** `!gacha_comprar <anime> <cantidad>`\n\n"
                    "**Ejemplos:**\n"
                    "`!gacha_comprar haikyuu 5`\n"
                    "`!gacha_comprar bluelock 1`\n"
                    "`!gacha_comprar jjk 10`"
                ),
                color=discord.Color.blue(),
            )
            for qty, price in PRICES.items():
                embed.add_field(name=f"{qty} tirada(s)", value=format_gems(price), inline=True)
            embed.add_field(
                name="📋 Banners disponibles",
                value=" | ".join(f"{b['emoji']} {b['nombre']}" for b in BANNERS.values()),
                inline=False,
            )
            embed.set_footer(text="Usa !banners para ver todos los banners en detalle")
            await ctx.send(embed=embed)
            return

        # Parsear: el último token debería ser el número
        parts = args.strip().split()
        try:
            cantidad = int(parts[-1])
            anime_query = " ".join(parts[:-1])
        except (ValueError, IndexError):
            await ctx.send(
                "❌ Formato incorrecto. Ej: `!gacha_comprar haikyuu 5`\n"
                "El número de tiradas va al final."
            )
            return

        if cantidad not in PRICES:
            await ctx.send(
                f"❌ Cantidad inválida. Solo puedes comprar: {', '.join(str(k) for k in PRICES)} tiradas."
            )
            return

        if not anime_query:
            await ctx.send(
                "❌ Debes indicar el anime. Ej: `!gacha_comprar haikyuu 5`\n"
                "Usa `!banners` para ver los disponibles."
            )
            return

        banner = resolve_banner(anime_query)
        if not banner:
            nombres = ", ".join(f"`{b['aliases'][0]}`" for b in BANNERS.values())
            await ctx.send(
                f"❌ Banner `{anime_query}` no encontrado.\n"
                f"Banners disponibles: {nombres}"
            )
            return

        user_id = ctx.author.id
        cost = PRICES[cantidad]
        balance = get_balance(user_id)

        if balance < cost:
            await ctx.send(
                f"❌ No tienes suficientes gemas.\n"
                f"Necesitas: **{format_gems(cost)}** | Tienes: **{format_gems(balance)}**"
            )
            return

        banner_cards = get_banner_cards(banner, self.bot.cards_catalog)
        if not banner_cards:
            await ctx.send(
                f"❌ El banner de **{banner['nombre']}** no tiene cartas disponibles."
            )
            return

        anime_key = next((k for k, b in BANNERS.items() if b is banner), "unknown")

        add_balance(user_id, -cost)
        cards_obtained = []
        for _ in range(cantidad):
            card = pull_from_banner(banner_cards)
            if card:
                add_to_inventory(user_id, card)
                cards_obtained.append(card)

        if not cards_obtained:
            await ctx.send("❌ Error al obtener cartas del banner.")
            return

        if cantidad == 1:
            await self._send_banner_result(
                ctx, cards_obtained[0], banner, anime_key,
                f"Comprada ({format_gems(cost)})", user_id
            )
        else:
            # Multi-tirada: carrusel ordenado de mayor a menor rareza
            carousel = MultiPullCarouselView(
                ctx=ctx,
                cards=cards_obtained,
                banner=banner,
                cost=cost,
                balance_after=get_balance(user_id),
            )
            await carousel.send()

    # ─── !banners ───

    @commands.command(name="banners")
    async def banners(self, ctx):
        """Muestra todos los banners de anime disponibles."""
        embed = discord.Embed(
            title="🎰 Banners de Gacha Disponibles",
            description=(
                "Usa `!gacha <anime>` para una tirada gratuita del banner.\n"
                "Usa `!gacha_comprar <anime> <1|5|10>` para tiradas de pago.\n"
                "El cooldown de la tirada gratuita es de **4 horas** (compartido con `!gacha`)."
            ),
            color=discord.Color.gold(),
        )

        for key, banner in BANNERS.items():
            banner_cards = get_banner_cards(banner, self.bot.cards_catalog)
            total_cards = sum(len(v) for v in banner_cards.values())
            rarities_available = " ".join(
                get_rarity_emoji(r) for r in BANNER_RARITIES if r in banner_cards
            )
            embed.add_field(
                name=f"{banner['emoji']} {banner['nombre']}",
                value=(
                    f"{banner['descripcion']}\n"
                    f"🃏 **{total_cards} cartas** | {rarities_available}\n"
                    f"Uso: `!gacha {key}` | `!banner_info {key}`"
                ),
                inline=False,
            )

        embed.set_footer(text="Usa !banner_info <anime> para ver las cartas exactas de cada banner")
        await ctx.send(embed=embed)

    # ─── !banner_info <anime> ───

    @commands.command(name="banner_info")
    async def banner_info(self, ctx, *, anime: str = None):
        """
        Muestra información detallada de un banner: cartas disponibles por rareza.
        Ejemplo: !banner_info haikyuu
        """
        if not anime:
            await ctx.send(
                "❌ Indica el nombre del anime. Ej: `!banner_info haikyuu`\n"
                "Usa `!banners` para ver todos los disponibles."
            )
            return

        banner = resolve_banner(anime)
        if not banner:
            nombres = ", ".join(f"`{b['aliases'][0]}`" for b in BANNERS.values())
            await ctx.send(
                f"❌ Banner `{anime}` no encontrado.\n"
                f"Disponibles: {nombres}"
            )
            return

        banner_cards = get_banner_cards(banner, self.bot.cards_catalog)

        embed = discord.Embed(
            title=f"{banner['emoji']} Banner: {banner['nombre']}",
            description=banner["descripcion"],
            color=banner["color"],
        )

        # Cartas por rareza
        for rarity in BANNER_RARITIES:
            if rarity not in banner_cards:
                continue
            cards = banner_cards[rarity]
            card_names = ", ".join(c["nombre"] for c in cards)
            prob = rarity_probabilities.get(rarity, 0) * 100
            embed.add_field(
                name=f"{get_rarity_emoji(rarity)} {rarity} — {len(cards)} cartas ({prob:.2f}%)",
                value=card_names if len(card_names) <= 1000 else card_names[:997] + "...",
                inline=False,
            )

        total = sum(len(v) for v in banner_cards.values())
        embed.set_footer(
            text=(
                f"Total: {total} cartas en el banner | "
                f"!gacha {anime.split()[0]} → tirada gratuita | "
                f"!gacha_comprar {anime.split()[0]} 10 → 10 tiradas"
            )
        )

        # Imagen del banner
        banner_img = banner.get("banner_img", "")
        if banner_img and os.path.exists(banner_img):
            file = discord.File(banner_img, filename="banner.png")
            embed.set_image(url="attachment://banner.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GachaBanners(bot))
