import asyncio
import json
import os
import random
import time

import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View

# ----------------------------
# Archivos de datos a crear
# ----------------------------
CATALOG_FILE = "catalogo.json"
DATA_FILE = "data.json"

# ----------------------------
# Cargar catálogo desde JSON
# ----------------------------
with open(CATALOG_FILE, "r", encoding="utf-8") as f:
    catalog_data = json.load(f)

# lista plana de cartas
catalog_cards = catalog_data.get("cards", [])

# Organizar cartas por rareza
cards_catalog = {}
for card in catalog_cards:
    rarity = card.get("rareza", "N")
    cards_catalog.setdefault(rarity, []).append(card)

# Nuevas probabilidades que incluyen UR, SP y L
rarity_probabilities = {
    "G": 0.010,   # Galaxia (1%) - Aumentado de 0.5%
    "SP": 0.020,  # Special (2%) - Aumentado de 1%
    "UR": 0.030,  # Ultra Raro (3%) - Aumentado de 1.5%
    "SSR": 0.060, # Super Super Raro (6%) - Aumentado de 3%
    "R": 0.120,  # Super Raro (12%) - Aumentado de 6%
    "N": 0.400,   # Normal (40%) - Aumentado de 20%
}

# ----------------------------
# Cargar inventarios/monedas persistentes
# ----------------------------
# En la sección de carga de datos persistentes, reemplaza con:
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
        user_inventories = user_data.get("inventories", {})
        user_balances = user_data.get("balances", {})
        user_rob_penalties = user_data.get("rob_penalties", {})
        user_completed_floors = user_data.get("completed_floors", {})  # Esta línea debe estar
else:
    user_inventories = {}
    user_balances = {}
    user_rob_penalties = {}
    user_completed_floors = {}  # Y esta también

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "inventories": user_inventories,
            "balances": user_balances,
            "rob_penalties": user_rob_penalties,
            "completed_floors": user_completed_floors  # Asegúrate de que esta línea esté presente
        }, f, ensure_ascii=False, indent=4)

        

# ----------------------------
# Inicialización del bot
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True  # necesario si usas comandos por mensajes

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# Estado de Pausa Global
# ----------------------------
bot_paused = False # Controla si el bot está en modo mantenimiento

# ----------------------------
# CHECK GLOBAL DE PAUSA
# ----------------------------
@bot.check
async def global_commands_check(ctx):
    """Bloquea comandos si el bot está pausado, excepto para admins o comandos de control."""
    global bot_paused
    
    # Comandos que deben funcionar incluso en pausa (Admin commands para reactivar)
    allowed_commands = ["pausa", "continuar", "reanudar"]
    
    # Si el bot NO está pausado, permite la ejecución.
    if not bot_paused:
        return True

    # Si el usuario es administrador (tiene permisos de administrador), permite.
    if ctx.author.guild_permissions.administrator:
        return True

    # Si el bot está pausado y el usuario NO es admin:
    # 1. Verifica si el comando es de la lista blanca.
    if ctx.command and ctx.command.name in allowed_commands:
        return True
    
    # 2. Si es un comando cualquiera y el bot está pausado, lo bloquea y notifica.
    embed = discord.Embed(
        title="❌ Bot Pausado por Mantenimiento",
        description="El bot se encuentra actualmente en modo de mantenimiento. Solo los administradores pueden usar comandos.",
        color=discord.Color.red()
    )
    # Enviar solo si no está en un DM para evitar errores.
    if ctx.guild:
        await ctx.send(embed=embed)
    return False


# Tiempos / cooldowns
user_last_trabajar = {}    # {user_id: timestamp}
user_last_daily = {}   # {user_id: timestamp}
user_last_gacha = {}   # {user_id: timestamp}
user_last_adivina = {} # {user_id: timestamp}
user_last_rob = {}     # {user_id: timestamp}
user_last_casino = {}  # {user_id: timestamp}
user_last_pesca = {}       # {user_id: timestamp}
user_last_minar = {}   # {user_id: timestamp}
user_last_jefe = {}  


# ----------------------------
# CONSTANTES Y COMANDO !ESPERA
# ----------------------------

# CONSTANTES DE COOLDOWNS (en segundos)
COOLDOWN_DIARIA = 24 * 3600    # !diaria (24 horas)
COOLDOWN_GACHA = 4 * 3600      # !gacha (4 horas)
COOLDOWN_ADIVINA = 1 * 3600    # !adivina (1 hora)
COOLDOWN_ROB = 30 * 60         # !rob (30 minutos)
COOLDOWN_TRABAJAR = 4 * 3600   # !trabajar (4 horas)
COOLDOWN_CASINO = 1 * 3600     # !casino (1 hora) <--- NUEVO
COOLDOWN_PESCA = 2 * 3600      # !pesca (2 horas) <-- ¡AÑADE ESTA LÍNEA!
COOLDOWN_MINAR = 60            # !minar (1 minuto)
COOLDOWN_JEFE = 7 * 24 * 3600 

def format_cooldown(seconds):
    """Convierte segundos en un formato de horas, minutos y segundos (Ej: 1h 30m 5s)."""
    if seconds <= 0:
        return "**✅ ¡LISTO!**"
    
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0:
        parts.append(f"{seconds}s")
    
    # Si el tiempo restante es > 0 pero no hay horas, minutos o segundos (e.g. 0.9s), forzar < 1s
    if not parts:
        return "< 1s"

    return " ".join(parts)

@bot.command(aliases=['cd'])
async def espera(ctx):
    """Muestra el tiempo restante de todos los cooldowns del usuario en horas, minutos y segundos."""
    user_id = ctx.author.id
    now = time.time()

    # Definir los comandos y sus cooldowns asociados
    cooldowns_config = [
        ("🎲 Gacha", user_last_gacha, COOLDOWN_GACHA),
        ("💼 Trabajar", user_last_trabajar, COOLDOWN_TRABAJAR),
        ("🎁 Recompensa Diaria", user_last_daily, COOLDOWN_DIARIA),
        ("🎯 Adivina Número", user_last_adivina, COOLDOWN_ADIVINA),
        ("🦹 Robo", user_last_rob, COOLDOWN_ROB),
        ("🎰 Casino", user_last_casino, COOLDOWN_CASINO), 
        ("🎣 Pesca", user_last_pesca, COOLDOWN_PESCA),
        ("⛏️ Minar", user_last_minar, COOLDOWN_MINAR),
        ("👑 Jefe Semanal", user_last_jefe, COOLDOWN_JEFE),
    ]
    
    cooldowns_text = []

    for name, last_used_dict, duration in cooldowns_config:
        last_used = last_used_dict.get(user_id, 0)
        time_elapsed = now - last_used
        time_remaining = duration - time_elapsed

        if time_remaining <= 0:
            status = "**✅ ¡LISTO!**"
        else:
            status = format_cooldown(time_remaining)

        cooldowns_text.append(f"• **{name}:** {status}")

    embed = discord.Embed(
        title=f"⏰ Cooldowns de {ctx.author.display_name}",
        description="Tiempo restante para poder usar los comandos (`!espera` también funciona como `!cd`).",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="Comandos", value="\n".join(cooldowns_text), inline=False)
    embed.set_footer(text="¡Usa los comandos cuando estén listos!")
    
    await ctx.send(embed=embed)

# ----------------------------
# COMANDOS DE PAUSA/REANUDACIÓN (Solo para administradores)
# ----------------------------

@bot.command()
@commands.has_permissions(administrator=True) # <--- ESTE ES EL CHECK DE ADMINISTRADOR
async def pausa(ctx):
    """Pausa el uso de la mayoría de los comandos del bot para los usuarios no administradores."""
    global bot_paused
    bot_paused = True
    embed = discord.Embed(
        title="⏸️ Bot Pausado",
        description="¡El bot ha sido puesto en modo de mantenimiento! Los comandos (excepto los de administración y los de control) no estarán disponibles para los usuarios hasta que se reanude.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(aliases=['reanudar'])
@commands.has_permissions(administrator=True) # <--- ESTE ES EL CHECK DE ADMINISTRADOR
async def continuar(ctx):
    """Reanuda el uso de todos los comandos del bot."""
    global bot_paused
    bot_paused = False
    embed = discord.Embed(
        title="▶️ Bot Reanudado",
        description="¡El modo de mantenimiento ha finalizado! Los usuarios pueden volver a usar todos los comandos.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


# ----------------------------
# COMANDO !CASINO (Tragaperras) <--- NUEVO COMANDO
# ----------------------------

@bot.command()
async def casino(ctx):
    """Juega a la tragaperras y gana entre 25 y 50 gemas con un cooldown de 1 hora."""
    user_id = ctx.author.id
    now = time.time()
    
    # 1. Verificar cooldown
    if user_id in user_last_casino and now - user_last_casino[user_id] < COOLDOWN_CASINO:
        time_remaining = COOLDOWN_CASINO - (now - user_last_casino[user_id])
        await ctx.send(f"⏰ **¡Espera!** Debes esperar {format_cooldown(time_remaining)} antes de volver a jugar al casino.")
        return

    user_last_casino[user_id] = now # Actualizar el tiempo de uso
    
    # 2. Configuración de la tragaperras
    # Símbolos comunes de tragaperras
    SYMBOLS = ["🍒", "🍋", "7️⃣", "💰", "💎", "⭐"]
    
    # Simular las 3 ruedas
    result = [random.choice(SYMBOLS) for _ in range(3)]
    
    # Determinar si hay premio gordo (Jackpot: tres iguales)
    is_jackpot = (result[0] == result[1] == result[2])
    
    # 3. Calcular recompensa
    if is_jackpot:
        reward_amount = 50 # Recompensa máxima
        title = "🎉 ¡JACKPOT!"
        color = discord.Color.gold()
        description = f"¡Tres símbolos iguales! Has ganado la recompensa máxima."
    else:
        # Recompensa mínima de 25, hasta 49 (para reservar 50 para el jackpot)
        reward_amount = random.randint(25, 49)
        title = "🎰 ¡A Rodar!"
        color = discord.Color.blue()
        
        # Mejorar el mensaje si hay 2 iguales (premio intermedio)
        if result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            description = f"¡Casi! Has ganado gemas por una pequeña coincidencia."
            color = discord.Color.orange()
            # Asegurar que el premio sea más cercano al máximo en caso de 2 aciertos
            reward_amount = random.randint(35, 49)
        else:
            description = f"Has ganado gemas por participación."

    # Asegurar el rango 25-50 (por si acaso la lógica anterior fallara en el futuro)
    if reward_amount > 50:
        reward_amount = 50
    if reward_amount < 25:
        reward_amount = 25
        
    # 4. Añadir balance y guardar
    add_balance(user_id, reward_amount)
    save_data()
    
    # 5. Enviar mensaje
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    # Formatear el resultado de las tragaperras para que se vea claramente
    slots_display = " | ".join(result)
    embed.add_field(name="Tragaperras", value=f"**{slots_display}**", inline=False)
    embed.add_field(name="🎁 Recompensa", value=format_gems(reward_amount), inline=True)
    embed.add_field(name="💰 Nuevo Balance", value=format_gems(get_balance(user_id)), inline=True)
    embed.set_footer(text=f"Próximo !casino en {format_cooldown(COOLDOWN_CASINO)}")
    
    await ctx.send(f"**{ctx.author.mention}** ha tirado de la palanca...", embed=embed)


# ----------------------------
# SISTEMA DE INTERCAMBIO
# ----------------------------
pending_trades = {}  # {trade_id: trade_data}

class AcceptRejectView(View):
    def __init__(self, trade_id, inviter, invited, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.inviter = inviter
        self.invited = invited

    @discord.ui.button(label="✅ Aceptar", style=discord.ButtonStyle.green)
    async def accept_callback(self, interaction, button):
        if interaction.user.id != self.invited.id:
            await interaction.response.send_message("❌ Solo el usuario invitado puede aceptar esta solicitud.", ephemeral=True)
            return

        # Actualizar estado del intercambio
        pending_trades[self.trade_id]['accepted'] = True
        pending_trades[self.trade_id]['invited_accepted'] = True

        # Crear vista de selección de cartas
        trade_view = TradeSelectionView(self.trade_id, self.inviter, self.invited)
        
        embed = discord.Embed(
            title="🔄 Intercambio Aceptado",
            description=f"{self.invited.mention} ha aceptado el intercambio.\n\nAhora ambos deben seleccionar las cartas que quieren intercambiar.",
            color=discord.Color.green()
        )
        embed.add_field(name="Instrucciones", value="• Usa las flechas para navegar\n• Presiona 'Seleccionar' para elegir cartas\n• Máximo 5 minutos para completar")
        
        await interaction.response.edit_message(embed=embed, view=trade_view)

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.red)
    async def reject_callback(self, interaction, button):
        if interaction.user.id != self.invited.id:
            await interaction.response.send_message("❌ Solo el usuario invitado puede rechazar esta solicitud.", ephemeral=True)
            return

        # Eliminar intercambio
        if self.trade_id in pending_trades:
            del pending_trades[self.trade_id]

        embed = discord.Embed(
            title="❌ Intercambio Rechazado",
            description=f"{self.invited.mention} ha rechazado la solicitud de intercambio.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class TradeSelectionView(View):
    def __init__(self, trade_id, user1, user2, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.user1 = user1
        self.user2 = user2
        self.user1_index = 0
        self.user2_index = 0

    async def send_trade_selection(self, interaction, user, user_index, is_user1):
        inventory = get_inventory(user.id)
        if not inventory:
            await interaction.response.send_message(f"❌ {user.mention} no tiene cartas para intercambiar.", ephemeral=True)
            return

        card = inventory[user_index]
        file = discord.File(card["imagen"], filename="carta_trade.png")
        
        rarity = card.get("rareza", "N")
        rarity_emoji = get_rarity_emoji(rarity)
        
        role = "Usuario 1" if is_user1 else "Usuario 2"
        selected_cards = pending_trades[self.trade_id]['user1_cards'] if is_user1 else pending_trades[self.trade_id]['user2_cards']
        
        embed = discord.Embed(
            title=f"🔄 Selección de Cartas - {role}",
            description=f"{user.mention}, selecciona las cartas que quieres intercambiar",
            color=get_rarity_color(rarity)
        )
        embed.add_field(name=f"{rarity_emoji} {card['nombre']} ({rarity})", value=card.get("descripcion", ""), inline=False)
        embed.add_field(name="Valor", value=format_gems(card.get('valor', 0)), inline=True)
        embed.add_field(name="Cartas seleccionadas", value=f"{len(selected_cards)} cartas", inline=True)
        embed.set_image(url="attachment://carta_trade.png")
        embed.set_footer(text=f"Carta {user_index + 1} de {len(inventory)}")

        # Crear botones específicos para este usuario
        view = View(timeout=300)
        
        async def prev_callback(interaction):
            nonlocal user_index
            if is_user1:
                self.user1_index = (user_index - 1) % len(inventory)
                user_index = self.user1_index
            else:
                self.user2_index = (user_index - 1) % len(inventory)
                user_index = self.user2_index
            await self.send_trade_selection(interaction, user, user_index, is_user1)

        async def next_callback(interaction):
            nonlocal user_index
            if is_user1:
                self.user1_index = (user_index + 1) % len(inventory)
                user_index = self.user1_index
            else:
                self.user2_index = (user_index + 1) % len(inventory)
                user_index = self.user2_index
            await self.send_trade_selection(interaction, user, user_index, is_user1)

        async def select_callback(interaction):
            if interaction.user.id != user.id:
                await interaction.response.send_message("❌ Solo puedes seleccionar cartas en tu propio intercambio.", ephemeral=True)
                return

            card = inventory[user_index]
            trade_data = pending_trades[self.trade_id]
            selected_cards = trade_data['user1_cards'] if is_user1 else trade_data['user2_cards']
            
            # Verificar si la carta ya está seleccionada
            card_ids = [c.get('id') for c in selected_cards]
            if card.get('id') in card_ids:
                # Deseleccionar
                selected_cards = [c for c in selected_cards if c.get('id') != card.get('id')]
            else:
                # Seleccionar
                selected_cards.append(card)
            
            if is_user1:
                trade_data['user1_cards'] = selected_cards
            else:
                trade_data['user2_cards'] = selected_cards
            
            pending_trades[self.trade_id] = trade_data
            
            await self.send_trade_selection(interaction, user, user_index, is_user1)

        async def confirm_callback(interaction):
            if interaction.user.id != user.id:
                await interaction.response.send_message("❌ Solo puedes confirmar tu propia selección.", ephemeral=True)
                return

            trade_data = pending_trades[self.trade_id]
            if is_user1:
                trade_data['user1_confirmed'] = True
            else:
                trade_data['user2_confirmed'] = True
            
            # Verificar si ambos confirmaron
            if trade_data['user1_confirmed'] and trade_data['user2_confirmed']:
                # Mostrar vista de confirmación final
                await self.show_final_confirmation(interaction)
            else:
                await interaction.response.send_message("✅ Selección confirmada. Esperando al otro usuario...", ephemeral=True)

        # Botones de navegación
        prev_btn = Button(label="⬅️", style=discord.ButtonStyle.blurple)
        next_btn = Button(label="➡️", style=discord.ButtonStyle.blurple)
        select_btn = Button(label="🔄 Seleccionar", style=discord.ButtonStyle.green)
        confirm_btn = Button(label="✅ Confirmar Selección", style=discord.ButtonStyle.red)

        prev_btn.callback = prev_callback
        next_btn.callback = next_callback
        select_btn.callback = select_callback
        confirm_btn.callback = confirm_callback

        view.add_item(prev_btn)
        view.add_item(next_btn)
        view.add_item(select_btn)
        view.add_item(confirm_btn)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)

    async def show_final_confirmation(self, interaction):
        trade_data = pending_trades[self.trade_id]
        user1_cards = trade_data['user1_cards']
        user2_cards = trade_data['user2_cards']
        
        # Crear embed de confirmación final
        embed = discord.Embed(
            title="🔄 Confirmación Final de Intercambio",
            description="Ambos usuarios han confirmado sus selecciones. Revisa los detalles:",
            color=discord.Color.blue()
        )
        
        # Cartas del usuario 1
        user1_cards_text = "\n".join([f"• {card['nombre']} ({card.get('rareza', 'C')})" for card in user1_cards]) if user1_cards else "Ninguna carta seleccionada"
        embed.add_field(name=f"🎁 {self.user1.display_name} ofrece:", value=user1_cards_text, inline=False)
        
        # Cartas del usuario 2
        user2_cards_text = "\n".join([f"• {card['nombre']} ({card.get('rareza', 'C')})" for card in user2_cards]) if user2_cards else "Ninguna carta seleccionada"
        embed.add_field(name=f"🎁 {self.user2.display_name} ofrece:", value=user2_cards_text, inline=False)
        
        # Vista de confirmación final
        final_view = FinalTradeView(self.trade_id, self.user1, self.user2)
        
        # Enviar a ambos usuarios
        try:
            await self.user1.send(embed=embed, view=final_view)
            await self.user2.send(embed=embed, view=final_view)
            await interaction.followup.send("✅ ¡Intercambio listo! Revisa tus mensajes privados para confirmar.", ephemeral=True)
        except:
            await interaction.followup.send("❌ No puedo enviar mensajes privados. Asegúrate de tener los MD abiertos.", ephemeral=True)

class FinalTradeView(View):
    def __init__(self, trade_id, user1, user2, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.user1 = user1
        self.user2 = user2

    @discord.ui.button(label="✅ Aceptar Intercambio", style=discord.ButtonStyle.green)
    async def accept_final_callback(self, interaction, button):
        trade_data = pending_trades.get(self.trade_id)
        if not trade_data:
            await interaction.response.send_message("❌ Este intercambio ya no existe.", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id == self.user1.id:
            trade_data['user1_final_accept'] = True
        elif user_id == self.user2.id:
            trade_data['user2_final_accept'] = True

        # Verificar si ambos aceptaron
        if trade_data.get('user1_final_accept') and trade_data.get('user2_final_accept'):
            # Ejecutar el intercambio
            await self.execute_trade(interaction)
        else:
            await interaction.response.send_message("✅ Has aceptado el intercambio. Esperando al otro usuario...", ephemeral=True)

    @discord.ui.button(label="❌ Cancelar Intercambio", style=discord.ButtonStyle.red)
    async def reject_final_callback(self, interaction, button):
        if self.trade_id in pending_trades:
            del pending_trades[self.trade_id]
        
        # Notificar al otro usuario
        other_user = self.user2 if interaction.user.id == self.user1.id else self.user1
        try:
            await other_user.send(f"❌ {interaction.user.mention} ha cancelado el intercambio.")
        except:
            pass
        
        await interaction.response.send_message("❌ Intercambio cancelado.", ephemeral=True)

    async def execute_trade(self, interaction):
        trade_data = pending_trades.get(self.trade_id)
        if not trade_data:
            return

        user1_cards = trade_data['user1_cards']
        user2_cards = trade_data['user2_cards']

        # Realizar el intercambio
        try:
            # Remover cartas de los inventarios originales
            for card in user1_cards:
                card_id = card.get('id')
                inv = get_inventory(self.user1.id)
                for i, c in enumerate(inv):
                    if c.get('id') == card_id:
                        remove_from_inventory_by_index(self.user1.id, i)
                        break
            
            for card in user2_cards:
                card_id = card.get('id')
                inv = get_inventory(self.user2.id)
                for i, c in enumerate(inv):
                    if c.get('id') == card_id:
                        remove_from_inventory_by_index(self.user2.id, i)
                        break

            # Añadir cartas a los nuevos dueños
            for card in user1_cards:
                add_to_inventory(self.user2.id, card)
            
            for card in user2_cards:
                add_to_inventory(self.user1.id, card)

            # Eliminar intercambio
            del pending_trades[self.trade_id]

            # Embed de éxito
            embed = discord.Embed(
                title="✅ ¡Intercambio Completado!",
                description="Las cartas han sido intercambiadas exitosamente.",
                color=discord.Color.green()
            )
            
            user1_receives = "\n".join([f"• {card['nombre']}" for card in user2_cards]) if user2_cards else "Nada"
            user2_receives = "\n".join([f"• {card['nombre']}" for card in user1_cards]) if user1_cards else "Nada"
            
            embed.add_field(name=f"🎁 {self.user1.display_name} recibe:", value=user1_receives, inline=False)
            embed.add_field(name=f"🎁 {self.user2.display_name} recibe:", value=user2_receives, inline=False)

            # Enviar a ambos usuarios
            try:
                await self.user1.send(embed=embed)
                await self.user2.send(embed=embed)
            except:
                pass

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            await interaction.response.send_message("❌ Error al ejecutar el intercambio. Inténtalo de nuevo.", ephemeral=True)

# ----------------------------
# Funciones auxiliares
# ----------------------------
def get_inventory(user_id):
    return user_inventories.get(str(user_id), [])

def get_completed_floors(user_id):
    """Obtiene la lista de pisos completados por un usuario"""
    user_id_str = str(user_id)
    # Asegurarse de que user_completed_floors esté inicializado
    if user_id_str not in user_completed_floors:
        user_completed_floors[user_id_str] = []
    return user_completed_floors[user_id_str]

def add_to_inventory(user_id, card):
    uid = str(user_id)
    if uid not in user_inventories:
        user_inventories[uid] = []
    user_inventories[uid].append(card)
    save_data()

def remove_from_inventory_by_index(user_id, index):
    uid = str(user_id)
    inv = user_inventories.get(uid, [])
    if 0 <= index < len(inv):
        removed = inv.pop(index)
        user_inventories[uid] = inv
        save_data()
        return removed
    return None

def get_balance(user_id):
    return user_balances.get(str(user_id), 0)

def add_balance(user_id, amount):
    uid = str(user_id)
    if uid not in user_balances:
        user_balances[uid] = 0
    user_balances[uid] += amount
    save_data()

def has_rob_penalty(user_id):
    uid = str(user_id)
    if uid in user_rob_penalties:
        return user_rob_penalties[uid] > time.time()
    return False

def get_rob_penalty_time(user_id):
    uid = str(user_id)
    if uid in user_rob_penalties:
        return user_rob_penalties[uid]
    return 0

def set_rob_penalty(user_id, penalty_end_time):
    uid = str(user_id)
    user_rob_penalties[uid] = penalty_end_time
    save_data()

# Función para obtener el ícono de gemas
def get_gem_emoji():
    return "💎"  # Emoji de gemas estándar

# Función para formatear cantidades con el ícono de gemas
def format_gems(amount):
    return f"{amount} {get_gem_emoji()}"

# Función para obtener emoji de rareza
def get_rarity_emoji(rarity):
    rarity_emojis = {
        "E": "🎉",   # Evento - Fiesta
        "M": "✨",   # Mítico - Brillo
        "G": "🌌",   # Galaxia - Espacio estrellado
        "F": "🎭",   # Fun - Máscaras
        "SP": "🎀",  # Special - Moño
        "UR": "💫",  # Ultra Raro - Estrella fugaz
        "SSR": "🔥", # Super Super Raro - Fuego
        "R": "⭐",   # Super Raro - Estrella
        "N": "🔹",   # Normal - Diamante azul
    }
    return rarity_emojis.get(rarity, "📄")

    
# Nueva Función para Obtener Cartas Aleatorias por Rareza

def obtener_carta_aleatoria_por_rareza(rarity):
    """Obtiene una carta aleatoria de la rareza especificada"""
    if rarity in cards_catalog and cards_catalog[rarity]:
        return random.choice(cards_catalog[rarity])
    return None

# Función para obtener color de embed según rareza
def get_rarity_color(rarity):
    rarity_colors = {
        "E": 0xFFD700,   # Evento - Oro
        "M": 0x9B59B6,   # Mítico - Púrpura
        "G": 0x6C5CE7,   # Galaxia - Morado espacial
        "F": 0x1ABC9C,   # Fun - Turquesa
        "SP": 0xFF69B4,  # Special - Rosa
        "UR": 0x3498DB,  # Ultra Raro - Azul
        "SSR": 0xE74C3C, # Super Super Raro - Rojo
        "R": 0xF1C40F,  # Super Raro - Amarillo
        "N": 0x3498DB,   # Normal - Azul claro
    }
    return rarity_colors.get(rarity, 0x000000)

# ----------------------------
# COMANDO INTERFAZ ADMIN (Solo para administradores)
# ----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def interfaz(ctx):
    """Interfaz de administración para gestionar el catálogo de cartas"""
    
    # Crear los botones del menú principal
    view = View(timeout=300)
    
    async def agregar_callback(interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo los administradores pueden usar esta interfaz.", ephemeral=True)
            return
        
        # Iniciar el proceso de agregar carta
        await iniciar_agregar_carta(interaction)
    
    async def eliminar_callback(interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo los administradores pueden usar esta interfaz.", ephemeral=True)
            return
        
        # Crear vista para eliminar carta
        view_eliminar = EliminarCartaView()
        await interaction.response.send_message("🔍 **Eliminar Carta**\nIngresa el ID de la carta que deseas eliminar:", view=view_eliminar)
    
    async def editar_stats_callback(interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo los administradores pueden usar esta interfaz.", ephemeral=True)
            return
        
        # Crear vista para editar stats
        view_editar = EditarStatsView()
        await interaction.response.send_message("📊 **Editar Stats de Carta**\nIngresa el ID de la carta cuyas stats deseas modificar:", view=view_editar)
    
    # Crear botones
    btn_agregar = Button(label="➕ Agregar Carta", style=discord.ButtonStyle.green)
    btn_eliminar = Button(label="🗑️ Eliminar Carta", style=discord.ButtonStyle.red)
    btn_editar = Button(label="📊 Editar Stats", style=discord.ButtonStyle.blurple)
    
    btn_agregar.callback = agregar_callback
    btn_eliminar.callback = eliminar_callback
    btn_editar.callback = editar_stats_callback
    
    view.add_item(btn_agregar)
    view.add_item(btn_eliminar)
    view.add_item(btn_editar)
    
    embed = discord.Embed(
        title="🛠️ **Interfaz de Administración**",
        description="Selecciona una opción para gestionar el catálogo de cartas:",
        color=discord.Color.blue()
    )
    embed.add_field(name="➕ Agregar Carta", value="Añadir una nueva carta al catálogo", inline=False)
    embed.add_field(name="🗑️ Eliminar Carta", value="Eliminar una carta existente del catálogo", inline=False)
    embed.add_field(name="📊 Editar Stats", value="Modificar las estadísticas de una carta", inline=False)
    embed.set_footer(text="Solo disponible para administradores • Tiempo límite: 5 minutos")
    
    await ctx.send(embed=embed, view=view)

# ----------------------------
# SISTEMA PARA AGREGAR CARTA (Usando vistas en lugar de modales anidados)
# ----------------------------
async def iniciar_agregar_carta(interaction):
    """Inicia el proceso de agregar carta con un modal inicial"""
    modal = AgregarCartaModalInicial()
    await interaction.response.send_modal(modal)

class AgregarCartaModalInicial(discord.ui.Modal, title='➕ Agregar Nueva Carta'):
    def __init__(self):
        super().__init__()
        # Campos principales (máximo 5)
        self.add_item(discord.ui.TextInput(
            label='ID de la Carta',
            placeholder='Ej: UR012, SP011, etc.',
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label='Nombre de la Carta',
            placeholder='Ej: Shoyo Hinata (Karasuno)',
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label='Rareza',
            placeholder='C, N, R, SSR, UR, SP, L',
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label='Valor en Gemas',
            placeholder='Ej: 100',
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label='Stock Disponible',
            placeholder='Ej: 50, 100, Unlimited',
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        # Guardar datos y mostrar vista para completar
        self.card_id = self.children[0].value.strip()
        self.nombre = self.children[1].value.strip()
        self.rareza = self.children[2].value.strip().upper()
        self.valor_str = self.children[3].value.strip()
        self.stock = self.children[4].value.strip()
        
        # Validaciones básicas
        if not self.valor_str.isdigit():
            await interaction.response.send_message("❌ El valor debe ser un número entero.", ephemeral=True)
            return
        
        # Verificar si el ID ya existe
        for card in catalog_cards:
            if card["id"] == self.card_id:
                await interaction.response.send_message(f"❌ Ya existe una carta con el ID `{self.card_id}`.", ephemeral=True)
                return
        
        # Mostrar vista para completar los campos restantes
        view = CompletarCartaView(self.card_id, self.nombre, self.rareza, self.valor_str, self.stock)
        
        embed = discord.Embed(
            title="➕ Completar Información de Carta",
            description="Por favor completa la información restante:",
            color=discord.Color.blue()
        )
        embed.add_field(name="ID", value=self.card_id, inline=True)
        embed.add_field(name="Nombre", value=self.nombre, inline=True)
        embed.add_field(name="Rareza", value=self.rareza, inline=True)
        embed.add_field(name="Valor", value=format_gems(int(self.valor_str)), inline=True)
        embed.add_field(name="Stock", value=self.stock, inline=True)
        embed.add_field(name="Faltante", value="Máximo por usuario y Descripción", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class CompletarCartaView(View):
    def __init__(self, card_id, nombre, rareza, valor_str, stock):
        super().__init__(timeout=300)
        self.card_id = card_id
        self.nombre = nombre
        self.rareza = rareza
        self.valor_str = valor_str
        self.stock = stock
    
    @discord.ui.button(label="📝 Completar Información", style=discord.ButtonStyle.green)
    async def completar_callback(self, interaction, button):
        # Abrir modal para completar información restante
        modal = CompletarCartaModal(self.card_id, self.nombre, self.rareza, self.valor_str, self.stock, self)
        await interaction.response.send_modal(modal)

class CompletarCartaModal(discord.ui.Modal, title='📝 Completar Información de Carta'):
    def __init__(self, card_id, nombre, rareza, valor_str, stock, parent_view):
        super().__init__()
        self.card_id = card_id
        self.nombre = nombre
        self.rareza = rareza
        self.valor_str = valor_str
        self.stock = stock
        self.parent_view = parent_view  # Guardar referencia a la vista padre
        
        self.add_item(discord.ui.TextInput(
            label='Máximo por Usuario',
            placeholder='Ej: 1, 10, 1000, Unlimited',
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label='Descripción',
            placeholder='Descripción de la carta...',
            style=discord.TextStyle.paragraph,
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        max_per_user_str = self.children[0].value.strip()
        descripcion = self.children[1].value.strip()
        
        # Validaciones
        if not max_per_user_str.isdigit() and max_per_user_str != "Unlimited":
            await interaction.response.send_message("❌ El máximo por usuario debe ser un número o 'Unlimited'.", ephemeral=True)
            return
        
        valor = int(self.valor_str)
        max_per_user = int(max_per_user_str) if max_per_user_str != "Unlimited" else "Unlimited"
        
        # Crear la nueva carta
        nueva_carta = {
            "id": self.card_id,
            "nombre": self.nombre,
            "rareza": self.rareza,
            "valor": valor,
            "stock": self.stock,
            "max_per_user": max_per_user,
            "imagen": f"images/{self.card_id}.png",  # Ruta por defecto
            "descripcion": descripcion,
            "stats": {
                "Evasion": 1,
                "Fuerza": 1,
                "Reacción": 1,
                "Defensa": 1,
                "Velocidad": 1,
                "IQ": 1,
                "Carisma ": 1,
                "Precisión": 1,
                "Energia": 1,
                "Suerte": 1
            }
        }
        
        # Agregar al catálogo
        catalog_cards.append(nueva_carta)
        cards_catalog.setdefault(self.rareza, []).append(nueva_carta)
        
        # Guardar en el archivo JSON
        catalog_data["cards"] = catalog_cards
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)
        
        embed = discord.Embed(
            title="✅ Carta Agregada Exitosamente",
            description=f"**{self.nombre}** ha sido añadida al catálogo.",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=self.card_id, inline=True)
        embed.add_field(name="Rareza", value=self.rareza, inline=True)
        embed.add_field(name="Valor", value=format_gems(valor), inline=True)
        embed.add_field(name="Stock", value=self.stock, inline=True)
        embed.add_field(name="Máx por Usuario", value=max_per_user, inline=True)
        embed.add_field(name="Stats Iniciales", value="Todas en 1", inline=True)
        embed.add_field(name="Imagen", value=f"images/{self.card_id}.png", inline=False)
        embed.add_field(name="Descripción", value=descripcion, inline=False)
        
        # Deshabilitar el botón en la vista original
        for item in self.parent_view.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

# ----------------------------
# COMANDO PARA SUBIR IMAGEN DE CARTA
# ----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def subir_imagen(ctx, card_id: str):
    """Sube una imagen para una carta específica"""
    
    # Verificar si hay archivos adjuntos
    if not ctx.message.attachments:
        await ctx.send("❌ Por favor adjunta una imagen con el comando.\nEjemplo: `!subir_imagen UR001` (con imagen adjunta)")
        return
    
    attachment = ctx.message.attachments[0]
    
    # Verificar que sea una imagen
    if not attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        await ctx.send("❌ El archivo debe ser una imagen (PNG, JPG, JPEG, GIF)")
        return
    
    # Buscar la carta
    carta_encontrada = None
    for card in catalog_cards:
        if card["id"] == card_id:
            carta_encontrada = card
            break
    
    if not carta_encontrada:
        await ctx.send(f"❌ No se encontró ninguna carta con el ID `{card_id}`.")
        return
    
    try:
        # Crear directorio images si no existe
        os.makedirs("images", exist_ok=True)
        
        # Descargar la imagen
        image_path = f"images/{card_id}.png"
        await attachment.save(image_path)
        
        # Actualizar la ruta de la imagen en la carta
        carta_encontrada["imagen"] = image_path
        
        # Guardar cambios en el archivo JSON
        catalog_data["cards"] = catalog_cards
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)
        
        # Actualizar también en cards_catalog
        for rarity in cards_catalog:
            for i, card in enumerate(cards_catalog[rarity]):
                if card["id"] == card_id:
                    cards_catalog[rarity][i] = carta_encontrada
                    break
        
        embed = discord.Embed(
            title="✅ Imagen Actualizada",
            description=f"Imagen de **{carta_encontrada['nombre']}** actualizada exitosamente.",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=card_id, inline=True)
        embed.add_field(name="Archivo", value=attachment.filename, inline=True)
        embed.add_field(name="Ruta", value=image_path, inline=True)
        
        # Mostrar la imagen actualizada
        file = discord.File(image_path, filename="carta_actualizada.png")
        embed.set_image(url="attachment://carta_actualizada.png")
        
        await ctx.send(embed=embed, file=file)
        
    except Exception as e:
        await ctx.send(f"❌ Error al guardar la imagen: {str(e)}")

# ----------------------------
# VISTA PARA ELIMINAR CARTA
# ----------------------------
class EliminarCartaView(View):
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="🔍 Buscar por ID", style=discord.ButtonStyle.blurple)
    async def buscar_callback(self, interaction, button):
        # Crear modal para ingresar ID
        modal = BuscarCartaModal("eliminar")
        await interaction.response.send_modal(modal)

class BuscarCartaModal(discord.ui.Modal, title='🔍 Buscar Carta por ID'):
    def __init__(self, action_type):
        super().__init__()
        self.action_type = action_type
        self.add_item(discord.ui.TextInput(
            label='ID de la Carta',
            placeholder='Ej: UR001, SP005, etc.',
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        card_id = self.children[0].value.strip()
        
        # Buscar la carta
        carta_encontrada = None
        for card in catalog_cards:
            if card["id"] == card_id:
                carta_encontrada = card
                break
        
        if not carta_encontrada:
            await interaction.response.send_message(f"❌ No se encontró ninguna carta con el ID `{card_id}`.", ephemeral=True)
            return
        
        if self.action_type == "eliminar":
            # Mostrar confirmación para eliminar
            view = ConfirmarEliminarView(carta_encontrada)
            
            embed = discord.Embed(
                title="🗑️ Confirmar Eliminación",
                description=f"¿Estás seguro de que deseas eliminar esta carta?",
                color=discord.Color.red()
            )
            embed.add_field(name="ID", value=carta_encontrada["id"], inline=True)
            embed.add_field(name="Nombre", value=carta_encontrada["nombre"], inline=True)
            embed.add_field(name="Rareza", value=carta_encontrada["rareza"], inline=True)
            embed.add_field(name="Valor", value=format_gems(carta_encontrada["valor"]), inline=True)
            
            try:
                file = discord.File(carta_encontrada["imagen"], filename="carta.png")
                embed.set_image(url="attachment://carta.png")
                await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
            except:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        elif self.action_type == "editar_stats":
            # Mostrar interfaz para editar stats
            view = EditarStatsFormView(carta_encontrada)
            
            embed = discord.Embed(
                title="📊 Editar Estadísticas",
                description=f"Modifica las stats de **{carta_encontrada['nombre']}**",
                color=discord.Color.blue()
            )
            
            stats = carta_encontrada.get("stats", {})
            embed.add_field(name="Evasion", value=stats.get("Evasion", 1), inline=True)
            embed.add_field(name="Fuerza", value=stats.get("Fuerza", 1), inline=True)
            embed.add_field(name="Reacción", value=stats.get("Reacción", 1), inline=True)
            embed.add_field(name="Defensa", value=stats.get("Defensa", 1), inline=True)
            embed.add_field(name="Velocidad", value=stats.get("Velocidad", 1), inline=True)
            embed.add_field(name="IQ", value=stats.get("IQ", 1), inline=True)
            embed.add_field(name="Carisma", value=stats.get("Carisma", 1), inline=True)
            embed.add_field(name="Precisión", value=stats.get("Precisión", 1), inline=True)
            embed.add_field(name="Energia", value=stats.get("Energia", 1), inline=True)
            embed.add_field(name="Suerte", value=stats.get("Suerte", 1), inline=True)
            
            try:
                file = discord.File(carta_encontrada["imagen"], filename="carta.png")
                embed.set_thumbnail(url="attachment://carta.png")
                await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
            except:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ConfirmarEliminarView(View):
    def __init__(self, carta):
        super().__init__(timeout=300)
        self.carta = carta
    
    @discord.ui.button(label="✅ Confirmar Eliminación", style=discord.ButtonStyle.red)
    async def confirmar_callback(self, interaction, button):
        # Eliminar la carta del catálogo
        global catalog_cards, cards_catalog
        
        # Remover de la lista plana
        catalog_cards = [card for card in catalog_cards if card["id"] != self.carta["id"]]
        
        # Remover del catálogo organizado por rareza
        rareza = self.carta["rareza"]
        if rareza in cards_catalog:
            cards_catalog[rareza] = [card for card in cards_catalog[rareza] if card["id"] != self.carta["id"]]
        
        # Guardar cambios
        catalog_data["cards"] = catalog_cards
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)
        
        embed = discord.Embed(
            title="✅ Carta Eliminada",
            description=f"**{self.carta['nombre']}** ha sido eliminada del catálogo.",
            color=discord.Color.green()
        )
        
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.gray)
    async def cancelar_callback(self, interaction, button):
        embed = discord.Embed(
            title="❌ Eliminación Cancelada",
            description="La carta no fue eliminada.",
            color=discord.Color.gray()
        )
        
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)

# ----------------------------
# VISTA PARA EDITAR STATS
# ----------------------------
class EditarStatsView(View):
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="🔍 Buscar por ID", style=discord.ButtonStyle.blurple)
    async def buscar_callback(self, interaction, button):
        # Crear modal para ingresar ID
        modal = BuscarCartaModal("editar_stats")
        await interaction.response.send_modal(modal)

class EditarStatsFormView(View):
    def __init__(self, carta):
        super().__init__(timeout=300)
        self.carta = carta
    
    @discord.ui.button(label="✏️ Editar Evasion", style=discord.ButtonStyle.blurple)
    async def editar_Evasion_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "Evasion")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="✏️ Editar Ataque", style=discord.ButtonStyle.blurple)
    async def editar_ataque_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "ataque")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="✏️ Editar Reacción", style=discord.ButtonStyle.blurple)
    async def editar_Reacción_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "Reacción")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="✏️ Editar Defensa", style=discord.ButtonStyle.blurple)
    async def editar_Defensa_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "Defensa")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="✏️ Editar Velocidad", style=discord.ButtonStyle.blurple)
    async def editar_Velocidad_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "Velocidad")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="✏️ Editar IQ", style=discord.ButtonStyle.blurple)
    async def editar_IQ_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "IQ")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✏️ Editar Carisma", style=discord.ButtonStyle.blurple)
    async def editar_Carisma_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "Carisma")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✏️ Editar Precisión", style=discord.ButtonStyle.blurple)
    async def editar_Precisión_callback(self, interaction, button):
        modal = EditarStatModal(self.carta, "Precisión")
        await interaction.response.send_modal(modal)        
    
    @discord.ui.button(label="💾 Guardar Cambios", style=discord.ButtonStyle.green)
    async def guardar_callback(self, interaction, button):
        # Los cambios ya se guardaron automáticamente en los modales
        embed = discord.Embed(
            title="✅ Cambios Guardados",
            description=f"Las estadísticas de **{self.carta['nombre']}** han sido actualizadas.",
            color=discord.Color.green()
        )
        
        stats = self.carta.get("stats", {})
        embed.add_field(name="Evasion", value=stats.get("Evasion", 1), inline=True)
        embed.add_field(name="Ataque", value=stats.get("Ataque", 1), inline=True)
        embed.add_field(name="Reacción", value=stats.get("Reacción", 1), inline=True)
        embed.add_field(name="Defensa", value=stats.get("Defensa", 1), inline=True)
        embed.add_field(name="Velocidad", value=stats.get("Velocidad", 1), inline=True)
        embed.add_field(name="IQ", value=stats.get("IQ", 1), inline=True)
        embed.add_field(name="Carisma", value=stats.get("Carisma", 1), inline=True)
        embed.add_field(name="Precisión", value=stats.get("Precisión", 1), inline=True)
        
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)

class EditarStatModal(discord.ui.Modal, title='✏️ Editar Estadística'):
    def __init__(self, carta, stat_name):
        super().__init__()
        self.carta = carta
        self.stat_name = stat_name
        
        # Traducir nombre de stat para mostrar
        stat_names = {
            "Evasion": "Evasion",
            "Fuerza": "Fuerza", 
            "Reacción": "Reacción",
            "Defensa": "Defensa",
            "Velocidad": "Velocidad",
            "IQ": "IQ",
            "Carisma": "Carisma",
            "Precisión": "Precisión",
            "Energia": "Energia",
            "Suerte": "Suerte"

        }
        
        current_value = carta.get("stats", {}).get(stat_name, 1)
        
        self.add_item(discord.ui.TextInput(
            label=f'Nuevo valor para {stat_names[stat_name]}',
            placeholder=f'Valor actual: {current_value}',
            required=True,
            default=str(current_value)
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        nuevo_valor_str = self.children[0].value.strip()
        
        # Validar que sea un número
        if not nuevo_valor_str.isdigit():
            await interaction.response.send_message("❌ El valor debe ser un número entero.", ephemeral=True)
            return
        
        nuevo_valor = int(nuevo_valor_str)
        
        # Actualizar el valor en la carta
        if "stats" not in self.carta:
            self.carta["stats"] = {}
        
        self.carta["stats"][self.stat_name] = nuevo_valor
        
        # Guardar cambios en el archivo
        catalog_data["cards"] = catalog_cards
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)
        
        # Actualizar también en cards_catalog
        for rarity in cards_catalog:
            for i, card in enumerate(cards_catalog[rarity]):
                if card["id"] == self.carta["id"]:
                    cards_catalog[rarity][i] = self.carta
                    break
        
        stat_names = {
            "Evasion": "Evasion",
            "Ataque": "Ataque",
            "Reacción": "Reacción", 
            "Defensa": "Defensa",
            "Velocidad": "Velocidad",
            "IQ": "IQ",
            "Carisma": "Carisma",
            "Precisión": "Precisión"
        }
        
        await interaction.response.send_message(
            f"✅ **{stat_names[self.stat_name]}** actualizado a **{nuevo_valor}** para **{self.carta['nombre']}**", 
            ephemeral=True
        )

# ----------------------------
# COMANDO DE AYUDA ACTUALIZADO (VERSIÓN SIMPLIFICADA - SIN PAGINACIÓN)
# ----------------------------

@bot.command()
async def ayuda(ctx):
    """Muestra todos los comandos disponibles para usuarios en una sola lista"""
    
    # Determinar si el usuario es administrador
    es_admin = ctx.author.guild_permissions.administrator
    
    embed = discord.Embed(
        title="🎮 **COMANDOS DISPONIBLES - PROJECT-KC**",
        description="Lista completa de comandos disponibles. ¡Usa `!ayuda` para ver este menú nuevamente!",
        color=discord.Color.blue()
    )
    
    # 🔹 ECONOMÍA Y GEMAS
    embed.add_field(
        name="💰 **ECONOMÍA Y GEMAS**",
        value=(
            "• `!gacha` - Tirada gratuita cada 4 horas\n"
            "• `!gacha_comprar [1/5/10]` - Compra tiradas con gemas\n"
            "• `!trabajar` - Gana 20-40 gemas (4h cooldown)\n"
            "• `!casino` - Tragaperras (1h cooldown)\n"
            "• `!pesca` - Minijuego de pesca (2h cooldown)\n"
            "• `!minar` - Minijuego de minería (1min cooldown)\n"
            "• `!diaria` - Recompensa diaria de 80 gemas\n"
            "• `!rob @usuario` - Roba gemas a otro usuario (30min cooldown)"
        ),
        inline=False
    )
    
    # ⚔️ DUELOS PVP
    embed.add_field(
        name="⚔️ **SISTEMA DE DUELOS PVP**",
        value=(
            "• `!dueloamistoso @usuario` - Duelo amistoso (3 rondas)\n"
            "• `!duelohonor @usuario [rareza]` - Duelo con apuestas\n"
            "• `!aceptar_duelo` - Acepta duelo pendiente\n"
            "• `!rechazar_duelo` - Rechaza duelo pendiente\n"
            "• `!cancelar_duelo` - Cancela duelos pendientes"
        ),
        inline=False
    )
    
    # 📦 GESTIÓN DE CARTAS
    embed.add_field(
        name="📦 **GESTIÓN DE CARTAS**",
        value=(
            "• `!inventario` - Cartas en carrusel\n"
            "• `!inventario_personal` - Lista completa en MD\n"
            "• `!album` - Cartas únicas en formato 4x4\n"
            "• `!vender` - Vende cartas una por una\n"
            "• `!vender_mayoreo` - Vende múltiples cartas\n"
            "• `!vender_rareza [rareza]` - Vende por rareza\n"
            "• `!intercambio @usuario` - Intercambia cartas\n"
            "• `!cancelar_intercambio` - Cancela intercambio"
        ),
        inline=False
    )
    
    # 🎮 MINIJUEGOS
    embed.add_field(
        name="🎮 **MINIJUEGOS**",
        value=(
            "• `!adivina` - Adivina el número (1h cooldown)\n"
            "• `!jefe_semanal` - Desafía al jefe semanal\n"
            "• `!eleccion_jefe [número]` - Selecciona carta para jefe\n"
            "• `!cancelar_jefe` - Cancela desafío al jefe"
        ),
        inline=False
    )
    
    # 🎁 RECOMPENSAS
    embed.add_field(
        name="🎁 **RECOMPENSAS Y ELECCIONES**",
        value=(
            "• `!recibir_recompensa` - Reclama recompensa temporal\n"
            "• `!estado_recompensa` - Estado de recompensa activa\n"
            "• `!eleccion_recompensa` - Reclama elección global\n"
            "• `!recibir_gemas` - Reclama recompensa fija de gemas"
        ),
        inline=False
    )
    
    # ℹ️ INFORMACIÓN
    embed.add_field(
        name="ℹ️ **INFORMACIÓN Y UTILIDAD**",
        value=(
            "• `!espera` / `!cd` - Muestra todos los cooldowns\n"
            "• `!rates` - Probabilidades del gacha\n"
            "• `!status` - Estado del bot y servicios\n"
            "• `!menu_principal` - Menú con botones interactivos"
        ),
        inline=False
    )
    
    # 🛠️ COMANDOS DE ADMINISTRADOR (solo si es admin)
    if es_admin:
        embed.add_field(
            name="👑 **COMANDOS DE ADMINISTRADOR**",
            value=(
                "• `!pausa` / `!continuar` - Control modo mantenimiento\n"
                "• `!interfaz` - Panel de gestión de cartas\n"
                "• `!subir_imagen [id]` - Sube imagen de carta\n"
                "• `!modificar_rates` - Cambia probabilidades gacha\n"
                "• `!recompensa_tiempo [id] [min]` - Crea recompensa temporal\n"
                "• `!cancelar_recompensa` - Cancela recompensa\n"
                "• `!dargemas @usuario [cantidad]` - Da gemas\n"
                "• `!quitargemas @usuario [cantidad]` - Quita gemas\n"
                "• `!darcarta @usuario [id]` - Regala carta\n"
                "• `!quitarcarta @usuario [id]` - Elimina carta\n"
                "• `!limpiar_inventario @usuario` - Limpia inventario\n"
                "• `!clear [cantidad]` - Borra mensajes\n"
                "• `!reset_data` - Resetea todos los datos\n"
                "• `!backup_now` - Backup manual\n"
                "• `!backup_status` - Estado backup\n"
                "• `!listar_backups` - Lista backups\n"
                "• `!borrar_backups` - Elimina backups\n"
                "• `!eleccion_carta [id1] [id2]` - Crea elección global\n"
                "• `!cancelar_eleccion` - Cancela elección\n"
                "• `!gemas_fijas [cant] [horas]` - Recompensa fija gemas\n"
                "• `!cancelar_gemas_fijas` - Cancela recompensa fija\n"
                "• `!estado_gemas_fijas` - Estado recompensa fija"
            ),
            inline=False
        )
    
    # 📊 SISTEMA DE RATES
    embed.add_field(
        name="🎰 **PROBABILIDADES ACTUALES DEL GACHA**",
        value=(
            "• **G (Galaxia)**: 1.0%\n"
            "• **SP (Special)**: 2.0%\n"
            "• **UR (Ultra Raro)**: 3.5%\n"
            "• **SSR (SSR)**: 6.5%\n"
            "• **R (Raro)**: 10.0%\n"
            "• **N (Normal)**: 77.0%"
        ),
        inline=False
    )
    
    # 📝 NOTAS FINALES
    footer_text = "¡Usa !ayuda para ver este menú nuevamente!"
    if es_admin:
        footer_text += " | Eres administrador 👑"
    
    embed.set_footer(text=footer_text)
    
    await ctx.send(embed=embed)
    
# ----------------------------
# SISTEMA DE INTERCAMBIO CORREGIDO
# ----------------------------

class AcceptRejectView(View):
    def __init__(self, trade_id, inviter, invited, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.inviter = inviter
        self.invited = invited

    @discord.ui.button(label="✅ Aceptar", style=discord.ButtonStyle.green)
    async def accept_callback(self, interaction, button):
        if interaction.user.id != self.invited.id:
            await interaction.response.send_message("❌ Solo el usuario invitado puede aceptar esta solicitud.", ephemeral=True)
            return

        # Actualizar estado del intercambio
        pending_trades[self.trade_id]['accepted'] = True
        pending_trades[self.trade_id]['invited_accepted'] = True

        # Deshabilitar los botones
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="🔄 Intercambio Aceptado",
            description=f"{self.invited.mention} ha aceptado el intercambio.\n\nAhora ambos deben seleccionar las cartas que quieren intercambiar.",
            color=discord.Color.green()
        )
        embed.add_field(name="Instrucciones", value="• Usa las flechas para navegar\n• Presiona 'Seleccionar' para elegir cartas\n• Máximo 5 minutos para completar")
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Enviar la selección de cartas a ambos usuarios
        try:
            # Para el usuario que inició
            trade_view1 = TradeSelectionView(self.trade_id, self.inviter, self.invited)
            await self.inviter.send(f"🔄 **Intercambio con {self.invited.display_name}**", view=trade_view1)
            await trade_view1.send_initial_selection(self.inviter, True)
            
            # Para el usuario que aceptó
            trade_view2 = TradeSelectionView(self.trade_id, self.inviter, self.invited)
            await self.invited.send(f"🔄 **Intercambio con {self.inviter.display_name}**", view=trade_view2)
            await trade_view2.send_initial_selection(self.invited, False)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ No puedo enviar mensajes privados. Asegúrate de tener los MD abiertos.", ephemeral=True)

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.red)
    async def reject_callback(self, interaction, button):
        if interaction.user.id != self.invited.id:
            await interaction.response.send_message("❌ Solo el usuario invitado puede rechazar esta solicitud.", ephemeral=True)
            return

        # Eliminar intercambio
        if self.trade_id in pending_trades:
            del pending_trades[self.trade_id]

        # Deshabilitar los botones
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="❌ Intercambio Rechazado",
            description=f"{self.invited.mention} ha rechazado la solicitud de intercambio.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class TradeSelectionView(View):
    def __init__(self, trade_id, user1, user2, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.user1 = user1
        self.user2 = user2
        self.user1_index = 0
        self.user2_index = 0
        self.current_user = None

    async def send_initial_selection(self, user, is_user1):
        """Envía la selección inicial de cartas"""
        self.current_user = user
        inventory = get_inventory(user.id)
        
        if not inventory:
            await user.send("❌ No tienes cartas para intercambiar.")
            return

        index = self.user1_index if is_user1 else self.user2_index
        await self.send_card_message(user, index, is_user1)

    async def send_card_message(self, user, card_idx, is_user1):
        """Envía un mensaje con una carta específica"""
        inventory = get_inventory(user.id)
        if not inventory or card_idx >= len(inventory):
            await user.send("❌ Error al cargar las cartas.")
            return

        card = inventory[card_idx]
        
        # Verificar si el archivo de imagen existe
        try:
            file = discord.File(card["imagen"], filename="carta_trade.png")
            image_url = "attachment://carta_trade.png"
        except:
            file = None
            image_url = None
        
        rarity = card.get("rareza", "N")
        rarity_emoji = get_rarity_emoji(rarity)
        
        role = "Tus cartas" if is_user1 else "Tus cartas"
        selected_cards = pending_trades[self.trade_id]['user1_cards'] if is_user1 else pending_trades[self.trade_id]['user2_cards']
        
        embed = discord.Embed(
            title=f"🔄 Selección de Cartas - Intercambio con {self.user2.display_name if is_user1 else self.user1.display_name}",
            description=f"Selecciona las cartas que quieres intercambiar",
            color=get_rarity_color(rarity)
        )
        embed.add_field(name=f"{rarity_emoji} {card['nombre']} ({rarity})", value=card.get("descripcion", ""), inline=False)
        embed.add_field(name="Valor", value=format_gems(card.get('valor', 0)), inline=True)
        embed.add_field(name="Cartas seleccionadas", value=f"{len(selected_cards)} cartas", inline=True)
        
        if image_url:
            embed.set_image(url=image_url)
        
        embed.set_footer(text=f"Carta {card_idx + 1} de {len(inventory)}")

        # Crear botones
        view = View(timeout=300)
        
        async def prev_callback(interaction):
            if interaction.user.id != user.id:
                await interaction.response.send_message("❌ Solo puedes interactuar con tu propio intercambio.", ephemeral=True)
                return
            
            new_index = (card_idx - 1) % len(inventory)
            if is_user1:
                self.user1_index = new_index
            else:
                self.user2_index = new_index
            
            try:
                await interaction.message.delete()
            except:
                pass
            
            await self.send_card_message(user, new_index, is_user1)

        async def next_callback(interaction):
            if interaction.user.id != user.id:
                await interaction.response.send_message("❌ Solo puedes interactuar con tu propio intercambio.", ephemeral=True)
                return
            
            new_index = (card_idx + 1) % len(inventory)
            if is_user1:
                self.user1_index = new_index
            else:
                self.user2_index = new_index
            
            try:
                await interaction.message.delete()
            except:
                pass
            
            await self.send_card_message(user, new_index, is_user1)

        async def select_callback(interaction):
            if interaction.user.id != user.id:
                await interaction.response.send_message("❌ Solo puedes seleccionar cartas en tu propio intercambio.", ephemeral=True)
                return

            card = inventory[card_idx]
            trade_data = pending_trades[self.trade_id]
            selected_cards = trade_data['user1_cards'] if is_user1 else trade_data['user2_cards']
            
            # Verificar si la carta ya está seleccionada
            card_ids = [c.get('id') for c in selected_cards]
            if card.get('id') in card_ids:
                # Deseleccionar
                selected_cards = [c for c in selected_cards if c.get('id') != card.get('id')]
                action = "❌ Deseleccionada"
            else:
                # Seleccionar
                selected_cards.append(card)
                action = "✅ Seleccionada"
            
            if is_user1:
                trade_data['user1_cards'] = selected_cards
            else:
                trade_data['user2_cards'] = selected_cards
            
            pending_trades[self.trade_id] = trade_data
            
            await interaction.response.send_message(f"{action} {card['nombre']}", ephemeral=True)
            await self.send_card_message(user, card_idx, is_user1)

        async def confirm_callback(interaction):
            if interaction.user.id != user.id:
                await interaction.response.send_message("❌ Solo puedes confirmar tu propia selección.", ephemeral=True)
                return

            trade_data = pending_trades[self.trade_id]
            if is_user1:
                trade_data['user1_confirmed'] = True
            else:
                trade_data['user2_confirmed'] = True
            
            pending_trades[self.trade_id] = trade_data
            
            # Verificar si ambos confirmaron
            if trade_data['user1_confirmed'] and trade_data['user2_confirmed']:
                # Mostrar vista de confirmación final
                await self.show_final_confirmation(interaction)
            else:
                await interaction.response.send_message("✅ Selección confirmada. Esperando al otro usuario...", ephemeral=True)

        # Botones de navegación
        prev_btn = Button(label="⬅️ Anterior", style=discord.ButtonStyle.blurple)
        next_btn = Button(label="Siguiente ➡️", style=discord.ButtonStyle.blurple)
        select_btn = Button(label="🔄 Seleccionar/Deseleccionar", style=discord.ButtonStyle.green)
        confirm_btn = Button(label="✅ Confirmar Selección", style=discord.ButtonStyle.red)

        prev_btn.callback = prev_callback
        next_btn.callback = next_callback
        select_btn.callback = select_callback
        confirm_btn.callback = confirm_callback

        view.add_item(prev_btn)
        view.add_item(next_btn)
        view.add_item(select_btn)
        view.add_item(confirm_btn)

        try:
            if file:
                await user.send(embed=embed, file=file, view=view)
            else:
                await user.send(embed=embed, view=view)
        except discord.Forbidden:
            # Intentar enviar al canal original si no se pueden enviar MD
            original_channel = self.get_original_channel()
            if original_channel:
                if file:
                    await original_channel.send(f"{user.mention} {embed.description}", embed=embed, file=file, view=view)
                else:
                    await original_channel.send(f"{user.mention} {embed.description}", embed=embed, view=view)

    def get_original_channel(self):
        """Obtiene el canal original donde se inició el intercambio"""
        # Esta es una simplificación - necesitarías guardar el canal original en pending_trades
        return None

    async def show_final_confirmation(self, interaction):
        trade_data = pending_trades[self.trade_id]
        user1_cards = trade_data['user1_cards']
        user2_cards = trade_data['user2_cards']
        
        # Crear embed de confirmación final
        embed = discord.Embed(
            title="🔄 Confirmación Final de Intercambio",
            description="Ambos usuarios han confirmado sus selecciones. Revisa los detalles:",
            color=discord.Color.blue()
        )
        
        # Cartas del usuario 1
        user1_cards_text = "\n".join([f"• {card['nombre']} ({card.get('rareza', 'C')})" for card in user1_cards]) if user1_cards else "Ninguna carta seleccionada"
        embed.add_field(name=f"🎁 {self.user1.display_name} ofrece:", value=user1_cards_text, inline=False)
        
        # Cartas del usuario 2
        user2_cards_text = "\n".join([f"• {card['nombre']} ({card.get('rareza', 'C')})" for card in user2_cards]) if user2_cards else "Ninguna carta seleccionada"
        embed.add_field(name=f"🎁 {self.user2.display_name} ofrece:", value=user2_cards_text, inline=False)
        
        embed.add_field(name="⚠️ Confirmación", value="Ambos deben aceptar para completar el intercambio", inline=False)
        
        # Vista de confirmación final
        final_view = FinalTradeView(self.trade_id, self.user1, self.user2)
        
        # Enviar a ambos usuarios
        try:
            await self.user1.send(embed=embed, view=final_view)
            await self.user2.send(embed=embed, view=final_view)
            await interaction.response.send_message("✅ ¡Intercambio listo! Revisa tus mensajes privados para confirmar.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ No puedo enviar mensajes privados. Asegúrate de tener los MD abiertos.", ephemeral=True)

# ... (el resto del código de FinalTradeView y comandos se mantiene igual)

@bot.command()
async def intercambio(ctx, member: discord.Member):
    """Inicia un intercambio de cartas con otro usuario"""
    # Verificaciones básicas
    if ctx.author.id == member.id:
        await ctx.send("❌ No puedes intercambiar contigo mismo.")
        return
    
    if member.bot:
        await ctx.send("❌ No puedes intercambiar con un bot.")
        return

    # Verificar que ambos usuarios tienen cartas
    author_inv = get_inventory(ctx.author.id)
    member_inv = get_inventory(member.id)
    
    if not author_inv:
        await ctx.send("❌ No tienes cartas para intercambiar.")
        return
    
    if not member_inv:
        await ctx.send(f"❌ {member.mention} no tiene cartas para intercambiar.")
        return

    # Generar ID único para el intercambio
    trade_id = f"{ctx.author.id}_{member.id}_{int(time.time())}"
    
    # Crear datos del intercambio
    pending_trades[trade_id] = {
        'user1': ctx.author,
        'user2': member,
        'user1_cards': [],
        'user2_cards': [],
        'user1_confirmed': False,
        'user2_confirmed': False,
        'user1_final_accept': False,
        'user2_final_accept': False,
        'accepted': False,
        'invited_accepted': False,
        'created_at': time.time(),
        'channel_id': ctx.channel.id  # Guardar el canal original
    }

    # Crear vista de aceptación/rechazo
    view = AcceptRejectView(trade_id, ctx.author, member)
    
    embed = discord.Embed(
        title="🔄 Solicitud de Intercambio",
        description=f"{ctx.author.mention} quiere intercambiar cartas con {member.mention}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Instrucciones", value=f"{member.mention}, presiona **Aceptar** para comenzar el intercambio o **Rechazar** para cancelar.")
    embed.set_footer(text="Tienes 5 minutos para responder")

    await ctx.send(embed=embed, view=view)

# ----------------------------
# COMANDO CANCELAR INTERCAMBIO
# ----------------------------
@bot.command()
async def cancelar_intercambio(ctx):
    """Cancela cualquier intercambio pendiente del usuario"""
    user_id = ctx.author.id
    trades_to_remove = []
    
    for trade_id, trade_data in pending_trades.items():
        if trade_data['user1'].id == user_id or trade_data['user2'].id == user_id:
            trades_to_remove.append(trade_id)
    
    for trade_id in trades_to_remove:
        del pending_trades[trade_id]
    
    if trades_to_remove:
        await ctx.send("✅ Se cancelaron todos tus intercambios pendientes.")
    else:
        await ctx.send("❌ No tienes intercambios pendientes.")

# ----------------------------
# COMANDO ROB
# ----------------------------
@bot.command()
async def rob(ctx, member: discord.Member):
    """Intenta robar gemas a otro usuario"""
    user_id = ctx.author.id
    target_id = member.id
    
    # No se puede robar a uno mismo
    if user_id == target_id:
        await ctx.send("❌ No puedes robarte a ti mismo.")
        return
    
    # Verificar cooldown (30 minutos)
    cooldown = 30 * 60  # 30 minutos en segundos
    now = time.time()
    
    if user_id in user_last_rob and now - user_last_rob[user_id] < cooldown:
        restante = int((cooldown - (now - user_last_rob[user_id])) / 60)
        await ctx.send(f"⏰ Ya intentaste robar recientemente. Espera {restante} minutos para intentar de nuevo.")
        return
    
    # Verificar si el usuario tiene penalización activa
    if has_rob_penalty(user_id):
        penalty_end = get_rob_penalty_time(user_id)
        restante = int((penalty_end - now) / 60)
        await ctx.send(f"⏰ Tienes una penalización activa por robo fallido. Espera {restante} minutos para poder usar !trabajar nuevamente.")
        return
    
    # Verificar que el objetivo tenga gemas
    target_balance = get_balance(target_id)
    if target_balance <= 0:
        await ctx.send(f"❌ {member.display_name} no tiene gemas para robar.")
        return
    
    # Calcular cantidad a robar (entre 25-60 gemas)
    steal_amount = random.randint(25, 60)
    
    # No robar más de lo que tiene el objetivo
    if steal_amount > target_balance:
        steal_amount = target_balance
    
    # 40% de probabilidad de éxito
    success = random.random() <= 0.40
    
    # Actualizar cooldown
    user_last_rob[user_id] = now
    
    if success:
        # Robo exitoso
        add_balance(user_id, steal_amount)
        add_balance(target_id, -steal_amount)
        
        embed = discord.Embed(
            title="🦹 ¡Robo Exitoso!",
            description=f"{ctx.author.mention} le robó {format_gems(steal_amount)} a {member.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Gemas robadas", value=format_gems(steal_amount), inline=True)
        embed.add_field(name="Tu nuevo balance", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text="¡Suerte la próxima vez!")
        
        await ctx.send(embed=embed)
    else:
        # Robo fallido
        penalty_amount = 50
        user_balance = get_balance(user_id)
        
        # Verificar si el usuario tiene gemas para pagar la penalización
        if user_balance >= penalty_amount:
            add_balance(user_id, -penalty_amount)
            
            embed = discord.Embed(
                title="🚫 ¡Robo Fallido!",
                description=f"{ctx.author.mention} falló al intentar robarle a {member.mention} and perdió {format_gems(penalty_amount)}",
                color=discord.Color.red()
            )
            embed.add_field(name="Penalización", value=format_gems(penalty_amount), inline=True)
            embed.add_field(name="Tu nuevo balance", value=format_gems(get_balance(user_id)), inline=True)
            embed.set_footer(text="¡Mejor suerte la próxima vez!")
            
            await ctx.send(embed=embed)
        else:
            # No tiene gemas para pagar, aplicar penalización de tiempo
            penalty_duration = 60 * 60  # 1 hora en segundos
            penalty_end = now + penalty_duration
            set_rob_penalty(user_id, penalty_end)
            
            embed = discord.Embed(
                title="🚫 ¡Robo Fallido!",
                description=f"{ctx.author.mention} falló al intentar robarle a {member.mention}",
                color=discord.Color.red()
            )
            embed.add_field(name="Penalización", value="No tenías gemas para pagar la multa", inline=True)
            embed.add_field(name="Consecuencia", value="Tu próximo !trabajar tendrá 1 hora adicional de cooldown", inline=True)
            embed.set_footer(text="La penalización durará 1 hora")
            
            await ctx.send(embed=embed)

# ----------------------------
# MINIJUEGO DE ADIVINANZA
# ----------------------------
@bot.command()
async def adivina(ctx):
    user_id = ctx.author.id
    now = time.time()
    cooldown = 3600  # 1 hora en segundos

    # Verificar cooldown
    if user_id in user_last_adivina and now - user_last_adivina[user_id] < cooldown:
        restante = int((cooldown - (now - user_last_adivina[user_id])) / 60)
        await ctx.send(f"⏰ Ya jugaste recientemente. Espera {restante} minutos para jugar de nuevo.")
        return

    # Generar número aleatorio entre 1 y 10
    numero_secreto = random.randint(1, 10)
    intentos_restantes = 3
    
    await ctx.send(f"🎯 **¡Adivina el número!**\n{ctx.author.mention}, estoy pensando en un número entre 1 y 10.\nTienes {intentos_restantes} intentos. ¡Buena suerte!")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

    while intentos_restantes > 0:
        try:
            msg = await bot.wait_for('message', timeout=30.0, check=check)
            intento = int(msg.content)
            
            if intento == numero_secreto:
                # ¡GANÓ!
                recompensa = random.randint(20, 50)
                add_balance(user_id, recompensa)
                user_last_adivina[user_id] = now
                
                await ctx.send(f"🎉 **¡Correcto!** 🎉\nEl número era {numero_secreto}. ¡Has ganado {format_gems(recompensa)}! 💎")
                return
                
            elif intento < numero_secreto:
                intentos_restantes -= 1
                if intentos_restantes > 0:
                    await ctx.send(f"📈 **Más alto**. Te quedan {intentos_restantes} intentos.")
                else:
                    await ctx.send(f"📈 **Más alto**. ¡Oh no! Se te acabaron los intentos.")
                    
            else:
                intentos_restantes -= 1
                if intentos_restantes > 0:
                    await ctx.send(f"📉 **Más bajo**. Te quedan {intentos_restantes} intentos.")
                else:
                    await ctx.send(f"📉 **Más bajo**. ¡Oh no! Se te acabaron los intentos.")
                    
        except asyncio.TimeoutError:
            await ctx.send("⏰ ¡Tiempo agotado! No respondiste a tiempo.")
            return

    # Si llegó aquí, perdió
    user_last_adivina[user_id] = now
    await ctx.send(f"😢 **Game Over**\nEl número era {numero_secreto}. ¡Mejor suerte la próxima vez!")

    # ----------------------------
# SISTEMA DE RECOMPENSAS TEMPORALES
# ----------------------------
recompensa_activa = None
recompensa_claimers = set()  # Usuarios que ya reclamaron

# COMANDO PARA ADMIN: CREAR RECOMPENSA
@bot.command()
@commands.has_permissions(administrator=True)
async def recompensa_tiempo(ctx, card_id: str = None, duracion_minutos: int = 60):
    """
    Crea una recompensa temporal que todos pueden reclamar
    !recompensa_tiempo UR001 30  (30 minutos)
    !recompensa_tiempo SP005 60  (1 hora)
    """
    
    global recompensa_activa, recompensa_claimers
    
    if not card_id:
        embed = discord.Embed(
            title="❌ Uso Incorrecto",
            description=(
                "**Sintaxis:** `!recompensa_tiempo <card_id> <minutos>`\n\n"
                "**Ejemplos:**\n"
                "• `!recompensa_tiempo UR001 30` - 30 minutos\n"
                "• `!recompensa_tiempo SP005 60` - 1 hora\n"
                "• `!recompensa_tiempo C012 120` - 2 horas\n\n"
                "**Nota:** Todos los usuarios podrán reclamar con `!recibir_recompensa`"
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Buscar carta
    found_card = None
    for card in catalog_cards:
        if card.get("id", "").upper() == card_id.upper():
            found_card = card
            break
    
    if not found_card:
        await ctx.send(f"❌ No se encontró ninguna carta con ID `{card_id}`.")
        return

    # Configurar recompensa
    recompensa_activa = {
        'carta': found_card,
        'inicio_tiempo': time.time(),
        'duracion': duracion_minutos * 60,  # Convertir a segundos
        'creador': ctx.author
    }
    recompensa_claimers.clear()  # Resetear lista de reclamantes

    # Embed de anuncio
    rarity = found_card.get("rareza", "N")
    rarity_emoji = get_rarity_emoji(rarity)
    
    embed = discord.Embed(
        title="🎉 ¡RECOMPENSA TEMPORAL ACTIVADA!",
        description=f"**¡{ctx.author.mention} ha activado una recompensa para todos!**",
        color=get_rarity_color(rarity)
    )
    
    embed.add_field(
        name=f"{rarity_emoji} Carta de Recompensa",
        value=f"**{found_card['nombre']}**\nRareza: {rarity}",
        inline=False
    )
    
    embed.add_field(
        name="⏰ Duración",
        value=f"{duracion_minutos} minutos",
        inline=True
    )
    
    embed.add_field(
        name="🎯 Cómo reclamar",
        value="Usa `!recibir_recompensa`",
        inline=True
    )
    
    embed.add_field(
        name="⚠️ Importante",
        value="Solo puedes reclamar **UNA VEZ** por recompensa",
        inline=False
    )
    
    embed.set_footer(text=f"Recompensa activa hasta: {duracion_minutos} minutos")
    
    # Mostrar imagen si existe
    image_path = found_card.get("imagen", "")
    if image_path and os.path.exists(image_path):
        try:
            file = discord.File(image_path, filename="recompensa.png")
            embed.set_thumbnail(url="attachment://recompensa.png")
            await ctx.send(embed=embed, file=file)
        except:
            await ctx.send(embed=embed)
    else:
        await ctx.send(embed=embed)
    
    # Programar fin de recompensa
    bot.loop.create_task(finalizar_recompensa_automaticamente(ctx, duracion_minutos * 60))

async def finalizar_recompensa_automaticamente(ctx, duracion_segundos):
    """Finaliza la recompensa automáticamente después del tiempo especificado"""
    await asyncio.sleep(duracion_segundos)
    
    global recompensa_activa
    if recompensa_activa:
        carta_nombre = recompensa_activa['carta']['nombre']
        total_reclamantes = len(recompensa_claimers)
        
        embed = discord.Embed(
            title="⏰ Recompensa Finalizada",
            description=f"La recompensa de **{carta_nombre}** ha terminado.",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="📊 Estadísticas",
            value=f"**{total_reclamantes}** usuarios reclamaron la recompensa",
            inline=False
        )
        
        await ctx.send(embed=embed)
        recompensa_activa = None
        recompensa_claimers.clear()

# COMANDO PARA USUARIOS: RECLAMAR RECOMPENSA
@bot.command()
async def recibir_recompensa(ctx):
    """Reclama la recompensa temporal activa"""
    global recompensa_activa, recompensa_claimers
    
    if not recompensa_activa:
        embed = discord.Embed(
            title="❌ No hay recompensas activas",
            description="No hay ninguna recompensa disponible en este momento.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="💡 Información",
            value="Los administradores pueden crear recompensas con `!recompensa_tiempo`",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    # Verificar si ya reclamó
    if ctx.author.id in recompensa_claimers:
        embed = discord.Embed(
            title="⚠️ Ya reclamaste esta recompensa",
            description="Solo puedes reclamar una vez por recompensa activa.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        return
    
    # Verificar tiempo restante
    tiempo_transcurrido = time.time() - recompensa_activa['inicio_tiempo']
    tiempo_restante = recompensa_activa['duracion'] - tiempo_transcurrido
    
    if tiempo_restante <= 0:
        embed = discord.Embed(
            title="⏰ Recompensa Expirada",
            description="Esta recompensa ya ha terminado.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        recompensa_activa = None
        recompensa_claimers.clear()
        return
    
    # Dar la carta al usuario
    carta = recompensa_activa['carta']
    try:
        card_copy = carta.copy()
        add_to_inventory(ctx.author.id, card_copy)
        recompensa_claimers.add(ctx.author.id)
        
        # Embed de éxito
        rarity = carta.get("rareza", "N")
        rarity_emoji = get_rarity_emoji(rarity)
        
        embed = discord.Embed(
            title="🎁 ¡Recompensa Reclamada!",
            description=f"{ctx.author.mention} ha reclamado la recompensa",
            color=get_rarity_color(rarity)
        )
        
        embed.add_field(
            name=f"{rarity_emoji} Carta Obtenida",
            value=f"**{carta['nombre']}**\nRareza: {rarity}",
            inline=False
        )
        
        minutos_restantes = int(tiempo_restante / 60)
        embed.add_field(
            name="⏰ Tiempo restante",
            value=f"{minutos_restantes} minutos",
            inline=True
        )
        
        total_reclamantes = len(recompensa_claimers)
        embed.add_field(
            name="👥 Total reclamantes",
            value=f"{total_reclamantes} usuarios",
            inline=True
        )
        
        # Mostrar imagen si existe
        image_path = carta.get("imagen", "")
        if image_path and os.path.exists(image_path):
            try:
                file = discord.File(image_path, filename="carta_recompensa.png")
                embed.set_thumbnail(url="attachment://carta_recompensa.png")
                await ctx.send(embed=embed, file=file)
            except:
                await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed)
            
    except Exception as e:
        await ctx.send(f"❌ Error al reclamar la recompensa: {str(e)}")

# COMANDO PARA VER ESTADO DE RECOMPENSA
@bot.command()
async def estado_recompensa(ctx):
    """Muestra el estado de la recompensa actual"""
    global recompensa_activa, recompensa_claimers
    
    if not recompensa_activa:
        embed = discord.Embed(
            title="📭 No hay recompensas activas",
            description="Actualmente no hay ninguna recompensa disponible.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="💡 ¿Cómo crear recompensas?",
            value="Los administradores pueden usar `!recompensa_tiempo <carta> <minutos>`",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    carta = recompensa_activa['carta']
    rarity = carta.get("rareza", "N")
    rarity_emoji = get_rarity_emoji(rarity)
    
    # Calcular tiempo restante
    tiempo_transcurrido = time.time() - recompensa_activa['inicio_tiempo']
    tiempo_restante = recompensa_activa['duracion'] - tiempo_transcurrido
    minutos_restantes = max(0, int(tiempo_restante / 60))
    
    embed = discord.Embed(
        title="🎯 Recompensa Activa",
        description="¡Hay una recompensa disponible para todos!",
        color=get_rarity_color(rarity)
    )
    
    embed.add_field(
        name=f"{rarity_emoji} Carta",
        value=f"**{carta['nombre']}**\nRareza: {rarity}",
        inline=False
    )
    
    embed.add_field(
        name="⏰ Tiempo restante",
        value=f"{minutos_restantes} minutos",
        inline=True
    )
    
    embed.add_field(
        name="👥 Reclamantes",
        value=f"{len(recompensa_claimers)} usuarios",
        inline=True
    )
    
    embed.add_field(
        name="🎯 Cómo reclamar",
        value="Usa `!recibir_recompensa`",
        inline=False
    )
    
    # Mostrar imagen si existe
    image_path = carta.get("imagen", "")
    if image_path and os.path.exists(image_path):
        try:
            file = discord.File(image_path, filename="recompensa_activa.png")
            embed.set_thumbnail(url="attachment://recompensa_activa.png")
            await ctx.send(embed=embed, file=file)
        except:
            await ctx.send(embed=embed)
    else:
        await ctx.send(embed=embed)

# COMANDO PARA ADMIN: CANCELAR RECOMPENSA
@bot.command()
@commands.has_permissions(administrator=True)
async def cancelar_recompensa(ctx):
    """Cancela la recompensa activa"""
    global recompensa_activa, recompensa_claimers
    
    if not recompensa_activa:
        await ctx.send("❌ No hay ninguna recompensa activa para cancelar.")
        return
    
    carta_nombre = recompensa_activa['carta']['nombre']
    total_reclamantes = len(recompensa_claimers)
    
    recompensa_activa = None
    recompensa_claimers.clear()
    
    embed = discord.Embed(
        title="🗑️ Recompensa Cancelada",
        description=f"La recompensa de **{carta_nombre}** ha sido cancelada.",
        color=discord.Color.orange()
    )
    embed.add_field(
        name="📊 Estadísticas finales",
        value=f"**{total_reclamantes}** usuarios reclamaron antes de cancelar",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ----------------------------
# GACHA MEJORADO (Ahora incluye L, SP, UR, SSR, R, N, C)
# ----------------------------

# Nuevas probabilidades que incluyen todas las rarezas del gacha
rarity_probabilities = {
    "G": 0.010,   # Galaxia (1%) - aumentado de 0.5%
    "SP": 0.020,  # Special (2%) - aumentado de 1%
    "UR": 0.035,  # Ultra Raro (3.5%) - aumentado de 1.5%
    "SSR": 0.065, # Super Super Raro (6.5%) - aumentado de 3%
    "R": 0.100,  # Super Raro (10%) - aumentado de 6%
    "N": 0.770,   # Normal (77%) - aumentado de 20%
}

# 🎲 Gacha gratuita
@bot.command()
async def gacha(ctx):
    user_id = ctx.author.id
    now = time.time()
    cooldown = 4 * 3600  # 4 horas

    if user_id in user_last_gacha and now - user_last_gacha[user_id] < cooldown:
        restante = int((cooldown - (now - user_last_gacha[user_id])) / 60)
        await ctx.send(f"❌ Ya usaste tu tirada gratuita, espera {restante} minutos.")
        return

    user_last_gacha[user_id] = now

    # Filtrar las rarezas que nos interesan (G, SP, UR, SSR, R, N, C)
    # NOTA: Las cartas "E" (Evento) NO salen en el gacha, solo las regalan admins
    target_rarities = ["G", "SP", "UR", "SSR", "R", "N"]
    available_rarities = []
    available_probabilities = []
    
    # Verificar que cada rareza tenga cartas disponibles
    for rarity in target_rarities:
        if rarity in cards_catalog and cards_catalog[rarity] and rarity in rarity_probabilities:
            available_rarities.append(rarity)
            available_probabilities.append(rarity_probabilities[rarity])
        else:
            print(f"⚠️  Rareza {rarity} no disponible en el gacha (sin cartas o probabilidad)")
    
    if not available_rarities:
        await ctx.send("❌ No hay cartas disponibles en el catálogo.")
        return

    # Ajustar probabilidades para que sumen 1
    total_prob = sum(available_probabilities)
    if total_prob <= 0:
        # Fallback: probabilidades iguales
        available_probabilities = [1.0/len(available_rarities)] * len(available_rarities)
        total_prob = 1.0
        
    # Normalizar probabilidades
    normalized_probs = [prob/total_prob for prob in available_probabilities]
    
    # Debug: mostrar probabilidades
    print(f"🎲 Gacha - Rarezas disponibles: {available_rarities}")
    print(f"🎲 Gacha - Probabilidades: {normalized_probs}")
    
    try:
        # Seleccionar rareza según probabilidades
        rarity = random.choices(available_rarities, normalized_probs, k=1)[0]
        card = random.choice(cards_catalog[rarity])
        add_to_inventory(user_id, card)

        rarity_emoji = get_rarity_emoji(rarity)
        embed = discord.Embed(
            title=f"{rarity_emoji} {card['nombre']} ({rarity}) {rarity_emoji}",
            description=card.get("descripcion", ""),
            color=get_rarity_color(rarity)
        )
        
        # Mostrar stats de la carta
        stats = card.get("stats", {})
        if stats:
            stats_text = []
            for stat_name, stat_value in stats.items():
                if stat_value > 1:  # Solo mostrar stats que no sean 1 (valor por defecto)
                    stats_text.append(f"{stat_name}: {stat_value}")
            if stats_text:
                embed.add_field(name="📊 Estadísticas", value="\n".join(stats_text), inline=False)
        
        file = discord.File(card["imagen"], filename="carta.png")
        embed.set_image(url="attachment://carta.png")
        embed.set_footer(text=f"¡Felicidades por obtener una carta {rarity}!")

        await ctx.send(
            content=f"🎉 {ctx.author.mention} obtuvo una carta!",
            embed=embed,
            file=file
        )
        
    except (IndexError, KeyError) as e:
        print(f"❌ Error en gacha: {e}")
        # Fallback seguro si algo sale mal
        safe_rarities = ["N", "R", "SSR", "UR", "SP", "G"]
        for safe_r in safe_rarities:
            if safe_r in cards_catalog and cards_catalog[safe_r]:
                card = random.choice(cards_catalog[safe_r])
                add_to_inventory(user_id, card)
                
                rarity_emoji = get_rarity_emoji(safe_r)
                embed = discord.Embed(
                    title=f"{rarity_emoji} {card['nombre']} ({safe_r}) {rarity_emoji}",
                    description=card.get("descripcion", ""),
                    color=get_rarity_color(safe_r)
                )
                
                file = discord.File(card["imagen"], filename="carta.png")
                embed.set_image(url="attachment://carta.png")
                embed.set_footer(text=f"¡Felicidades por obtener una carta {safe_r}!")

                await ctx.send(
                    content=f"🎉 {ctx.author.mention} obtuvo una carta! (Fallback)",
                    embed=embed,
                    file=file
                )
                break
        else:
            await ctx.send("❌ Error crítico: No hay cartas disponibles en el sistema.")


# 💰 Comprar tiradas - VERSIÓN CON PARÁMETROS
@bot.command()
async def gacha_comprar(ctx, cantidad: int = 1):
    """Compra tiradas de gacha con gemas
    Ejemplos:
    !gacha_comprar 1    - Compra 1 tirada
    !gacha_comprar 5    - Compra 5 tiradas  
    !gacha_comprar 10   - Compra 10 tiradas
    """
    
    # Validar la cantidad
    if cantidad not in [1, 5, 10]:
        await ctx.send("❌ Cantidad inválida. Solo puedes comprar 1, 5 o 10 tiradas.")
        return
    
    # Filtrar las rarezas del gacha (L, SP, UR, SSR, R, N, C)
    target_rarities = ["G", "SP", "UR", "SSR", "R", "N"]
    available_rarities = []
    available_probabilities = []
    
    for rarity in target_rarities:
        if rarity in cards_catalog and cards_catalog[rarity] and rarity in rarity_probabilities:
            available_rarities.append(rarity)
            available_probabilities.append(rarity_probabilities[rarity])
    
    if not available_rarities:
        await ctx.send("❌ No hay cartas disponibles en el catálogo.")
        return

    user_id = ctx.author.id
    cost = 80 * cantidad
    current_gems = get_balance(user_id)
    
    # Verificar si tiene suficientes gemas
    if current_gems < cost:
        await ctx.send(
            f"❌ No tienes suficientes gemas. Necesitas {format_gems(cost)}. Actualmente tienes {format_gems(current_gems)}."
        )
        return

    # Procesar el pago
    add_balance(user_id, -cost)
    
    # Obtener las cartas
    cartas_obtenidas = []
    
    for _ in range(cantidad):
        # Normalizar probabilidades
        total_prob = sum(available_probabilities)
        if total_prob <= 0:
            normalized_probs = [1.0/len(available_rarities)] * len(available_rarities)
        else:
            normalized_probs = [prob/total_prob for prob in available_probabilities]
        
        try:
            rarity = random.choices(available_rarities, normalized_probs, k=1)[0]
            card = random.choice(cards_catalog[rarity])
            card_copy = card.copy()  # Hacer copia para evitar referencia
            add_to_inventory(user_id, card_copy)
            cartas_obtenidas.append(card_copy)
        except (IndexError, KeyError) as e:
            print(f"Error en gacha: {e}")
            # Fallback a carta común
            if "N" in cards_catalog and cards_catalog["N"]:
                card = random.choice(cards_catalog["N"])
                card_copy = card.copy()
                add_to_inventory(user_id, card_copy)
                cartas_obtenidas.append(card_copy)

    # Mensaje de confirmación
    embed = discord.Embed(
        title="✅ Compra Exitosa",
        description=f"Has comprado {cantidad} tirada(s) por {format_gems(cost)}",
        color=discord.Color.green()
    )
    embed.add_field(name="💰 Gems gastadas", value=format_gems(cost), inline=True)
    embed.add_field(name="💎 Gems restantes", value=format_gems(get_balance(user_id)), inline=True)
    embed.add_field(name="📦 Cartas obtenidas", value=f"{len(cartas_obtenidas)} carta(s)", inline=False)
    
    await ctx.send(embed=embed)
    
    # Mostrar las cartas obtenidas en un carrusel
    if cartas_obtenidas:
        await show_cards_carousel(ctx, cartas_obtenidas, title="🎁 Cartas Obtenidas")
# ----------------------------
# Función robusta para mostrar carrusel de cartas (CORREGIDA)
# ----------------------------
async def show_cards_carousel(ctx_or_interaction, cards, title=None):
    if not cards:
        if hasattr(ctx_or_interaction, 'response'):
            await ctx_or_interaction.response.send_message("No hay cartas para mostrar.", ephemeral=True)
        else:
            await ctx_or_interaction.send("No hay cartas para mostrar.")
        return

    index = 0
    current_message = None

    # Función para crear un mensaje con una carta específica
    async def send_card_message(channel, card_idx, view=None):
        nonlocal current_message
        
        card = cards[card_idx]
        
        # Verificar si la imagen existe y manejarla correctamente
        image_path = card.get("imagen", "")
        file = None
        image_url = None
        
        if image_path and os.path.exists(image_path):
            try:
                file = discord.File(image_path, filename="carta.png")
                image_url = "attachment://carta.png"
            except Exception as e:
                print(f"❌ Error cargando imagen {image_path}: {e}")
        else:
            print(f"⚠️  Imagen no encontrada: {image_path}")
        
        # Determinar el título del embed
        if card_idx == 0 and title:
            embed_title = title
        else:
            rarity = card.get("rareza", "N")
            rarity_emoji = get_rarity_emoji(rarity)
            embed_title = f"{rarity_emoji} {card['nombre']} ({rarity}) {rarity_emoji}"
        
        embed = discord.Embed(
            title=embed_title,
            description=card.get("descripcion", ""),
            color=get_rarity_color(card.get("rareza", "N"))
        )
        embed.add_field(name="Valor", value=format_gems(card.get('valor', 0)), inline=True)
        
        if image_url:
            embed.set_image(url=image_url)
            
        embed.set_footer(text=f"Carta {card_idx + 1} de {len(cards)}")
        
        # Si ya existe un mensaje, editarlo en lugar de crear uno nuevo
        if current_message and not hasattr(ctx_or_interaction, 'response'):
            try:
                if file:
                    await current_message.edit(embed=embed, attachments=[file], view=view)
                else:
                    await current_message.edit(embed=embed, view=view)
                return current_message
            except Exception as e:
                print(f"❌ Error editando mensaje: {e}")
                # Si falla la edición, crear nuevo mensaje
                current_message = None
        
        # Crear nuevo mensaje
        if hasattr(ctx_or_interaction, 'response') and ctx_or_interaction.response.is_done():
            # Para interacciones después de la respuesta inicial
            if file:
                new_message = await channel.send(embed=embed, file=file, view=view)
            else:
                new_message = await channel.send(embed=embed, view=view)
        else:
            # Para comandos normales o primera respuesta
            if file:
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(embed=embed, file=file, view=view)
                    new_message = await ctx_or_interaction.original_response()
                else:
                    new_message = await channel.send(embed=embed, file=file, view=view)
            else:
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(embed=embed, view=view)
                    new_message = await ctx_or_interaction.original_response()
                else:
                    new_message = await channel.send(embed=embed, view=view)
        
        current_message = new_message
        return new_message

    # Crear view con botones
    view = View(timeout=180)

    async def prev_callback(interaction):
        nonlocal index
        author_id = ctx_or_interaction.author.id if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user.id
        if interaction.user.id != author_id:
            await interaction.response.send_message("❌ Solo el dueño del inventario puede navegar.", ephemeral=True)
            return
            
        new_index = (index - 1) % len(cards)
        index = new_index
        
        await interaction.response.defer()
        await send_card_message(interaction.channel, index, view)

    async def next_callback(interaction):
        nonlocal index
        author_id = ctx_or_interaction.author.id if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user.id
        if interaction.user.id != author_id:
            await interaction.response.send_message("❌ Solo el dueño del inventario puede navegar.", ephemeral=True)
            return
            
        new_index = (index + 1) % len(cards)
        index = new_index
        
        await interaction.response.defer()
        await send_card_message(interaction.channel, index, view)

    prev_btn = Button(label="⬅️ Anterior", style=discord.ButtonStyle.blurple)
    next_btn = Button(label="Siguiente ➡️", style=discord.ButtonStyle.blurple)
    prev_btn.callback = prev_callback
    next_btn.callback = next_callback
    view.add_item(prev_btn)
    view.add_item(next_btn)

    # Enviar mensaje inicial
    if hasattr(ctx_or_interaction, 'response') and not ctx_or_interaction.response.is_done():
        # Para interacciones que no han respondido
        await send_card_message(ctx_or_interaction.channel, 0, view)
    else:
        # Para comandos normales o interacciones que ya respondieron
        await send_card_message(ctx_or_interaction.channel if hasattr(ctx_or_interaction, 'channel') else ctx_or_interaction, 0, view)



# 💼 trabajar (cada 4 hrs) - CON MODIFICACIÓN PARA PENALIZACIONES
@bot.command()
async def trabajar(ctx):
    user_id = ctx.author.id
    now = time.time()
    cooldown = 4 * 3600  # 4 horas base
    
    # Verificar si tiene penalización activa
    if has_rob_penalty(user_id):
        cooldown += 3600  # Añadir 1 hora extra de cooldown
        penalty_end = get_rob_penalty_time(user_id)
        if now < penalty_end:
            # Aún tiene penalización activa
            restante = int((penalty_end - now) / 60)
            await ctx.send(f"⏰ Tienes una penalización activa por robo fallido. Espera {restante} minutos para poder trabajar.")
            return
        else:
            # La penalización ya expiró, eliminarla
            uid = str(user_id)
            if uid in user_rob_penalties:
                del user_rob_penalties[uid]
                save_data()
    
    # Verificar cooldown normal
    if user_id in user_last_trabajar and now - user_last_trabajar[user_id] < cooldown:
        restante = int((cooldown - (now - user_last_trabajar[user_id])) / 60)
        await ctx.send(f"💼 Debes esperar {restante} minutos para volver a trabajar.")
        return

    # PROBABILIDAD DE FALLAR: 5% a 10%
    fail_chance = random.uniform(0.05, 0.10)  # 5% a 10% de probabilidad de fallar
    if random.random() < fail_chance:
        # FALLO - No gana gemas
        user_last_trabajar[user_id] = now
        
        # Mensajes de fallo aleatorios
        fail_messages = [
            "💼 ¡Oh no! Tu jefe te despidió por llegar tarde. No ganaste gemas esta vez.",
            "💼 La empresa quebró justo cuando ibas a cobrar. Mejor suerte la próxima vez.",
            "💼 Te quedaste dormido y perdiste tu turno de trabajo. No ganaste gemas.",
            "💼 Tu computadora se apagó y perdiste todo tu progreso. No ganaste gemas hoy.",
            "💼 Hubo un recorte de personal y fuiste el primero en ser despedido. No gemas esta vez.",
            "💼 Tu cliente canceló el proyecto a último momento. No hay pago para ti.",
            "💼 Te hackearon la cuenta y robaron tu salario. No ganaste gemas.",
            "💼 Tu jefe encontró a alguien que trabaja más barato. No ganaste gemas.",
            "💼 Hubo un problema técnico y no pudiste completar tu trabajo. No hay pago.",
            "💼 Te confundiste de horario y trabajaste cuando no debías. No ganaste gemas."
        ]
        
        fail_message = random.choice(fail_messages)
        
        # Mensaje especial si acaba de terminar una penalización
        if user_id in user_rob_penalties and now >= user_rob_penalties.get(str(user_id), 0):
            uid = str(user_id)
            if uid in user_rob_penalties:
                del user_rob_penalties[uid]
                save_data()
            await ctx.send(f"{fail_message} ¡Pero al menos tu penalización ha terminado!")
        else:
            await ctx.send(f"{fail_message} Total: {format_gems(get_balance(user_id))}")
        
        return

    # ÉXITO - Gana gemas normalmente (95% a 90% de probabilidad)
    reward = random.randint(20, 40)
    add_balance(user_id, reward)
    user_last_trabajar[user_id] = now
    
    # Mensajes de éxito aleatorios
    success_messages = [
        f"💼 {ctx.author.mention} completó un proyecto exitosamente y ganó {format_gems(reward)}!",
        f"💼 {ctx.author.mention} recibió un bono por buen desempeño: {format_gems(reward)}!",
        f"💼 {ctx.author.mention} trabajó horas extras y ganó {format_gems(reward)}!",
        f"💼 {ctx.author.mention} cerró un trato importante y ganó {format_gems(reward)}!",
        f"💼 {ctx.author.mention} completó sus tareas eficientemente y ganó {format_gems(reward)}!"
    ]
    
    success_message = random.choice(success_messages)
    
    # Mensaje especial si acaba de terminar una penalización
    if user_id in user_rob_penalties and now >= user_rob_penalties.get(str(user_id), 0):
        uid = str(user_id)
        if uid in user_rob_penalties:
            del user_rob_penalties[uid]
            save_data()
        await ctx.send(f"{success_message} ¡Y tu penalización ha terminado! Total: {format_gems(get_balance(user_id))}")
    else:
        await ctx.send(f"{success_message} Total: {format_gems(get_balance(user_id))}")


# Mapeo de rareza para el orden (Asegúrate de que esto esté definido globalmente en main.py)
# 0 es la rareza más alta (mayor)
RARITY_ORDER = {"G": 0, "SP": 1, "UR": 2, "SSR": 3, "R": 4, "N": 5}

def get_rarity_sort_key(card):
    """Obtiene la clave de rareza para ordenar (0 es la más rara/mayor)."""
    rarity = card.get("rareza", "N")
    return RARITY_ORDER.get(rarity, 99) 

# --- CLASE VIEW RESTAURADA Y CORREGIDA ---

class InventoryView(View):
    def __init__(self, ctx, unique_inv, total_inv_count, total_gems):
        super().__init__(timeout=180)
        self.ctx = ctx
        # Este es el inventario de cartas únicas y ordenadas
        self.inv = unique_inv 
        self.total_inv_count = total_inv_count # Cuenta total para el resumen
        self.author_id = ctx.author.id
        self.index = 0
        self.message = None
        self.total_gems = total_gems
        
        # FIX: Inicializar los botones correctamente y añadir el callback
        self.prev_button = discord.ui.Button(label="⬅️ Anterior", style=discord.ButtonStyle.blurple)
        self.next_button = discord.ui.Button(label="Siguiente ➡️", style=discord.ButtonStyle.blurple)
        
        self.prev_button.callback = self.prev_callback
        self.next_button.callback = self.next_callback
        
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def update_message(self, interaction=None):
        if not self.inv:
            return # No debería pasar si se maneja antes, pero por seguridad
            
        card = self.inv[self.index]
        rarity = card.get("rareza", "N")
        rarity_emoji = get_rarity_emoji(rarity)
        
        # --- Construcción del Embed (Carrusel de 1 Carta) ---
        embed = discord.Embed(
            title=f"{rarity_emoji} {card['nombre']} ({rarity})",
            description=card.get("descripcion", ""),
            color=get_rarity_color(rarity)
        )
        # Añadir las características de la carta
        embed.add_field(name="Valor", value=format_gems(card.get('valor', 0)), inline=True)
        # Mostrar qué carta única se está viendo, y el total de cartas en el inventario
        embed.set_footer(text=f"Carta Única {self.index + 1} de {len(self.inv)} | Total de cartas: {self.total_inv_count}")
        
        file = None
        
        try:
            # Adjuntar la imagen de la carta
            file = discord.File(card["imagen"], filename="carta.png")
            embed.set_image(url="attachment://carta.png")
        except Exception as e:
            # Si falla la imagen, simplemente se imprime el error y se envía sin ella
            print(f"Error cargando imagen: {e}")
            
        # Actualizar el estado de los botones
        # Los botones se deshabilitan si solo hay 1 carta única
        self.prev_button.disabled = len(self.inv) <= 1
        self.next_button.disabled = len(self.inv) <= 1

        # Enviar o editar el mensaje
        if self.message:
            await self.message.edit(embed=embed, attachments=[file] if file else [], view=self)
        elif interaction:
            await interaction.response.send_message(embed=embed, file=file, view=self)
        else:
            self.message = await self.ctx.send(embed=embed, file=file, view=self)

    # Callbacks (Ahora como métodos normales, referenciados en __init__)
    async def prev_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo puedes navegar tu propio inventario.", ephemeral=True)
            return
            
        self.index = (self.index - 1) % len(self.inv)
        await interaction.response.defer()
        await self.update_message()

    async def next_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo puedes navegar tu propio inventario.", ephemeral=True)
            return
            
        self.index = (self.index + 1) % len(self.inv)
        await interaction.response.defer()
        await self.update_message()

# --- La función de comando principal ---

@bot.command()
async def inventario(ctx):
    """Muestra el inventario del usuario con carrusel de cartas únicas, ordenadas por rareza."""
    user_id = ctx.author.id
    inv = get_inventory(user_id) # Inventario completo, con duplicados
    gems = get_balance(user_id)
    
    # 1. Manejo de Inventario Vacío
    if not inv:
        embed = discord.Embed(
            title="📦 Inventario Vacío",
            description="No tienes cartas todavía. ¡Usa `!gacha` para obtener algunas!",
            color=discord.Color.blue()
        )
        embed.add_field(name="💎 Gemas actuales", value=format_gems(gems))
        await ctx.send(embed=embed)
        return
        
    # 2. **FILTRAR REPETIDOS y OBTENER LA LISTA ÚNICA**
    seen_names = set()
    unique_inv = []
    # Usamos el set para garantizar unicidad por nombre
    for card in inv:
        if card['nombre'] not in seen_names:
            unique_inv.append(card)
            seen_names.add(card['nombre'])
    
    # 3. **ORDENAR POR RAREZA (Mayor a Menor)**
    unique_inv.sort(key=get_rarity_sort_key)
    
    # 4. Mostrar información básica (Resumen)
    embed = discord.Embed(
        title=f"💎 Inventario de {ctx.author.display_name}",
        description=f"Navega tus **{len(unique_inv)}** cartas únicas a continuación. (Orden: Mayor Rareza a Menor)",
        color=discord.Color.gold()
    )
    embed.add_field(name="Gemas", value=format_gems(gems), inline=True)
    embed.add_field(name="Total de cartas (incl. duplicados)", value=str(len(inv)), inline=True)
    
    # Contar por rareza (usando el inventario completo, no el único)
    rarity_count = {}
    for card in inv:
        rarity = card.get("rareza", "N")
        rarity_count[rarity] = rarity_count.get(rarity, 0) + 1
    
    rarity_text = ""
    # Se itera en el orden deseado para mostrar el resumen
    for rarity in ["G", "SP", "UR", "SSR", "R", "N"]:
        if rarity in rarity_count:
            emoji = get_rarity_emoji(rarity)
            rarity_text += f"{emoji} {rarity}: {rarity_count[rarity]}\n"
    
    if rarity_text:
        embed.add_field(name="📊 Cartas por rareza", value=rarity_text, inline=False)
    
    # Envía el resumen y luego el carrusel
    await ctx.send(embed=embed)
    
    # 5. Mostrar el carrusel de cartas únicas y ordenadas
    view = InventoryView(ctx, unique_inv, len(inv), gems)
    
    # No es necesario deshabilitar los botones si len(unique_inv) <= 1, el View lo hará.
    await view.update_message()

# ----------------------------
# COMANDO VENDER EN CARRUSEL (se cierra tras vender 1 carta)
# ----------------------------
@bot.command()
async def vender(ctx):
    """Permite vender cartas del inventario usando un carrusel (se detiene tras 1 venta)"""
    user_id = ctx.author.id
    inventory = get_inventory(user_id)

    if not inventory:
        await ctx.send("📭 No tienes cartas en tu inventario para vender.")
        return

    index = 0

    async def send_card_message(channel, card_idx, view=None):
        card = inventory[card_idx]
        file = discord.File(card["imagen"], filename=f"carta_{card_idx}.png")
        rarity = card.get("rareza", "N")
        rarity_emoji = get_rarity_emoji(rarity)

        embed = discord.Embed(
            title=f"{rarity_emoji} {card['nombre']} ({rarity}) {rarity_emoji}",
            description=card.get("descripcion", ""),
            color=get_rarity_color(rarity)
        )
        embed.add_field(name="Valor de venta", value=format_gems(card.get('valor', 0)))
        embed.set_image(url=f"attachment://carta_{card_idx}.png")
        embed.set_footer(text=f"Carta {card_idx + 1} de {len(inventory)}")

        return await channel.send(embed=embed, file=file, view=view)

    # View con botones
    view = View(timeout=180)

    async def prev_callback(interaction):
        nonlocal index
        index = (index - 1) % len(inventory)
        try:
            await interaction.message.delete()
        except:
            pass
        await send_card_message(interaction.channel, index, view)

    async def next_callback(interaction):
        nonlocal index
        index = (index + 1) % len(inventory)
        try:
            await interaction.message.delete()
        except:
            pass
        await send_card_message(interaction.channel, index, view)

    async def sell_callback(interaction):
        nonlocal index, inventory
        if not inventory:
            await interaction.response.send_message("❌ Ya no tienes cartas para vender.", ephemeral=True)
            return

        sold_card = remove_from_inventory_by_index(user_id, index)
        if sold_card:
            value = sold_card.get("valor", 0)
            add_balance(user_id, value)

            # Embed de confirmación de venta
            confirm_embed = discord.Embed(
                title=f"💰 Vendiste {sold_card['nombre']}!",
                description=f"Ganaste {format_gems(value)}.\n"
                            f"Nuevo balance: {format_gems(get_balance(user_id))}",
                color=discord.Color.gold()
            )
            file = discord.File(sold_card["imagen"], filename="vendida.png")
            confirm_embed.set_thumbnail(url="attachment://vendida.png")

            await interaction.channel.send(embed=confirm_embed, file=file)

            # Eliminar el mensaje con los botones (cierra el carrusel)
            try:
                await interaction.message.delete()
            except:
                pass

            # Deshabilitar la vista para que no puedan presionar más
            view.stop()
        else:
            await interaction.response.send_message("❌ No se pudo vender la carta.", ephemeral=True)

    prev_btn = Button(label="⬅️", style=discord.ButtonStyle.blurple)
    next_btn = Button(label="➡️", style=discord.ButtonStyle.blurple)
    sell_btn = Button(label="💰 Vender", style=discord.ButtonStyle.red)

    prev_btn.callback = prev_callback
    next_btn.callback = next_callback
    sell_btn.callback = sell_callback

    view.add_item(prev_btn)
    view.add_item(next_btn)
    view.add_item(sell_btn)

    await send_card_message(ctx, index, view)

# ----------------------------
# SISTEMA DE DUELOS PVP MEJORADO - VERSIÓN COMPLETA
# ----------------------------

# Diccionario para duelos pendientes
pending_duels = {}  # {duel_id: duel_data}

# Atributos disponibles para duelos
duel_attributes = {
    "Evasion": "👻 Evasion",
    "Fuerza": "💥 Fuerza", 
    "Reacción": "🌀 Reacción",
    "Defensa": "🛡️ Defensa",
    "Velocidad": "💨 Velocidad",
    "IQ": "🧠 IQ",
    "Carisma": "✨ Carisma",
    "Precisión": "🎯 Precisión",
    "Energia": "⚡ Energia",
    "Suerte": "🍀 Suerte",
}

# Orden de rarezas para filtros
rarity_order = {"G": 0, "SP": 1, "UR": 2, "SSR": 3, "R": 4, "N": 5}

class DuelAcceptView(View):
    def __init__(self, duel_id, challenger, challenged, duel_type="amistoso", max_rarity=None, timeout=120):
        super().__init__(timeout=timeout)
        self.duel_id = duel_id
        self.challenger = challenger
        self.challenged = challenged
        self.duel_type = duel_type
        self.max_rarity = max_rarity

    @discord.ui.button(label="⚔️ Aceptar Duelo", style=discord.ButtonStyle.green)
    async def accept_callback(self, interaction, button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("❌ Solo el usuario retado puede aceptar este duelo.", ephemeral=True)
            return

        # Actualizar estado del duelo
        pending_duels[self.duel_id]['accepted'] = True
        
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="⚔️ ¡Duelo Aceptado!",
            description=f"{self.challenged.mention} ha aceptado el duelo contra {self.challenger.mention}",
            color=discord.Color.green()
        )
        
        if self.duel_type == "honor":
            embed.add_field(name="🎯 Tipo", value=f"Duelo de Honor (5 rondas)", inline=True)
            embed.add_field(name="📊 Rareza Máxima", value=self.max_rarity, inline=True)
        else:
            embed.add_field(name="🎯 Tipo", value="Duelo Amistoso (3 rondas)", inline=True)
            
        embed.add_field(name="⏰ Próximo paso", value="Ambos jugadores deben seleccionar sus cartas.", inline=False)
        embed.set_footer(text="Tienes 5 minutos para seleccionar cartas")
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Iniciar selección de cartas según el tipo de duelo
        if self.duel_type == "honor":
            await iniciar_seleccion_cartas_honor(self.duel_id)
        else:
            await iniciar_seleccion_cartas_amistoso(self.duel_id)

    @discord.ui.button(label="❌ Rechazar Duelo", style=discord.ButtonStyle.red)
    async def reject_callback(self, interaction, button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("❌ Solo el usuario retado puede rechazar este duelo.", ephemeral=True)
            return

        # Eliminar duelo
        if self.duel_id in pending_duels:
            del pending_duels[self.duel_id]

        # Deshabilitar botones
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="❌ Duelo Rechazado",
            description=f"{self.challenged.mention} ha rechazado el duelo contra {self.challenger.mention}",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

async def iniciar_seleccion_cartas_amistoso(duel_id):
    """Inicia la selección de cartas para duelo amistoso"""
    duel_data = pending_duels[duel_id]
    
    # Para el retador
    view_challenger = DuelCardSelectionAmistosoView(duel_id, duel_data['challenger'], True)
    await view_challenger.send_card_list()
    
    # Para el retado
    view_challenged = DuelCardSelectionAmistosoView(duel_id, duel_data['challenged'], False)
    await view_challenged.send_card_list()

async def iniciar_seleccion_cartas_honor(duel_id):
    """Inicia la selección de cartas para duelo de honor"""
    duel_data = pending_duels[duel_id]
    
    # Para el retador
    view_challenger = DuelCardSelectionHonorView(duel_id, duel_data['challenger'], True)
    await view_challenger.send_card_list()
    
    # Para el retado
    view_challenged = DuelCardSelectionHonorView(duel_id, duel_data['challenged'], False)
    await view_challenged.send_card_list()

class DuelCardSelectionAmistosoView:
    def __init__(self, duel_id, user, is_challenger, timeout=300):
        self.duel_id = duel_id
        self.user = user
        self.is_challenger = is_challenger
        self.selected_cards = []
        self.current_round = 1
        self.message = None
        self.timeout = timeout

    async def send_card_list(self):
        """Envía la lista de cartas ordenadas por rareza - EVITANDO DUPLICADOS"""
        inventory = get_inventory(self.user.id)
        
        if not inventory:
            await self.user.send("❌ No tienes cartas para usar en el duelo.")
            return

        # Crear copia del inventario sin las cartas ya seleccionadas
        available_inventory = [card for card in inventory if card not in self.selected_cards]
        
        if not available_inventory:
            await self.user.send("❌ No tienes más cartas disponibles para seleccionar.")
            if self.duel_id in pending_duels:
                del pending_duels[self.duel_id]
            return
        
        # Ordenar por rareza (de más rara a menos rara)
        self.sorted_cards = sorted(available_inventory, key=lambda x: rarity_order.get(x.get("rareza", "N"), 6))
        
        # Crear embed con la lista de cartas
        embed = discord.Embed(
            title=f"⚔️ Carta Ronda {self.current_round} - Duelo Amistoso",
            description=f"Selecciona la carta para la ronda {self.current_round}/3:\n\n",
            color=discord.Color.blue()
        )
        
        # Agregar cartas numeradas
        for i, card in enumerate(self.sorted_cards, 1):
            rarity = card.get("rareza", "N")
            rarity_emoji = get_rarity_emoji(rarity)
            embed.description += f"**{i}. {rarity_emoji} {card['nombre']}** ({rarity})\n"
        
        embed.description += f"\nResponde con `!1` a `!{len(self.sorted_cards)}` para seleccionar."
        embed.set_footer(text="Tienes 5 minutos para completar todas las selecciones")
        
        self.message = await self.user.send(embed=embed)
            
        # Esperar selección del usuario
        def check(m):
            return m.author == self.user and m.channel == self.message.channel and m.content.startswith('!')
        
        try:
            msg = await bot.wait_for('message', timeout=300.0, check=check)
            selection = msg.content[1:]  # Remover el "!"
            
            if selection.isdigit():
                card_index = int(selection) - 1
                if 0 <= card_index < len(self.sorted_cards):
                    selected_card = self.sorted_cards[card_index]
                    
                    # VERIFICAR QUE LA CARTA NO ESTÉ YA SELECCIONADA
                    if selected_card in self.selected_cards:
                        await self.user.send("❌ Esta carta ya ha sido seleccionada. Por favor elige otra.")
                        await self.send_card_list()
                        return
                    
                    # Selección de carta para ronda
                    self.selected_cards.append(selected_card)
                    
                    await self.user.send(f"✅ **Carta para la ronda {self.current_round} seleccionada: {selected_card['nombre']}**")
                    
                    self.current_round += 1
                    
                    if self.current_round <= 3:
                        await self.send_card_list()
                    else:
                        await self.finalize_selection()
                else:
                    await self.user.send("❌ Selección inválida. Intenta de nuevo.")
                    await self.send_card_list()
            else:
                await self.user.send("❌ Por favor responde con un número. Intenta de nuevo.")
                await self.send_card_list()
                
        except asyncio.TimeoutError:
            await self.user.send("⏰ Tiempo agotado. El duelo ha sido cancelado.")
            if self.duel_id in pending_duels:
                del pending_duels[self.duel_id]

    async def finalize_selection(self):
        """Finaliza la selección cuando se han elegido todas las cartas"""
        duel_data = pending_duels[self.duel_id]
        
        if self.is_challenger:
            duel_data['challenger_cards'] = self.selected_cards
            duel_data['challenger_selected'] = True
        else:
            duel_data['challenged_cards'] = self.selected_cards
            duel_data['challenged_selected'] = True
        
        pending_duels[self.duel_id] = duel_data
        
        # Verificar si ambos han seleccionado
        if duel_data.get('challenger_selected') and duel_data.get('challenged_selected'):
            await self.iniciar_duelo_amistoso()
        else:
            await self.user.send("✅ Todas tus cartas han sido seleccionadas. Esperando al oponente...")

    async def iniciar_duelo_amistoso(self):
        """Inicia el duelo amistoso una vez ambos han seleccionado sus cartas"""
        duel_data = pending_duels[self.duel_id]
        challenger_cards = duel_data['challenger_cards']
        challenged_cards = duel_data['challenged_cards']
        channel = duel_data.get('channel')
        
        if not channel or len(challenger_cards) != 3 or len(challenged_cards) != 3:
            return

        # Realizar 3 rondas
        challenger_wins = 0
        challenged_wins = 0
        results = []

        for round_num in range(3):
            challenger_card = challenger_cards[round_num]
            challenged_card = challenged_cards[round_num]
            
            # Seleccionar atributo aleatorio
            selected_attribute = random.choice(list(duel_attributes.keys()))
            attribute_display = duel_attributes[selected_attribute]
            
            # Obtener valores
            challenger_value = challenger_card.get("stats", {}).get(selected_attribute, 1)
            challenged_value = challenged_card.get("stats", {}).get(selected_attribute, 1)
            
            # Determinar ganador de la ronda
            if challenger_value > challenged_value:
                round_winner = "challenger"
                challenger_wins += 1
            elif challenged_value > challenger_value:
                round_winner = "challenged"
                challenged_wins += 1
            else:
                round_winner = "empate"
            
            results.append({
                'round': round_num + 1,
                'attribute': attribute_display,
                'challenger_card': challenger_card,
                'challenged_card': challenged_card,
                'challenger_value': challenger_value,
                'challenged_value': challenged_value,
                'winner': round_winner
            })

        # Determinar ganador final
        if challenger_wins > challenged_wins:
            final_winner = duel_data['challenger']
            final_loser = duel_data['challenged']
        elif challenged_wins > challenger_wins:
            final_winner = duel_data['challenged']
            final_loser = duel_data['challenger']
        else:
            final_winner = None

        # Crear embed de resultados
        embed = discord.Embed(
            title="⚔️ ¡Resultado del Duelo Amistoso!",
            color=discord.Color.blue()
        )
        
        # Mostrar resultados por ronda
        for result in results:
            winner_text = ""
            if result['winner'] == "challenger":
                winner_text = f"🏆 {duel_data['challenger'].display_name}"
            elif result['winner'] == "challenged":
                winner_text = f"🏆 {duel_data['challenged'].display_name}"
            else:
                winner_text = "🤝 Empate"
            
            embed.add_field(
                name=f"🎯 Ronda {result['round']} - {result['attribute']}",
                value=(
                    f"{duel_data['challenger'].display_name}: **{result['challenger_card']['nombre']}** ({result['challenger_value']})\n"
                    f"{duel_data['challenged'].display_name}: **{result['challenged_card']['nombre']}** ({result['challenged_value']})\n"
                    f"{winner_text}"
                ),
                inline=False
            )
        
        # Resultado final
        if final_winner:
            embed.add_field(
                name="🏆 ¡GANADOR FINAL!",
                value=f"**{final_winner.display_name}** gana el duelo {challenger_wins}-{challenged_wins}!",
                inline=False
            )
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="🤝 ¡EMPATE FINAL!",
                value=f"El duelo terminó {challenger_wins}-{challenged_wins}.",
                inline=False
            )
            embed.color = discord.Color.blue()
        
        await channel.send(embed=embed)
        
        # Eliminar duelo
        if self.duel_id in pending_duels:
            del pending_duels[self.duel_id]

class DuelCardSelectionHonorView:
    def __init__(self, duel_id, user, is_challenger, timeout=300):
        self.duel_id = duel_id
        self.user = user
        self.is_challenger = is_challenger
        self.bet_card = None
        self.selected_cards = []
        self.current_round = 1
        self.message = None
        self.max_rarity = pending_duels[duel_id].get('max_rarity', 'UR')
        self.timeout = timeout

    async def send_card_list(self):
        """Envía la lista de cartas ordenadas por rareza - EVITANDO DUPLICADOS"""
        inventory = get_inventory(self.user.id)
        
        if not inventory:
            await self.user.send("❌ No tienes cartas para usar en el duelo.")
            return

        # Determinar qué selección estamos haciendo
        if not self.bet_card:
            # SELECCIÓN DE CARTA APOSTADA: SIN FILTRO DE RAREZA
            selection_type = "Carta a Apostar"
            instructions = "Selecciona la carta que apostarás en este duelo (puede ser de cualquier rareza):"
            
            # Para la carta apostada, mostrar todo el inventario
            self.sorted_cards = sorted(inventory, key=lambda x: rarity_order.get(x.get("rareza", "N"), 6))
            
        else:
            # SELECCIÓN DE CARTAS PARA RONDAS: CON FILTRO DE RAREZA Y SIN DUPLICADOS
            selection_type = f"Carta Ronda {self.current_round}"
            instructions = f"Selecciona la carta para la ronda {self.current_round}/5 (rareza máxima: {self.max_rarity}):"
            
            # Filtrar cartas por rareza máxima para las rondas
            max_rarity_value = rarity_order.get(self.max_rarity, 6)
            
            # Crear copia del inventario sin:
            # 1. La carta apostada
            # 2. Las cartas ya seleccionadas para rondas anteriores
            inventory_without_bet_and_selected = [
                card for card in inventory 
                if card.get('id') != self.bet_card.get('id') 
                and card not in self.selected_cards
            ]
            
            # Filtrar por rareza
            filtered_inventory = [
                card for card in inventory_without_bet_and_selected 
                if rarity_order.get(card.get("rareza", "N"), 6) >= max_rarity_value
            ]
            
            if not filtered_inventory:
                await self.user.send(f"❌ No tienes cartas con rareza {self.max_rarity} o superior disponibles para las rondas.")
                if self.duel_id in pending_duels:
                    del pending_duels[self.duel_id]
                return
            
            self.sorted_cards = sorted(filtered_inventory, key=lambda x: rarity_order.get(x.get("rareza", "N"), 6))
        
        # Crear embed con la lista de cartas
        embed = discord.Embed(
            title=f"⚔️ {selection_type} - Duelo de Honor",
            description=f"{instructions}\n\n",
            color=discord.Color.gold()
        )
        
        # Agregar cartas numeradas
        for i, card in enumerate(self.sorted_cards, 1):
            rarity = card.get("rareza", "N")
            rarity_emoji = get_rarity_emoji(rarity)
            embed.description += f"**{i}. {rarity_emoji} {card['nombre']}** ({rarity})\n"
        
        embed.description += f"\nResponde con `!1` a `!{len(self.sorted_cards)}` para seleccionar."
        embed.set_footer(text="Tienes 5 minutos para completar todas las selecciones")
        
        self.message = await self.user.send(embed=embed)
            
        # Esperar selección del usuario
        def check(m):
            return m.author == self.user and m.channel == self.message.channel and m.content.startswith('!')
        
        try:
            msg = await bot.wait_for('message', timeout=300.0, check=check)
            selection = msg.content[1:]  # Remover el "!"
            
            if selection.isdigit():
                card_index = int(selection) - 1
                if 0 <= card_index < len(self.sorted_cards):
                    selected_card = self.sorted_cards[card_index]
                    
                    if not self.bet_card:
                        # Selección de carta apostada
                        # VERIFICAR QUE LA CARTA NO ESTÉ YA SELECCIONADA (aunque no debería pasar aquí)
                        if selected_card in self.selected_cards:
                            await self.user.send("❌ Esta carta ya ha sido seleccionada. Por favor elige otra.")
                            await self.send_card_list()
                            return
                            
                        self.bet_card = selected_card
                        await self.user.send(f"✅ **Carta apostada seleccionada: {selected_card['nombre']}**")
                        
                        # Continuar con selección de cartas para rondas
                        await self.send_card_list()
                    else:
                        # Selección de carta para ronda
                        # VERIFICAR QUE LA CARTA NO ESTÉ YA SELECCIONADA
                        if selected_card in self.selected_cards:
                            await self.user.send("❌ Esta carta ya ha sido seleccionada. Por favor elige otra.")
                            await self.send_card_list()
                            return
                            
                        self.selected_cards.append(selected_card)
                        
                        await self.user.send(f"✅ **Carta para la ronda {self.current_round} seleccionada: {selected_card['nombre']}**")
                        
                        self.current_round += 1
                        
                        if self.current_round <= 5:
                            await self.send_card_list()
                        else:
                            await self.finalize_selection()
                else:
                    await self.user.send("❌ Selección inválida. Intenta de nuevo.")
                    await self.send_card_list()
            else:
                await self.user.send("❌ Por favor responde con un número. Intenta de nuevo.")
                await self.send_card_list()
                
        except asyncio.TimeoutError:
            await self.user.send("⏰ Tiempo agotado. El duelo ha sido cancelado.")
            if self.duel_id in pending_duels:
                del pending_duels[self.duel_id]

    async def finalize_selection(self):
        """Finaliza la selección cuando se han elegido todas las cartas"""
        duel_data = pending_duels[self.duel_id]
        
        if self.is_challenger:
            duel_data['challenger_bet_card'] = self.bet_card
            duel_data['challenger_cards'] = self.selected_cards
            duel_data['challenger_selected'] = True
        else:
            duel_data['challenged_bet_card'] = self.bet_card
            duel_data['challenged_cards'] = self.selected_cards
            duel_data['challenged_selected'] = True
        
        pending_duels[self.duel_id] = duel_data
        
        # Verificar si ambos han seleccionado
        if duel_data.get('challenger_selected') and duel_data.get('challenged_selected'):
            await self.iniciar_duelo_honor()
        else:
            await self.user.send("✅ Todas tus cartas han sido seleccionadas. Esperando al oponente...")

    async def iniciar_duelo_honor(self):
        """Inicia el duelo de honor una vez ambos han seleccionado sus cartas"""
        duel_data = pending_duels[self.duel_id]
        challenger_bet = duel_data['challenger_bet_card']
        challenged_bet = duel_data['challenged_bet_card']
        challenger_cards = duel_data['challenger_cards']
        challenged_cards = duel_data['challenged_cards']
        channel = duel_data.get('channel')
        
        if not channel or len(challenger_cards) != 5 or len(challenged_cards) != 5:
            return

        # Realizar 5 rondas
        challenger_wins = 0
        challenged_wins = 0
        results = []

        for round_num in range(5):
            challenger_card = challenger_cards[round_num]
            challenged_card = challenged_cards[round_num]
            
            # Seleccionar atributo aleatorio
            selected_attribute = random.choice(list(duel_attributes.keys()))
            attribute_display = duel_attributes[selected_attribute]
            
            # Obtener valores
            challenger_value = challenger_card.get("stats", {}).get(selected_attribute, 1)
            challenged_value = challenged_card.get("stats", {}).get(selected_attribute, 1)
            
            # Determinar ganador de la ronda
            if challenger_value > challenged_value:
                round_winner = "challenger"
                challenger_wins += 1
            elif challenged_value > challenger_value:
                round_winner = "challenged"
                challenged_wins += 1
            else:
                round_winner = "empate"
            
            results.append({
                'round': round_num + 1,
                'attribute': attribute_display,
                'challenger_card': challenger_card,
                'challenged_card': challenged_card,
                'challenger_value': challenger_value,
                'challenged_value': challenged_value,
                'winner': round_winner
            })

        # Determinar ganador final y transferir cartas apostadas
        if challenger_wins > challenged_wins:
            final_winner = duel_data['challenger']
            final_loser = duel_data['challenged']
            # El ganador recibe la carta apostada del perdedor
            add_to_inventory(final_winner.id, challenged_bet.copy())
            quitarcarta_from_inventory(final_loser.id, challenged_bet['id'])
        elif challenged_wins > challenger_wins:
            final_winner = duel_data['challenged']
            final_loser = duel_data['challenger']
            # El ganador recibe la carta apostada del perdedor
            add_to_inventory(final_winner.id, challenger_bet.copy())
            quitarcarta_from_inventory(final_loser.id, challenger_bet['id'])
        else:
            final_winner = None
            # En caso de empate, nadie gana las cartas apostadas

        # Crear embed de resultados
        embed = discord.Embed(
            title="⚔️ ¡Resultado del Duelo de Honor!",
            color=discord.Color.gold()
        )
        
        # Mostrar cartas apostadas
        embed.add_field(
            name="🎲 Cartas Apostadas",
            value=(
                f"{duel_data['challenger'].display_name}: **{challenger_bet['nombre']}**\n"
                f"{duel_data['challenged'].display_name}: **{challenged_bet['nombre']}**"
            ),
            inline=False
        )
        
        # Mostrar resultados por ronda
        for result in results:
            winner_text = ""
            if result['winner'] == "challenger":
                winner_text = f"🏆 {duel_data['challenger'].display_name}"
            elif result['winner'] == "challenged":
                winner_text = f"🏆 {duel_data['challenged'].display_name}"
            else:
                winner_text = "🤝 Empate"
            
            embed.add_field(
                name=f"🎯 Ronda {result['round']} - {result['attribute']}",
                value=(
                    f"{duel_data['challenger'].display_name}: **{result['challenger_card']['nombre']}** ({result['challenger_value']})\n"
                    f"{duel_data['challenged'].display_name}: **{result['challenged_card']['nombre']}** ({result['challenged_value']})\n"
                    f"{winner_text}"
                ),
                inline=False
            )
        
        # Resultado final
        if final_winner:
            winner_name = final_winner.display_name
            loser_name = final_loser.display_name
            winner_card = challenger_bet if final_winner == duel_data['challenger'] else challenged_bet
            loser_card = challenged_bet if final_winner == duel_data['challenger'] else challenger_bet
            
            embed.add_field(
                name="🏆 ¡GANADOR FINAL!",
                value=(
                    f"**{winner_name}** gana el duelo {challenger_wins}-{challenged_wins}!\n"
                    f"**{winner_name}** recibe la carta **{loser_card['nombre']}** de **{loser_name}**"
                ),
                inline=False
            )
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="🤝 ¡EMPATE FINAL!",
                value=f"El duelo terminó {challenger_wins}-{challenged_wins}. Nadie gana las cartas apostadas.",
                inline=False
            )
            embed.color = discord.Color.blue()
        
        await channel.send(embed=embed)
        
        # Eliminar duelo
        if self.duel_id in pending_duels:
            del pending_duels[self.duel_id]

def quitarcarta_from_inventory(user_id, card_id):
    """Elimina una carta específica del inventario de un usuario"""
    uid = str(user_id)
    if uid in user_inventories:
        user_inventories[uid] = [card for card in user_inventories[uid] if card.get('id') != card_id]
        save_data()

# ----------------------------
# COMANDOS DE DUELO COMPLETOS
# ----------------------------

@bot.command()
async def dueloamistoso(ctx, member: discord.Member):
    """Retar a otro usuario a un duelo amistoso de 3 rondas"""
    # Verificaciones básicas
    if ctx.author.id == member.id:
        await ctx.send("❌ No puedes retarte a ti mismo.")
        return
    
    if member.bot:
        await ctx.send("❌ No puedes retar a un bot.")
        return

    # Verificar que ambos usuarios tienen al menos 3 cartas
    author_inv = get_inventory(ctx.author.id)
    member_inv = get_inventory(member.id)
    
    if len(author_inv) < 3:
        await ctx.send("❌ Necesitas al menos 3 cartas para un duelo amistoso.")
        return
    
    if len(member_inv) < 3:
        await ctx.send(f"❌ {member.mention} necesita al menos 3 cartas para un duelo amistoso.")
        return

    # VERIFICACIÓN CORREGIDA - Solo prevenir múltiples duelos como retador
    for duel_id, duel_data in pending_duels.items():
        # El retador no puede iniciar otro duelo
        if duel_data['challenger'].id == ctx.author.id and not duel_data.get('accepted', False):
            await ctx.send("❌ Ya tienes un duelo pendiente. Espera a que termine.")
            return
        
        # El retado puede ser retado múltiples veces, pero no puede ser retador en otro duelo
        if duel_data['challenger'].id == member.id and not duel_data.get('accepted', False):
            await ctx.send(f"❌ {member.mention} ya tiene un duelo pendiente como retador.")
            return
        
        # No prevenir que alguien sea retado múltiples veces - eso es válido

    # Generar ID único para el duelo
    duel_id = f"amistoso_{ctx.author.id}_{member.id}_{int(time.time())}"
    
    # Crear datos del duelo
    pending_duels[duel_id] = {
        'challenger': ctx.author,
        'challenged': member,
        'challenger_cards': [],
        'challenged_cards': [],
        'challenger_selected': False,
        'challenged_selected': False,
        'accepted': False,
        'duel_type': 'amistoso',
        'created_at': time.time(),
        'channel': ctx.channel
    }

    # Crear vista de aceptación/rechazo
    view = DuelAcceptView(duel_id, ctx.author, member, "amistoso")
    
    embed = discord.Embed(
        title="⚔️ ¡Desafío de Duelo Amistoso!",
        description=f"{ctx.author.mention} reta a {member.mention} a un duelo amistoso de 3 rondas",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🎯 Cómo funciona", 
        value=(
            "1. Ambos seleccionan 3 cartas para las rondas\n"
            "2. Cada ronda se elige un atributo al azar\n"
            "3. ¡Gana quien gane más rondas!\n"
            "4. **No hay apuesta de cartas** - Es solo por diversión"
        ),
        inline=False
    )
    embed.add_field(
        name="⏰ Tiempo límite", 
        value="2 minutos para aceptar\n5 minutos para seleccionar cartas",
        inline=True
    )
    embed.set_footer(text="¡Que gane el mejor!")

    await ctx.send(embed=embed, view=view)

@bot.command()
async def duelohonor(ctx, member: discord.Member, max_rarity: str = "UR"):
    """Retar a otro usuario a un duelo de honor de 5 rondas con apuesta de cartas"""
    # Validar rareza máxima
    valid_rarities = ["G", "SP", "UR", "SSR", "R", "N"]
    max_rarity = max_rarity.upper()
    
    if max_rarity not in valid_rarities:
        await ctx.send(f"❌ Rareza inválida. Usa: {', '.join(valid_rarities)}")
        return
    
    # Verificaciones básicas
    if ctx.author.id == member.id:
        await ctx.send("❌ No puedes retarte a ti mismo.")
        return
    
    if member.bot:
        await ctx.send("❌ No puedes retar a un bot.")
        return

    # Verificar que ambos usuarios tienen al menos 6 cartas (5 + 1 de apuesta)
    author_inv = get_inventory(ctx.author.id)
    member_inv = get_inventory(member.id)
    
    if len(author_inv) < 6:
        await ctx.send("❌ Necesitas al menos 6 cartas para un duelo de honor (5 para rondas + 1 de apuesta).")
        return
    
    if len(member_inv) < 6:
        await ctx.send(f"❌ {member.mention} necesita al menos 6 cartas para un duelo de honor (5 para rondas + 1 de apuesta).")
        return

    # Verificar que ambos tienen cartas de la rareza especificada o superior
    max_rarity_value = rarity_order.get(max_rarity, 6)
    
    author_has_rarity = any(rarity_order.get(card.get("rareza", "N"), 6) >= max_rarity_value for card in author_inv)
    member_has_rarity = any(rarity_order.get(card.get("rareza", "N"), 6) >= max_rarity_value for card in member_inv)
    
    if not author_has_rarity:
        await ctx.send(f"❌ No tienes cartas con rareza {max_rarity} o superior para el duelo.")
        return
    
    if not member_has_rarity:
        await ctx.send(f"❌ {member.mention} no tiene cartas con rareza {max_rarity} o superior para el duelo.")
        return

    # VERIFICACIÓN CORREGIDA - Solo prevenir múltiples duelos como retador
    for duel_id, duel_data in pending_duels.items():
        # El retador no puede iniciar otro duelo
        if duel_data['challenger'].id == ctx.author.id and not duel_data.get('accepted', False):
            await ctx.send("❌ Ya tienes un duelo pendiente. Espera a que termine.")
            return
        
        # El retado puede ser retado múltiples veces, pero no puede ser retador en otro duelo
        if duel_data['challenger'].id == member.id and not duel_data.get('accepted', False):
            await ctx.send(f"❌ {member.mention} ya tiene un duelo pendiente como retador.")
            return
        
        # No prevenir que alguien sea retado múltiples veces - eso es válido

    # Generar ID único para el duelo
    duel_id = f"honor_{ctx.author.id}_{member.id}_{int(time.time())}"
    
    # Crear datos del duelo
    pending_duels[duel_id] = {
        'challenger': ctx.author,
        'challenged': member,
        'challenger_bet_card': None,
        'challenged_bet_card': None,
        'challenger_cards': [],
        'challenged_cards': [],
        'challenger_selected': False,
        'challenged_selected': False,
        'accepted': False,
        'duel_type': 'honor',
        'max_rarity': max_rarity,
        'created_at': time.time(),
        'channel': ctx.channel
    }

    # Crear vista de aceptación/rechazo
    view = DuelAcceptView(duel_id, ctx.author, member, "honor", max_rarity)
    
    embed = discord.Embed(
        title="⚔️ ¡Desafío de Duelo de Honor!",
        description=f"{ctx.author.mention} reta a {member.mention} a un duelo de honor de 5 rondas",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="🎯 Cómo funciona", 
        value=(
            "1. Ambos seleccionan 1 carta para apostar y 5 cartas para las rondas\n"
            "2. Cada ronda se elige un atributo al azar\n"
            "3. ¡Gana quien gane más rondas!\n"
            "4. **El perdedor entrega su carta apostada al ganador**"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Rareza Máxima", 
        value=f"Cartas permitidas: {max_rarity} o superior",
        inline=True
    )
    embed.add_field(
        name="⏰ Tiempo límite", 
        value="2 minutos para aceptar\n5 minutos para seleccionar cartas",
        inline=True
    )
    embed.set_footer(text="¡Apuesta con sabiduría!")

    await ctx.send(embed=embed, view=view)

# ----------------------------
# COMANDOS DE GESTIÓN DE DUELOS
# ----------------------------

@bot.command()
async def aceptar_duelo(ctx):
    """Aceptar un duelo pendiente"""
    user = ctx.author
    
    # Buscar duelos pendientes donde el usuario sea el retado
    pending_duel = None
    duel_id_to_remove = None
    
    for duel_id, duel_data in pending_duels.items():
        if duel_data['challenged'].id == user.id and not duel_data.get('accepted', False):
            pending_duel = duel_data
            duel_id_to_remove = duel_id
            break
    
    if not pending_duel:
        await ctx.send("❌ No tienes duelos pendientes para aceptar.")
        return
    
    # Actualizar estado del duelo
    pending_duels[duel_id_to_remove]['accepted'] = True
    
    embed = discord.Embed(
        title="⚔️ ¡Duelo Aceptado!",
        description=f"{user.mention} ha aceptado el duelo contra {pending_duel['challenger'].mention}",
        color=discord.Color.green()
    )
    
    if pending_duel['duel_type'] == "honor":
        embed.add_field(name="🎯 Tipo", value=f"Duelo de Honor (5 rondas)", inline=True)
        embed.add_field(name="📊 Rareza Máxima", value=pending_duel['max_rarity'], inline=True)
    else:
        embed.add_field(name="🎯 Tipo", value="Duelo Amistoso (3 rondas)", inline=True)
        
    embed.add_field(name="⏰ Próximo paso", value="Ambos jugadores deben seleccionar sus cartas.", inline=False)
    embed.set_footer(text="Tienes 5 minutos para seleccionar cartas")
    
    await ctx.send(embed=embed)
    
    # Iniciar selección de cartas según el tipo de duelo
    if pending_duel['duel_type'] == "honor":
        await iniciar_seleccion_cartas_honor(duel_id_to_remove)
    else:
        await iniciar_seleccion_cartas_amistoso(duel_id_to_remove)

@bot.command()
async def rechazar_duelo(ctx):
    """Rechazar un duelo pendiente donde eres el retado"""
    user = ctx.author
    
    # Buscar TODOS los duelos pendientes donde el usuario esté involucrado
    pending_duels_to_reject = []
    
    for duel_id, duel_data in pending_duels.items():
        # Si es el retado y no ha sido aceptado
        if duel_data['challenged'].id == user.id and not duel_data.get('accepted', False):
            pending_duels_to_reject.append((duel_id, duel_data))
        # Si es el retador y no ha sido aceptado (para cancelar)
        elif duel_data['challenger'].id == user.id and not duel_data.get('accepted', False):
            pending_duels_to_reject.append((duel_id, duel_data))
    
    if not pending_duels_to_reject:
        await ctx.send("❌ No tienes duelos pendientes para rechazar.")
        return
    
    # Si hay múltiples, rechazar el más reciente
    duel_id_to_remove, pending_duel = pending_duels_to_reject[0]
    
    # Eliminar duelo
    del pending_duels[duel_id_to_remove]
    
    # Determinar el otro usuario
    other_user = pending_duel['challenger'] if user.id == pending_duel['challenged'].id else pending_duel['challenged']
    
    embed = discord.Embed(
        title="❌ Duelo Rechazado",
        description=f"{user.mention} ha rechazado el duelo contra {other_user.mention}",
        color=discord.Color.red()
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def cancelar_duelo(ctx):
    """Cancelar cualquier duelo pendiente donde estés involucrado"""
    user = ctx.author
    
    # Buscar TODOS los duelos pendientes donde el usuario esté involucrado
    pending_duels_to_cancel = []
    
    for duel_id, duel_data in pending_duels.items():
        # Si es el retador y no ha sido aceptado
        if duel_data['challenger'].id == user.id and not duel_data.get('accepted', False):
            pending_duels_to_cancel.append((duel_id, duel_data))
        # Si es el retado y no ha sido aceptado
        elif duel_data['challenged'].id == user.id and not duel_data.get('accepted', False):
            pending_duels_to_cancel.append((duel_id, duel_data))
    
    if not pending_duels_to_cancel:
        await ctx.send("❌ No tienes duelos pendientes para cancelar.")
        return
    
    # Cancelar todos los duelos encontrados
    for duel_id, duel_data in pending_duels_to_cancel:
        del pending_duels[duel_id]
    
    # Crear mensaje de confirmación
    if len(pending_duels_to_cancel) == 1:
        duel_data = pending_duels_to_cancel[0][1]
        other_user = duel_data['challenged'] if user.id == duel_data['challenger'].id else duel_data['challenger']
        
        embed = discord.Embed(
            title="❌ Duelo Cancelado",
            description=f"{user.mention} ha cancelado el duelo contra {other_user.mention}",
            color=discord.Color.orange()
        )
    else:
        embed = discord.Embed(
            title="❌ Múltiples Duelos Cancelados",
            description=f"{user.mention} ha cancelado {len(pending_duels_to_cancel)} duelos pendientes",
            color=discord.Color.orange()
        )
    
    await ctx.send(embed=embed)


# ----------------------------
# FUNCIONES AUXILIARES
# ----------------------------

def get_rarity_emoji(rarity):
    """Devuelve el emoji correspondiente a la rareza"""
    emoji_map = {
        "G": "💎", "SP": "✨", "UR": "🔥", 
        "SSR": "⭐", "R": "🌟", "N": "🟢"
    }
    return emoji_map.get(rarity.upper(), "🟢")

# ----------------------------
# COMANDO INVENTARIO PERSONAL (MD)
# ----------------------------
@bot.command()
async def inventario_personal(ctx):
    """Muestra tu inventario completo en mensajes directos en formato de lista"""
    user_id = ctx.author.id
    inventory = get_inventory(user_id)
    
    if not inventory:
        embed = discord.Embed(
            title="📦 Inventario Vacío",
            description="No tienes cartas en tu inventario.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="💡 Consejo", 
            value="Usa `!gacha` para obtener cartas gratis cada 4 horas\nUsa `!gacha_comprar` para comprar tiradas con gemas",
            inline=False
        )
        try:
            await ctx.author.send(embed=embed)
            await ctx.send("✅ Te he enviado tu inventario por mensaje directo.")
        except discord.Forbidden:
            await ctx.send("❌ No puedo enviarte mensajes directos. Por favor, habilita los MDs y usa el comando nuevamente.")
        return
    
    # Ordenar inventario por rareza (L, SP, UR, SSR, R, N, C)
    rarity_order = {"G": 0, "SP": 1, "UR": 2, "SSR": 3, "R": 4, "N": 5}
    sorted_inventory = sorted(inventory, key=lambda x: rarity_order.get(x.get("rareza", "N"), 6))
    
    # Dividir en chunks para evitar límites de Discord
    chunk_size = 10  # Número de cartas por mensaje
    chunks = [sorted_inventory[i:i + chunk_size] for i in range(0, len(sorted_inventory), chunk_size)]
    
    try:
        # Enviar mensaje inicial
        total_gems = get_balance(user_id)
        total_cards = len(inventory)
        
        # Contar cartas por rareza
        rarity_count = {}
        for card in inventory:
            rarity = card.get("rareza", "N")
            rarity_count[rarity] = rarity_count.get(rarity, 0) + 1
        
        # Crear embed de resumen
        summary_embed = discord.Embed(
            title=f"📦 Inventario de {ctx.author.display_name}",
            description=f"Tienes **{total_cards} cartas** y **{format_gems(total_gems)}**",
            color=discord.Color.gold()
        )
        
        # Agregar conteo por rareza
        rarity_text = ""
        for rarity in ["G", "SP", "UR", "SSR", "R", "N"]:
            if rarity in rarity_count:
                emoji = get_rarity_emoji(rarity)
                rarity_text += f"{emoji} **{rarity}**: {rarity_count[rarity]}\n"
        
        if rarity_text:
            summary_embed.add_field(name="📊 Distribución por Rareza", value=rarity_text, inline=False)
        
        summary_embed.set_footer(text=f"Página 1 de {len(chunks)} • Total: {total_cards} cartas")
        await ctx.author.send(embed=summary_embed)
        
        # Enviar cada chunk de cartas
        for page_num, chunk in enumerate(chunks, 1):
            embed = discord.Embed(
                title=f"📋 Lista de Cartas - Página {page_num}/{len(chunks)}",
                color=discord.Color.blue()
            )
            
            for i, card in enumerate(chunk, 1):
                rarity = card.get("rareza", "N")
                rarity_emoji = get_rarity_emoji(rarity)
                card_value = format_gems(card.get('valor', 0))
                
                # Obtener stats (solo mostrar las que no sean 1)
                stats = card.get("stats", {})
                stats_text = ""
                for stat_name, stat_value in stats.items():
                    if stat_value > 1:  # Solo mostrar stats que no sean el valor por defecto (1)
                        stat_display = {
                            "Evasion": "👻 Eva",
                            "Fuerza": "💥 Fuer", 
                            "Reacción": "🌀 Reacción",
                            "Defensa": "🛡️ Def",
                            "Velocidad": "💨 Vel",
                            "IQ": "🧠 IQ",
                            "Carisma": "✨ Car",
                            "Precisión": "🎯 Prec",
                            "Energia": "⚡ Ener",
                            "Suerte": "🍀 Suer",
                        }.get(stat_name, stat_name)
                        stats_text += f"{stat_display}: {stat_value} "
                
                if not stats_text:
                    stats_text = "📊 Stats base"
                
                # Crear field para cada carta
                field_value = f"**Rareza**: {rarity_emoji} {rarity}\n**Valor**: {card_value}\n**Stats**: {stats_text}"
                
                embed.add_field(
                    name=f"#{i + (page_num-1)*chunk_size}. {card['nombre']}",
                    value=field_value,
                    inline=False
                )
            
            # Agregar información del chunk actual
            embed.set_footer(text=f"Página {page_num} de {len(chunks)} • Cartas {((page_num-1)*chunk_size)+1}-{min(page_num*chunk_size, total_cards)} de {total_cards}")
            
            await ctx.author.send(embed=embed)
        
        # Enviar mensaje de confirmación en el canal
        await ctx.send(f"✅ {ctx.author.mention}, te he enviado tu inventario completo ({total_cards} cartas) por mensaje directo.")
        
    except discord.Forbidden:
        await ctx.send("❌ No puedo enviarte mensajes directos. Por favor, habilita los MDs en la configuración de privacidad del servidor.")
    except Exception as e:
        await ctx.send(f"❌ Error al enviar el inventario: {str(e)}")

        # ----------------------------
# COMANDO VENDER MAYOREO
# ----------------------------
@bot.command()
async def vender_mayoreo(ctx):
    """Vende múltiples cartas de tu inventario a la vez usando números"""
    user_id = ctx.author.id
    inventory = get_inventory(user_id)
    
    if not inventory:
        await ctx.send("📭 No tienes cartas en tu inventario para vender.")
        return
    
    # Crear lista numerada de cartas
    cartas_lista = []
    total_valor = 0
    
    for i, card in enumerate(inventory, 1):
        rarity = card.get("rareza", "N")
        rarity_emoji = get_rarity_emoji(rarity)
        valor = card.get('valor', 0)
        total_valor += valor
        
        cartas_lista.append(
            f"**{i}. {rarity_emoji} {card['nombre']}** ({rarity}) - {format_gems(valor)}"
        )
    
    # Dividir en chunks si hay muchas cartas
    chunk_size = 15
    chunks = [cartas_lista[i:i + chunk_size] for i in range(0, len(cartas_lista), chunk_size)]
    
    # Enviar lista de cartas
    for page_num, chunk in enumerate(chunks, 1):
        embed = discord.Embed(
            title=f"💰 Venta al Mayoreo - Página {page_num}/{len(chunks)}",
            description="**Selecciona las cartas que quieres vender:**\n\n" + "\n".join(chunk),
            color=discord.Color.gold()
        )
        
        if page_num == 1:
            embed.add_field(
                name="📝 **Cómo vender:**",
                value=(
                    "**Vender una carta:** `!1`\n"
                    "**Vender múltiples:** `!1,2,5`\n"
                    "**Vender rango:** `!1-5`\n"
                    "**Vender todo:** `!todo`\n\n"
                    "**Ejemplos:**\n"
                    "• `!3` - Vende la carta #3\n"
                    "• `!1,5,8` - Vende cartas 1, 5 y 8\n"
                    "• `!2-6` - Vende cartas 2, 3, 4, 5, 6\n"
                    "• `!todo` - Vende TODAS las cartas\n\n"
                    f"💎 **Valor total del inventario:** {format_gems(total_valor)}"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"Total cartas: {len(inventory)} • Responde en los próximos 2 minutos")
        await ctx.send(embed=embed)
    
    # Esperar respuesta del usuario
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.startswith('!')
    
    try:
        msg = await bot.wait_for('message', timeout=120.0, check=check)
        seleccion = msg.content[1:].strip().lower()  # Remover el "!" y limpiar
        
        if not seleccion:
            await ctx.send("❌ Selección vacía. Usa `!vender_mayoreo` para intentar de nuevo.")
            return
        
        cartas_a_vender = []
        gems_ganadas = 0
        
        if seleccion == "todo":
            # Vender todo el inventario
            cartas_a_vender = inventory.copy()
            for card in inventory:
                gems_ganadas += card.get('valor', 0)
            
            # Limpiar inventario
            user_inventories[str(user_id)] = []
            save_data()
            
        else:
            # Procesar selección individual
            indices_seleccionados = set()
            
            # Procesar diferentes formatos: 1,2,3 o 1-5 o combinaciones
            partes = seleccion.split(',')
            
            for parte in partes:
                parte = parte.strip()
                if '-' in parte:
                    # Es un rango: 1-5
                    try:
                        inicio, fin = map(int, parte.split('-'))
                        for i in range(inicio, fin + 1):
                            if 1 <= i <= len(inventory):
                                indices_seleccionados.add(i - 1)  # Convertir a índice 0-based
                    except ValueError:
                        await ctx.send(f"❌ Formato de rango inválido: `{parte}`. Usa `!vender_mayoreo` para intentar de nuevo.")
                        return
                else:
                    # Es un número individual
                    try:
                        num = int(parte)
                        if 1 <= num <= len(inventory):
                            indices_seleccionados.add(num - 1)  # Convertir a índice 0-based
                        else:
                            await ctx.send(f"❌ Número fuera de rango: `{num}`. El rango válido es 1-{len(inventory)}.")
                            return
                    except ValueError:
                        await ctx.send(f"❌ Formato inválido: `{parte}`. Usa `!vender_mayoreo` para intentar de nuevo.")
                        return
            
            if not indices_seleccionados:
                await ctx.send("❌ No seleccionaste ninguna carta válida. Usa `!vender_mayoreo` para intentar de nuevo.")
                return
            
            # Ordenar índices de mayor a menor para eliminar correctamente
            indices_ordenados = sorted(indices_seleccionados, reverse=True)
            
            # Recolectar cartas a vender y calcular ganancias
            cartas_vendidas_info = []
            for idx in indices_ordenados:
                if 0 <= idx < len(inventory):
                    carta = inventory[idx]
                    valor = carta.get('valor', 0)
                    gems_ganadas += valor
                    cartas_a_vender.append(carta)
                    cartas_vendidas_info.append(f"• {carta['nombre']} - {format_gems(valor)}")
            
            # Eliminar cartas del inventario (de atrás hacia adelante para evitar problemas de índices)
            for idx in indices_ordenados:
                if 0 <= idx < len(inventory):
                    remove_from_inventory_by_index(user_id, idx)
        
        # Añadir las gemas ganadas
        if gems_ganadas > 0:
            add_balance(user_id, gems_ganadas)
        
        # Crear embed de resultados
        if seleccion == "todo":
            embed = discord.Embed(
                title="💰 ¡Venta Completa Realizada!",
                description=f"Has vendido **TODO tu inventario** ({len(cartas_a_vender)} cartas)",
                color=discord.Color.green()
            )
            embed.add_field(
                name="💎 Ganancias Totales",
                value=f"**{format_gems(gems_ganadas)}**",
                inline=True
            )
            embed.add_field(
                name="📦 Nuevo Inventario",
                value="0 cartas",
                inline=True
            )
            embed.add_field(
                name="💰 Nuevo Balance",
                value=format_gems(get_balance(user_id)),
                inline=True
            )
            
        else:
            embed = discord.Embed(
                title="💰 ¡Venta al Mayoreo Exitosa!",
                description=f"Has vendido **{len(cartas_a_vender)} cartas**",
                color=discord.Color.green()
            )
            
            # Mostrar cartas vendidas (máximo 10 para no exceder límites)
            if len(cartas_a_vender) <= 10:
                cartas_texto = "\n".join([f"• {card['nombre']} - {format_gems(card.get('valor', 0))}" for card in cartas_a_vender])
            else:
                # Mostrar solo las primeras 10 y resumen
                primeras_10 = cartas_a_vender[:10]
                cartas_texto = "\n".join([f"• {card['nombre']} - {format_gems(card.get('valor', 0))}" for card in primeras_10])
                cartas_texto += f"\n\n... y {len(cartas_a_vender) - 10} cartas más"
            
            embed.add_field(
                name="🛒 Cartas Vendidas",
                value=cartas_texto,
                inline=False
            )
            
            embed.add_field(
                name="💎 Ganancias",
                value=format_gems(gems_ganadas),
                inline=True
            )
            
            embed.add_field(
                name="📦 Cartas Restantes",
                value=f"{len(get_inventory(user_id))} cartas",
                inline=True
            )
            
            embed.add_field(
                name="💰 Nuevo Balance",
                value=format_gems(get_balance(user_id)),
                inline=True
            )
        
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ Tiempo agotado. No respondiste a tiempo. Usa `!vender_mayoreo` para intentar de nuevo.")

# 🎁 Recompensa diaria
@bot.command()
async def diaria(ctx):
    user_id = ctx.author.id
    now = time.time()
    if user_id in user_last_daily and now - user_last_daily[user_id] < 24 * 3600:
        restante = int((24 * 3600 - (now - user_last_daily[user_id])) / 3600)
        await ctx.send(f"🎁 Ya reclamaste tu recompensa diaria. Espera {restante} horas.")
        return
    add_balance(user_id, 80)
    user_last_daily[user_id] = now
    await ctx.send(f"🎁 {ctx.author.mention} reclamó su recompensa diaria de {format_gems(80)}. Total: {format_gems(get_balance(user_id))}")

# 💎 Dar gemas (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def dargemas(ctx, member: discord.Member, amount: int):
    add_balance(member.id, amount)
    await ctx.send(f"💎 {member.mention} recibió {format_gems(amount)}. Total: {format_gems(get_balance(member.id))}")

# 💎 Quitar gemas (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def quitargemas(ctx, member: discord.Member, amount: int):
    uid = str(member.id)
    if uid not in user_balances:
        await ctx.send(f"❌ {member.mention} no tiene registro de gemas.")
        return
    if user_balances[uid] < amount:
        await ctx.send(f"⚠️ {member.mention} no tiene suficientes gemas. Actualmente tiene {format_gems(user_balances[uid])}.")
        return
    user_balances[uid] -= amount
    save_data()
    await ctx.send(f"💎 A {member.mention} se le quitaron {format_gems(amount)}. Ahora tiene {format_gems(user_balances[uid])}.")

# 🗑️ Borrar inventario completo (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def limpiar_inventario(ctx, member: discord.Member):
    user_inventories[str(member.id)] = []
    save_data()
    await ctx.send(f"🗑️ Se borró todo el inventario de {member.mention}.")

# 🗑️ Borrar una carta específica (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def quitarcarta(ctx, member: discord.Member, card_id: str):
    inv = get_inventory(member.id)
    for i, card in enumerate(inv):
        if card.get("id") == card_id:
            del inv[i]
            user_inventories[str(member.id)] = inv
            save_data()
            await ctx.send(f"🗑️ Se eliminó la carta `{card['nombre']}` de {member.mention}.")
            return
    await ctx.send(f"❌ No se encontró la carta con ID `{card_id}` en el inventario de {member.mention}.")

    # ----------------------------
# COMANDO VENDER POR RAREZA
# ----------------------------
@bot.command()
async def vender_rareza(ctx, rareza: str):
    """Vende todas las cartas de una rareza específica de tu inventario"""
    user_id = ctx.author.id
    inventory = get_inventory(user_id)
    
    if not inventory:
        await ctx.send("📭 No tienes cartas en tu inventario para vender.")
        return
    
    # Validar y normalizar la rareza
    rareza = rareza.upper()
    valid_rarities = ["G", "SP", "UR", "SSR", "R", "N"]
    
    if rareza not in valid_rarities:
        await ctx.send(f"❌ Rareza inválida. Usa: {', '.join(valid_rarities)}")
        return
    
    # Filtrar cartas de la rareza especificada
    cartas_a_vender = [card for card in inventory if card.get("rareza", "N") == rareza]
    
    if not cartas_a_vender:
        await ctx.send(f"❌ No tienes cartas de rareza **{rareza}** en tu inventario.")
        return
    
    # Calcular ganancias totales
    gems_ganadas = sum(card.get('valor', 0) for card in cartas_a_vender)
    
    # Crear embed de confirmación
    embed = discord.Embed(
        title=f"💰 Venta de Cartas {rareza}",
        description=f"¿Estás seguro de que quieres vender **{len(cartas_a_vender)} cartas** de rareza **{rareza}**?",
        color=get_rarity_color(rareza)
    )
    
    # Mostrar algunas cartas (máximo 10)
    if len(cartas_a_vender) <= 10:
        cartas_texto = "\n".join([f"• {card['nombre']} - {format_gems(card.get('valor', 0))}" for card in cartas_a_vender])
    else:
        primeras_10 = cartas_a_vender[:10]
        cartas_texto = "\n".join([f"• {card['nombre']} - {format_gems(card.get('valor', 0))}" for card in primeras_10])
        cartas_texto += f"\n\n... y {len(cartas_a_vender) - 10} cartas más"
    
    embed.add_field(
        name="🛒 Cartas a Vender",
        value=cartas_texto,
        inline=False
    )
    
    embed.add_field(
        name="💎 Ganancia Total",
        value=format_gems(gems_ganadas),
        inline=True
    )
    
    embed.add_field(
        name="📦 Cartas Restantes",
        value=f"{len(inventory) - len(cartas_a_vender)} cartas",
        inline=True
    )
    
    embed.set_footer(text="Tienes 1 minuto para confirmar")
    
    # Crear vista de confirmación
    class ConfirmarVentaRarezaView(View):
        def __init__(self, rareza, cartas_a_vender, gems_ganadas):
            super().__init__(timeout=60)
            self.rareza = rareza
            self.cartas_a_vender = cartas_a_vender
            self.gems_ganadas = gems_ganadas
            self.confirmed = False
        
        @discord.ui.button(label="✅ Confirmar Venta", style=discord.ButtonStyle.green)
        async def confirm_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes confirmar tu propia venta.", ephemeral=True)
                return
            
            self.confirmed = True
            
            # Eliminar las cartas del inventario
            user_inv = get_inventory(ctx.author.id)
            nuevas_cartas = [card for card in user_inv if card.get("rareza", "N") != self.rareza]
            user_inventories[str(ctx.author.id)] = nuevas_cartas
            
            # Añadir las gemas ganadas
            add_balance(ctx.author.id, self.gems_ganadas)
            save_data()
            
            # Embed de éxito
            embed = discord.Embed(
                title="💰 ¡Venta por Rareza Exitosa!",
                description=f"Has vendido **{len(self.cartas_a_vender)} cartas** de rareza **{self.rareza}**",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="💎 Ganancias",
                value=format_gems(self.gems_ganadas),
                inline=True
            )
            
            embed.add_field(
                name="📦 Nuevo Inventario",
                value=f"{len(nuevas_cartas)} cartas",
                inline=True
            )
            
            embed.add_field(
                name="💰 Nuevo Balance",
                value=format_gems(get_balance(ctx.author.id)),
                inline=True
            )
            
            # Deshabilitar botones
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        
        @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.red)
        async def cancel_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes cancelar tu propia venta.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="❌ Venta Cancelada",
                description="La venta por rareza ha sido cancelada.",
                color=discord.Color.red()
            )
            
            # Deshabilitar botones
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        
        async def on_timeout(self):
            # Si se acaba el tiempo, deshabilitar los botones
            for item in self.children:
                item.disabled = True
            
            try:
                embed = discord.Embed(
                    title="⏰ Tiempo Agotado",
                    description="La venta por rareza ha sido cancelada por tiempo.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
            except:
                pass
    
    # Enviar mensaje de confirmación
    view = ConfirmarVentaRarezaView(rareza, cartas_a_vender, gems_ganadas)
    message = await ctx.send(embed=embed, view=view)
    view.message = message

import asyncio

# ----------------------------
# SISTEMA DE PING AL DASHBOARD (Keep Alive)
# ----------------------------



@bot.command()
async def status(ctx):
    """Muestra el estado del bot y sus servicios"""
    embed = discord.Embed(
        title="📊 Estado del Sistema Project-KC",
        color=discord.Color.blue()
    )
    
    # Estado del bot
    embed.add_field(
        name="🤖 Estado del Bot",
        value="✅ En línea y funcionando",
        inline=True
    )
    
    # Estado del dashboard
    dashboard_url = "https://Project-KC.onrender.com"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(dashboard_url, timeout=10) as response:
                if response.status == 200:
                    dashboard_status = "✅ En línea"
                else:
                    dashboard_status = f"⚠️ Código {response.status}"
    except:
        dashboard_status = "❌ Sin conexión"
    
    embed.add_field(
        name="🌐 Dashboard Web",
        value=dashboard_status,
        inline=True
    )
    
    # Estado del backup
    backup_status = "✅ Activo" if GITHUB_TOKEN else "⚠️ Sin token"
    embed.add_field(
        name="💾 Sistema de Backup",
        value=backup_status,
        inline=True
    )
    
    # Estadísticas
    total_usuarios = len(user_inventories)
    total_cartas = sum(len(inv) for inv in user_inventories.values())
    total_gemas = sum(user_balances.values())
    
    embed.add_field(
        name="📈 Estadísticas",
        value=(
            f"👥 Usuarios: {total_usuarios}\n"
            f"🎴 Cartas: {total_cartas}\n"
            f"💎 Gemas: {total_gemas}"
        ),
        inline=False
    )
    
    # Servicios activos
    embed.add_field(
        name="🛠️ Servicios Activos",
        value=(
            "• Ping automático al dashboard\n"
            "• Backup automático GitHub\n" 
            "• Servidor web estadísticas\n"
            "• Sistema de duelos PvP\n"
            "• Intercambios entre usuarios"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

# ----------------------------
# COMANDO ALBUM
# ----------------------------
@bot.command()
async def album(ctx):
    """Muestra tus cartas únicas en formato 4x4 ordenadas por rareza (sin duplicados)"""
    user_id = ctx.author.id
    inventory = get_inventory(user_id)
    
    if not inventory:
        embed = discord.Embed(
            title="📓 Colección Vacía",
            description="No tienes cartas en tu colección. ¡Usa `!gacha` para obtener algunas!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return
    
    # Eliminar duplicados (usando el ID de la carta) y ordenar por rareza
    rarity_order = {"G": 0, "SP": 1, "UR": 2, "SSR": 3, "R": 4, "N": 5}
    
    # Crear diccionario para eliminar duplicados
    unique_cards = {}
    for card in inventory:
        card_id = card.get("id")
        if card_id not in unique_cards:
            unique_cards[card_id] = card
    
    # Convertir a lista y ordenar por rareza
    unique_cards_list = list(unique_cards.values())
    unique_cards_list.sort(key=lambda x: rarity_order.get(x.get("rareza", "N"), 6))
    
    # Estadísticas
    total_cards = len(inventory)
    unique_cards_count = len(unique_cards_list)
    duplicates_count = total_cards - unique_cards_count
    
    # Crear páginas de 4x4 (16 cartas por página)
    cards_per_page = 16
    pages = [unique_cards_list[i:i + cards_per_page] for i in range(0, len(unique_cards_list), cards_per_page)]
    
    current_page = 0
    
    async def send_album_page(page_num):
        """Envía una página específica del álbum"""
        if page_num >= len(pages) or page_num < 0:
            return None
            
        page_cards = pages[page_num]
        
        # Crear embed para la página
        embed = discord.Embed(
            title=f"📓 Colección de {ctx.author.display_name}",
            description=f"Página {page_num + 1}/{len(pages)} | Cartas únicas: {unique_cards_count}/{total_cards}",
            color=discord.Color.purple()
        )
        
        # Agregar estadísticas en la primera página
        if page_num == 0:
            embed.add_field(
                name="📊 Estadísticas",
                value=(
                    f"• **Cartas totales:** {total_cards}\n"
                    f"• **Cartas únicas:** {unique_cards_count}\n"
                    f"• **Duplicados:** {duplicates_count}"
                ),
                inline=False
            )
        
        # Crear grid 4x4 con imágenes
        grid_size = 4
        grid_text = ""
        
        for row in range(grid_size):
            row_text = ""
            for col in range(grid_size):
                index = row * grid_size + col
                if index < len(page_cards):
                    card = page_cards[index]
                    rarity = card.get("rareza", "N")
                    rarity_emoji = get_rarity_emoji(rarity)
                    row_text += f"{rarity_emoji} "
                else:
                    row_text += "⚫ "  # Espacio vacío
            
            grid_text += row_text + "\n"
        
        embed.add_field(
            name=f"🎴 Cartas Únicas ({len(page_cards)} en esta página)",
            value=grid_text,
            inline=False
        )
        
        # Agregar leyenda de rarezas
        legend_text = (
            f"{get_rarity_emoji('L')} Galaxia | "
            f"{get_rarity_emoji('SP')} Special | "
            f"{get_rarity_emoji('UR')} Ultra Raro\n"
            f"{get_rarity_emoji('SSR')} SSR | "
            f"{get_rarity_emoji('R')} R | "
            f"{get_rarity_emoji('N')} Normal | "
            f"{get_rarity_emoji('C')} Común"
        )
        embed.add_field(name="📖 Galaxia", value=legend_text, inline=False)
        
        # Mostrar miniaturas de las primeras 4 cartas de la página
        if page_cards:
            # Tomar hasta 4 cartas para mostrar como miniaturas
            preview_cards = page_cards[:4]
            for i, card in enumerate(preview_cards):
                try:
                    if os.path.exists(card.get("imagen", "")):
                        file = discord.File(card["imagen"], filename=f"preview_{i}.png")
                        embed.set_thumbnail(url=f"attachment://preview_{i}.png")
                        # Solo mostrar una miniatura
                        break
                except:
                    pass
        
        # Agregar lista de cartas en esta página (solo nombres)
        if len(page_cards) <= 12:  # Mostrar lista si hay pocas cartas
            cards_list = "\n".join([
                f"{get_rarity_emoji(card.get('rareza', 'C'))} **{card['nombre']}**"
                for card in page_cards
            ])
            if cards_list:
                embed.add_field(
                    name=f"📋 Cartas en esta página",
                    value=cards_list,
                    inline=False
                )
        
        embed.set_footer(text=f"Página {page_num + 1}/{len(pages)} • Usa los botones para navegar")
        
        return embed
    
    # View para navegar el álbum
    class AlbumView(View):
        def __init__(self):
            super().__init__(timeout=180)
            self.current_page = 0
            self.message = None
            
        async def update_message(self):
            embed = await send_album_page(self.current_page)
            if embed and self.message:
                # Intentar cargar imagen para la miniatura
                page_cards = pages[self.current_page]
                if page_cards:
                    try:
                        # Tomar la primera carta de la página para la miniatura
                        first_card = page_cards[0]
                        if os.path.exists(first_card.get("imagen", "")):
                            file = discord.File(first_card["imagen"], filename="album_thumbnail.png")
                            embed.set_thumbnail(url="attachment://album_thumbnail.png")
                            await self.message.edit(embed=embed, view=self, attachments=[file])
                            return
                    except:
                        pass
                
                await self.message.edit(embed=embed, view=self)
            elif embed:
                # Para el primer mensaje, intentar incluir imagen
                page_cards = pages[self.current_page]
                if page_cards:
                    try:
                        first_card = page_cards[0]
                        if os.path.exists(first_card.get("imagen", "")):
                            file = discord.File(first_card["imagen"], filename="album_thumbnail.png")
                            embed.set_thumbnail(url="attachment://album_thumbnail.png")
                            self.message = await ctx.send(embed=embed, file=file, view=self)
                            return
                    except:
                        pass
                
                self.message = await ctx.send(embed=embed, view=self)
        
        @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.blurple)
        async def prev_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes navegar tu propia colección.", ephemeral=True)
                return
                
            self.current_page = (self.current_page - 1) % len(pages)
            await interaction.response.defer()
            await self.update_message()
        
        @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.blurple)
        async def next_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes navegar tu propia colección.", ephemeral=True)
                return
                
            self.current_page = (self.current_page + 1) % len(pages)
            await interaction.response.defer()
            await self.update_message()
        
        @discord.ui.button(label="🖼️ Ver Cartas", style=discord.ButtonStyle.green)
        async def view_cards_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes ver tus propias cartas.", ephemeral=True)
                return
            
            # Mostrar las cartas de esta página en formato carrusel
            page_cards = pages[self.current_page]
            if page_cards:
                await show_cards_carousel(interaction, page_cards, title=f"🎴 Cartas - Página {self.current_page + 1}")
            else:
                await interaction.response.send_message("❌ No hay cartas en esta página.", ephemeral=True)
        
        @discord.ui.button(label="❌ Cerrar", style=discord.ButtonStyle.red)
        async def close_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes cerrar tu propia colección.", ephemeral=True)
                return
            
            # Deshabilitar todos los botones
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            self.stop()
    
    # Mostrar el álbum
    view = AlbumView()
    await view.update_message()    

# 💝 Regalar carta (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def darcarta(ctx, member: discord.Member, card_id: str):
    found_card = None
    for rarity_cards in cards_catalog.values():
        for card in rarity_cards:
            if card.get("id") == card_id:
                found_card = card
                break
        if found_card:
            break

    if not found_card:
        await ctx.send(f"❌ No se encontró ninguna carta con ID `{card_id}`.")
        return

    add_to_inventory(member.id, found_card)

    rarity = found_card.get("rareza", "N")
    rarity_emoji = get_rarity_emoji(rarity)
    
    file = discord.File(found_card["imagen"], filename="carta.png")
    embed = discord.Embed(
        title=f"{rarity_emoji} {found_card['nombre']} ({rarity}) {rarity_emoji}",
        description=f"Te ha sido regalada por {ctx.author.mention}",
        color=get_rarity_color(rarity)
    )
    embed.set_image(url="attachment://carta.png")
    await ctx.send(embed=embed, file=file)

# 🔄 Resetear todo el progreso (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def reset_data(ctx):
    global user_inventories, user_balances, user_last_trabajar, user_last_daily, user_last_gacha, user_last_adivina, user_last_rob, user_rob_penalties
    user_inventories = {}
    user_balances = {}
    user_last_trabajar = {}
    user_last_daily = {}
    user_last_gacha = {}
    user_last_adivina = {}
    user_last_rob = {}
    user_rob_penalties = {}
    save_data()
    await ctx.send("⚠️ Todos los datos de inventario, gemas y cooldowns fueron reseteados. El catálogo de cartas sigue intacto.")

# ----------------------------
# COMANDO BORRAR BACKUPS
# ----------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def borrar_backups(ctx):
    """Elimina todos los archivos de backup del repositorio de GitHub"""
    
    if not GITHUB_TOKEN:
        embed = discord.Embed(
            title="❌ Error de Configuración",
            description="El token de GitHub no está configurado.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="💡 Solución",
            value="Agrega `GITHUB_TOKEN` en las variables de entorno de Render",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Crear vista de confirmación
    class ConfirmarBorradoBackupsView(View):
        def __init__(self):
            super().__init__(timeout=60)
            self.confirmed = False

        @discord.ui.button(label="🗑️ Confirmar Borrado", style=discord.ButtonStyle.red)
        async def confirm_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes confirmar tu propia acción.", ephemeral=True)
                return

            self.confirmed = True
            
            # Deshabilitar botones inmediatamente
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            
            # Ejecutar el borrado
            await self.borrar_backups_github(interaction)

        @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.gray)
        async def cancel_callback(self, interaction, button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Solo puedes cancelar tu propia acción.", ephemeral=True)
                return

            embed = discord.Embed(
                title="✅ Operación Cancelada",
                description="El borrado de backups ha sido cancelado.",
                color=discord.Color.green()
            )
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

        async def borrar_backups_github(self, interaction):
            """Elimina todos los archivos de la carpeta backups"""
            try:
                headers = {
                    'Authorization': f'token {GITHUB_TOKEN}',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                # Primero, obtener la lista de archivos en la carpeta backups - CORREGIDO
                url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/backups?ref={BACKUP_BRANCH}"
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    embed = discord.Embed(
                        title="❌ Error al acceder a backups",
                        description=f"No se pudo acceder a la carpeta de backups: {response.status_code} - {response.text}",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                files = response.json()
                
                # Si files es un diccionario en lugar de una lista, significa que es un solo archivo
                if isinstance(files, dict):
                    files = [files]
                    
                if not files:
                    embed = discord.Embed(
                        title="📭 Carpeta Vacía",
                        description="No hay backups para eliminar.",
                        color=discord.Color.blue()
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Contadores para el progreso
                total_files = len(files)
                deleted_files = 0
                error_files = 0
                
                # Enviar mensaje de progreso inicial
                progress_embed = discord.Embed(
                    title="🔄 Eliminando Backups...",
                    description=f"Procesando {total_files} archivos...",
                    color=discord.Color.orange()
                )
                progress_message = await interaction.followup.send(embed=progress_embed)
                
                # Eliminar cada archivo
                deleted_files_list = []
                
                for file_info in files:
                    try:
                        file_name = file_info['name']
                        file_sha = file_info['sha']
                        
                        # Crear request para eliminar el archivo - CORREGIDO
                        delete_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/backups/{file_name}"
                        delete_data = {
                            "message": f"🗑️ Eliminación manual de backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            "sha": file_sha,
                            "branch": BACKUP_BRANCH  # Especificar la rama
                        }
                        
                        delete_response = requests.delete(delete_url, headers=headers, json=delete_data, timeout=30)
                        
                        if delete_response.status_code in [200, 204]:
                            deleted_files += 1
                            deleted_files_list.append(file_name)
                            
                            # Actualizar progreso cada 5 archivos
                            if deleted_files % 5 == 0:
                                progress_embed.description = f"Progreso: {deleted_files}/{total_files} archivos eliminados..."
                                await progress_message.edit(embed=progress_embed)
                        else:
                            error_files += 1
                            print(f"❌ Error eliminando {file_name}: {delete_response.status_code} - {delete_response.text}")
                            
                    except Exception as e:
                        error_files += 1
                        print(f"❌ Error con archivo {file_info.get('name', 'unknown')}: {e}")
                
                # Crear embed de resultados finales
                result_embed = discord.Embed(
                    title="✅ Borrado de Backups Completado",
                    color=discord.Color.green() if error_files == 0 else discord.Color.orange()
                )
                
                result_embed.add_field(
                    name="📊 Resultados",
                    value=(
                        f"✅ **Archivos eliminados:** {deleted_files}\n"
                        f"❌ **Errores:** {error_files}\n"
                        f"📁 **Total procesado:** {total_files}"
                    ),
                    inline=False
                )
                
                # Mostrar algunos archivos eliminados (máximo 10)
                if deleted_files_list:
                    if len(deleted_files_list) <= 10:
                        files_text = "\n".join([f"• `{name}`" for name in deleted_files_list])
                    else:
                        files_text = "\n".join([f"• `{name}`" for name in deleted_files_list[:10]])
                        files_text += f"\n\n... y {len(deleted_files_list) - 10} archivos más"
                    
                    result_embed.add_field(
                        name="🗑️ Archivos Eliminados",
                        value=files_text,
                        inline=False
                    )
                
                if error_files > 0:
                    result_embed.add_field(
                        name="⚠️ Advertencia",
                        value="Algunos archivos no pudieron ser eliminados. Revisa los logs para más detalles.",
                        inline=False
                    )
                
                await progress_message.edit(embed=result_embed)
                
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Error Crítico",
                    description=f"Ocurrió un error durante el borrado: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed)

        async def on_timeout(self):
            # Si se acaba el tiempo, deshabilitar los botones
            for item in self.children:
                item.disabled = True
            
            try:
                embed = discord.Embed(
                    title="⏰ Tiempo Agotado",
                    description="La confirmación de borrado ha expirado.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
            except:
                pass

    # Embed de advertencia inicial
    warning_embed = discord.Embed(
        title="⚠️ ¡ADVERTENCIA! - Borrado de Backups",
        description="Estás a punto de eliminar **TODOS** los archivos de backup del repositorio.",
        color=discord.Color.red()
    )
    
    warning_embed.add_field(
        name="🔒 Acción Irreversible",
        value="Esta acción **NO SE PUEDE DESHACER**. Todos los backups serán eliminados permanentemente.",
        inline=False
    )
    
    warning_embed.add_field(
        name="📁 Ubicación",
        value=f"Repositorio: `{REPO_OWNER}/{REPO_NAME}`\nRama: `{BACKUP_BRANCH}`\nCarpeta: `/backups/`",
        inline=False
    )
    
    warning_embed.add_field(
        name="✅ Confirmación Requerida",
        value="Presiona **Confirmar Borrado** para proceder o **Cancelar** para abortar.",
        inline=False
    )
    
    warning_embed.set_footer(text="Tienes 1 minuto para confirmar")
    
    view = ConfirmarBorradoBackupsView()
    message = await ctx.send(embed=warning_embed, view=view)
    view.message = message

@bot.command()
@commands.has_permissions(administrator=True)
async def listar_backups(ctx):
    """Muestra todos los backups disponibles en el repositorio"""
    
    if not GITHUB_TOKEN:
        embed = discord.Embed(
            title="❌ Error de Configuración",
            description="El token de GitHub no está configurado.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Obtener la lista de archivos en la carpeta backups - CORREGIDO
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/backups?ref={BACKUP_BRANCH}"
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            embed = discord.Embed(
                title="❌ Carpeta No Encontrada",
                description=f"No se encontró la carpeta backups en la rama `{BACKUP_BRANCH}`",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Verificación",
                value="Asegúrate de que la rama existe y tiene la carpeta backups",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        if response.status_code != 200:
            embed = discord.Embed(
                title="❌ Error al acceder a backups",
                description=f"Error {response.status_code}: {response.text}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        files = response.json()
        
        # Si files es un diccionario en lugar de una lista, significa que es un solo archivo
        if isinstance(files, dict):
            files = [files]
        
        if not files:
            embed = discord.Embed(
                title="📭 No hay Backups",
                description="La carpeta de backups existe pero está vacía.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        # Ordenar archivos por fecha (más recientes primero)
        files.sort(key=lambda x: x.get('name', ''), reverse=True)
        
        # Crear embed con la lista de backups
        embed = discord.Embed(
            title="📊 Lista de Backups Disponibles",
            description=f"Total de backups: {len(files)}",
            color=discord.Color.blue()
        )
        
        # Mostrar los 15 backups más recientes
        for i, file_info in enumerate(files[:15], 1):
            file_name = file_info['name']
            size_kb = file_info.get('size', 0) / 1024
            download_url = file_info.get('download_url', '')
            
            # Extraer fecha del nombre del archivo si es posible
            if 'backup_' in file_name and ('_data.json' in file_name or '_catalogo.json' in file_name):
                date_part = file_name.replace('backup_', '').replace('_data.json', '').replace('_catalogo.json', '')
                try:
                    # Intentar parsear la fecha
                    date_obj = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                    date_display = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    date_display = "Fecha desconocida"
            else:
                date_display = "Formato desconocido"
            
            embed.add_field(
                name=f"{i}. {file_name}",
                value=f"📅 {date_display} | 📏 {size_kb:.1f} KB",
                inline=False
            )
        
        if len(files) > 15:
            embed.set_footer(text=f"Mostrando 15 de {len(files)} backups. Usa !borrar_backups para eliminarlos.")
        else:
            embed.set_footer(text="Usa !borrar_backups para eliminar todos los backups")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error al listar backups: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# 🧹 Limpiar mensajes del chat (admins)
@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 10):
    """Borra la cantidad de mensajes indicada (por defecto 10)."""
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Se borraron {amount} mensajes.", delete_after=5)

# ----------------------------
# INICIAR SERVIDOR WEB (AL FINAL, ANTES DEL bot.run)
# ----------------------------
try:
    # Importar y configurar el servidor web
    # Pasar las variables del bot al webserver
    import webserver
    from webserver import start_webserver
    webserver.user_inventories = user_inventories
    webserver.user_balances = user_balances
    webserver.catalog_cards = catalog_cards
    webserver.cards_catalog = cards_catalog
    webserver.pending_trades = pending_trades
    webserver.user_last_trabajar = user_last_trabajar
    webserver.user_last_daily = user_last_daily
    webserver.user_last_gacha = user_last_gacha
    webserver.user_last_adivina = user_last_adivina
    webserver.user_last_rob = user_last_rob
    webserver.user_rob_penalties = user_rob_penalties

    # Iniciar servidor web
    if start_webserver():
        print("✅ Servidor web iniciado en http://localhost:5000")
    else:
        print("❌ No se pudo iniciar el servidor web")
        
except Exception as e:
    print(f"⚠️  Servidor web no disponible: {e}")

    # ----------------------------
import threading
from datetime import datetime

# SISTEMA DE BACKUP AUTOMÁTICO
# ----------------------------
import requests
import schedule

# Configuración de GitHub para backup
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')  # Usar variable de entorno
REPO_OWNER = "CosmicDragneel21"
REPO_NAME = "Project-KC"
BACKUP_BRANCH = "backup-auto"

def create_github_backup():
    """Crea un backup automático en GitHub"""
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN no configurado - Skipping backup")
        return
    
    try:
        print("🔄 Iniciando backup automático...")
        
        # Leer los archivos de datos actualizados
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data_content = f.read()
        
        with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
            catalog_content = f.read()
        
        # Headers para la API de GitHub
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Crear backup con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_files = {
            f"backup_{timestamp}_data.json": data_content,
            f"backup_{timestamp}_catalogo.json": catalog_content
        }
        
        success_count = 0
        
        for filename, content in backup_files.items():
            try:
                # Codificar contenido en base64 (GitHub requiere base64)
                import base64
                content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                
                # Crear commit en GitHub
                url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/backups/{filename}"
                
                data = {
                    "message": f"🤖 Backup automático - {timestamp}",
                    "content": content_base64,
                    "branch": BACKUP_BRANCH
                }
                
                response = requests.put(url, headers=headers, json=data, timeout=30)
                
                if response.status_code in [201, 200]:
                    print(f"✅ Backup creado: {filename}")
                    success_count += 1
                else:
                    error_msg = response.json().get('message', 'Unknown error')
                    print(f"❌ Error en backup {filename}: {error_msg}")
                    
            except Exception as e:
                print(f"❌ Error subiendo {filename}: {e}")
        
        print(f"📊 Backup completado: {success_count}/2 archivos")
                
    except Exception as e:
        print(f"❌ Error en backup automático: {e}")

def backup_on_user_action():
    """Backup cuando hay una acción importante de usuario"""
    try:
        # Usar un hilo separado para no bloquear el bot
        thread = threading.Thread(target=create_github_backup, daemon=True)
        thread.start()
    except Exception as e:
        print(f"❌ Error en backup de acción: {e}")

# Guardar referencias a las funciones originales
original_add_to_inventory = add_to_inventory
original_add_balance = add_balance
original_save_data = save_data

# Versiones con backup de las funciones críticas
def add_to_inventory_with_backup(user_id, card):
    """Versión con backup de add_to_inventory"""
    result = original_add_to_inventory(user_id, card)
    backup_on_user_action()
    return result

def add_balance_with_backup(user_id, amount):
    """Versión con backup de add_balance"""
    result = original_add_balance(user_id, amount)
    backup_on_user_action()
    return result

def save_data_with_backup():
    """Versión con backup de save_data"""
    result = original_save_data()
    backup_on_user_action()
    return result

# Reemplazar las funciones originales con las versiones con backup
add_to_inventory = add_to_inventory_with_backup
add_balance = add_balance_with_backup
save_data = save_data_with_backup

# Backup programado cada 6 horas
def scheduled_backup():
    """Backup programado"""
    print("⏰ Ejecutando backup programado...")
    create_github_backup()

def run_scheduled_backups():
    """Ejecutar backups programados en un hilo separado"""
    # Configurar schedule
    schedule.every(6).hours.do(scheduled_backup)
    schedule.every().day.at("00:00").do(scheduled_backup)  # Backup adicional a medianoche
    
    print("🕒 Programador de backups iniciado")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Revisar cada minuto
        except Exception as e:
            print(f"❌ Error en programador: {e}")
            time.sleep(60)

# Iniciar hilo de backups programados
try:
    backup_thread = threading.Thread(target=run_scheduled_backups, daemon=True)
    backup_thread.start()
    print("✅ Sistema de backup automático iniciado")
except Exception as e:
    print(f"❌ No se pudo iniciar el sistema de backup: {e}")

# ----------------------------
# COMANDOS DE BACKUP MANUAL
# ----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def backup_now(ctx):
    """Crea un backup manual inmediato"""
    await ctx.send("🔄 Creando backup... Esto puede tomar unos segundos.")
    
    try:
        create_github_backup()
        await ctx.send("✅ Backup creado exitosamente en GitHub")
    except Exception as e:
        await ctx.send(f"❌ Error creando backup: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def backup_status(ctx):
    """Muestra el estado del sistema de backup"""
    embed = discord.Embed(
        title="📊 Estado del Sistema de Backup",
        color=discord.Color.blue()
    )
    
    has_token = bool(GITHUB_TOKEN)
    embed.add_field(
        name="🔑 Token de GitHub",
        value="✅ Configurado" if has_token else "❌ No configurado",
        inline=True
    )
    
    embed.add_field(
        name="🕒 Backup Programado",
        value="Cada 6 horas + acciones de usuarios",
        inline=True
    )
    
    embed.add_field(
        name="📁 Rama de Backup",
        value=BACKUP_BRANCH,
        inline=True
    )
    
    if not has_token:
        embed.add_field(
            name="⚠️ Configuración Requerida",
            value="Agrega `GITHUB_TOKEN` en las variables de entorno de Render",
            inline=False
        )
    
    await ctx.send(embed=embed)

    # ----------------------------
# COMANDO PARA MODIFICAR RATES (Solo administradores)
# ----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def modificar_rates(ctx):
    """Interfaz para modificar las probabilidades del gacha"""
    
    # Crear embed con las probabilidades actuales
    embed = discord.Embed(
        title="🎰 Modificar Probabilidades del Gacha",
        description="**Probabilidades actuales:**",
        color=discord.Color.blue()
    )
    
    # Mostrar probabilidades actuales
    for rarity, prob in rarity_probabilities.items():
        percentage = prob * 100
        emoji = get_rarity_emoji(rarity)
        embed.add_field(
            name=f"{emoji} {rarity}",
            value=f"{percentage:.2f}%",
            inline=True
        )
    
    embed.add_field(
        name="📊 Total Actual",
        value=f"{sum(rarity_probabilities.values()) * 100:.2f}%",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Importante",
        value="Las probabilidades deben sumar exactamente 100%",
        inline=False
    )
    
    # Crear botones para cada rareza
    view = View(timeout=300)
    
    # Función para crear callback para cada rareza
    def create_rarity_callback(rarity):
        async def rarity_callback(interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Solo los administradores pueden modificar los rates.", ephemeral=True)
                return
            
            # Crear modal para modificar esta rareza
            modal = ModificarRateModal(rarity, rarity_probabilities[rarity])
            await interaction.response.send_modal(modal)
        
        return rarity_callback
    
    # Crear botones para cada rareza
    rarities = ["G", "SP", "UR", "SSR", "R", "N"]
    for rarity in rarities:
        emoji = get_rarity_emoji(rarity)
        btn = Button(label=f"Modificar {rarity}", style=discord.ButtonStyle.blurple, emoji=emoji)
        btn.callback = create_rarity_callback(rarity)
        view.add_item(btn)
    
    # Botón para restablecer valores por defecto
    async def reset_callback(interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo los administradores pueden modificar los rates.", ephemeral=True)
            return
        
        # Restablecer probabilidades por defecto
        global rarity_probabilities
        rarity_probabilities = {
            "G": 0.010,   # Galaxia (1%) - aumentado de 0.5%
            "SP": 0.020,  # Special (2%) - aumentado de 1%
            "UR": 0.035,  # Ultra Raro (3.5%) - aumentado de 1.5%
            "SSR": 0.065, # Super Super Raro (6.5%) - aumentado de 3%
            "R": 0.100,  # Super Raro (10%) - aumentado de 6%
            "N": 0.770,   # Normal (77%) - aumentado de 20%
        }
        
        embed = discord.Embed(
            title="✅ Probabilidades Restablecidas",
            description="Se han restablecido las probabilidades por defecto.",
            color=discord.Color.green()
        )
        
        # Mostrar nuevas probabilidades
        for rarity, prob in rarity_probabilities.items():
            percentage = prob * 100
            emoji = get_rarity_emoji(rarity)
            embed.add_field(
                name=f"{emoji} {rarity}",
                value=f"{percentage:.2f}%",
                inline=True
            )
        
        embed.add_field(
            name="📊 Total",
            value=f"{sum(rarity_probabilities.values()) * 100:.2f}%",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    reset_btn = Button(label="🔄 Restablecer Default", style=discord.ButtonStyle.gray)
    reset_btn.callback = reset_callback
    view.add_item(reset_btn)
    
    await ctx.send(embed=embed, view=view)

class ModificarRateModal(discord.ui.Modal, title='🎰 Modificar Probabilidad'):
    def __init__(self, rarity, current_prob):
        super().__init__()
        self.rarity = rarity
        self.current_prob = current_prob
        
        # Campo para ingresar el nuevo porcentaje
        self.add_item(discord.ui.TextInput(
            label=f'Nuevo porcentaje para {rarity}',
            placeholder=f'Actual: {current_prob * 100:.2f}% - Ej: 1.5 para 1.5%',
            default=str(current_prob * 100),
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            nuevo_porcentaje = float(self.children[0].value.strip())
            
            # Validar que sea un número positivo
            if nuevo_porcentaje < 0:
                await interaction.response.send_message("❌ El porcentaje debe ser un número positivo.", ephemeral=True)
                return
            
            # Convertir porcentaje a probabilidad (de 0.0 a 1.0)
            nueva_probabilidad = nuevo_porcentaje / 100.0
            
            # Guardar la probabilidad anterior para cálculos
            prob_anterior = rarity_probabilities[self.rarity]
            
            # Actualizar la probabilidad
            rarity_probabilities[self.rarity] = nueva_probabilidad
            
            # Calcular diferencia
            diferencia = nueva_probabilidad - prob_anterior
            
            # Ajustar automáticamente la rareza C para mantener el total en 100%
            if self.rarity != "N":
                rarity_probabilities["N"] -= diferencia
            
            # Verificar que el total sea 100%
            total = sum(rarity_probabilities.values())
            
            if abs(total - 1.0) > 0.001:  # Permitir pequeña tolerancia
                # Si no suma 100%, ajustar la rareza C
                rarity_probabilities["N"] += (1.0 - total)
            
            # Verificar que todas las probabilidades sean válidas
            for rarity, prob in rarity_probabilities.items():
                if prob < 0:
                    await interaction.response.send_message(
                        f"❌ Error: La probabilidad de {rarity} sería negativa ({prob:.4f}). "
                        f"Ajusta otros rates primero.",
                        ephemeral=True
                    )
                    # Revertir cambios
                    rarity_probabilities[self.rarity] = prob_anterior
                    # Restaurar probabilidades por defecto para C temporalmente
                    rarity_probabilities["N"] = 0.770
                    return
            
            # Crear embed de confirmación
            embed = discord.Embed(
                title="✅ Probabilidad Actualizada",
                description=f"**{self.rarity}** modificado exitosamente",
                color=discord.Color.green()
            )
            
            # Mostrar cambios
            embed.add_field(
                name="📊 Cambios Realizados",
                value=(
                    f"**{self.rarity}**: {prob_anterior * 100:.2f}% → {nueva_probabilidad * 100:.2f}%\n"
                    f"**C**: {prob_anterior * 100:.2f}% → {rarity_probabilities['C'] * 100:.2f}%"
                ),
                inline=False
            )
            
            # Mostrar todas las probabilidades actualizadas
            embed.add_field(
                name="🎰 Probabilidades Actuales",
                value="\n".join([
                    f"{get_rarity_emoji(rarity)} {rarity}: {prob * 100:.2f}%"
                    for rarity, prob in rarity_probabilities.items()
                ]),
                inline=False
            )
            
            embed.add_field(
                name="📈 Total",
                value=f"{sum(rarity_probabilities.values()) * 100:.2f}%",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Actualizar el mensaje original con las nuevas probabilidades
            original_embed = discord.Embed(
                title="🎰 Modificar Probabilidades del Gacha",
                description="**Probabilidades actuales:**",
                color=discord.Color.blue()
            )
            
            for rarity, prob in rarity_probabilities.items():
                percentage = prob * 100
                emoji = get_rarity_emoji(rarity)
                original_embed.add_field(
                    name=f"{emoji} {rarity}",
                    value=f"{percentage:.2f}%",
                    inline=True
                )
            
            original_embed.add_field(
                name="📊 Total Actual",
                value=f"{sum(rarity_probabilities.values()) * 100:.2f}%",
                inline=False
            )
            
            original_embed.add_field(
                name="✅ Cambio Realizado",
                value=f"{interaction.user.mention} modificó {self.rarity}",
                inline=False
            )
            
            # Recrear la vista
            view = View(timeout=300)
            
            def create_rarity_callback(rarity):
                async def rarity_callback(interaction):
                    if not interaction.user.guild_permissions.administrator:
                        await interaction.response.send_message("❌ Solo los administradores pueden modificar los rates.", ephemeral=True)
                        return
                    
                    modal = ModificarRateModal(rarity, rarity_probabilities[rarity])
                    await interaction.response.send_modal(modal)
                
                return rarity_callback
            
            rarities = ["G", "SP", "UR", "SSR", "R", "N"]
            for rarity in rarities:
                emoji = get_rarity_emoji(rarity)
                btn = Button(label=f"Modificar {rarity}", style=discord.ButtonStyle.blurple, emoji=emoji)
                btn.callback = create_rarity_callback(rarity)
                view.add_item(btn)
            
            async def reset_callback(interaction):
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ Solo los administradores pueden modificar los rates.", ephemeral=True)
                    return
                
                global rarity_probabilities
                rarity_probabilities = {
                    "G": 0.010, "SP": 0.020, "UR": 0.035, "SSR": 0.065,
                    "R": 0.100, "N": 0.770
                }
                
                embed = discord.Embed(
                    title="✅ Probabilidades Restablecidas",
                    description="Se han restablecido las probabilidades por defecto.",
                    color=discord.Color.green()
                )
                
                for rarity, prob in rarity_probabilities.items():
                    percentage = prob * 100
                    emoji = get_rarity_emoji(rarity)
                    embed.add_field(
                        name=f"{emoji} {rarity}",
                        value=f"{percentage:.2f}%",
                        inline=True
                    )
                
                embed.add_field(
                    name="📊 Total",
                    value=f"{sum(rarity_probabilities.values()) * 100:.2f}%",
                    inline=False
                )
                
                await interaction.response.edit_message(embed=embed, view=view)
            
            reset_btn = Button(label="🔄 Restablecer Default", style=discord.ButtonStyle.gray)
            reset_btn.callback = reset_callback
            view.add_item(reset_btn)
            
            # Editar el mensaje original
            await interaction.message.edit(embed=original_embed, view=view)
            
        except ValueError:
            await interaction.response.send_message("❌ Por favor ingresa un número válido (ej: 1.5 para 1.5%).", ephemeral=True)

# ----------------------------
# ESTADO GLOBAL PARA ELECCIÓN DE CARTAS GLOBAL
# ----------------------------
# Almacena la oferta global activa: [card_id_1, card_id_2] o None si no hay oferta.
current_global_choice = None

# Almacena los IDs de usuario que ya han reclamado la recompensa.
users_claimed_global_choice = set()

# ----------------------------
# FUNCIONES DE UTILITY (Asumiendo que no existen)
# ----------------------------

def find_card_by_id(card_id):
    """Busca una carta en el catálogo por su ID."""
    # Nota: Asume que 'catalog_cards' está cargado y disponible
    for card in catalog_cards:
        if str(card.get('id')) == str(card_id):
            return card
    return None

# Debes asegurarte de que esta función exista y que get_user_data y save_data también lo hagan
def add_card_to_inventory(user_id, card_id, amount=1):
    """Añade una carta al inventario del usuario."""
    # **REEMPLAZA ESTO CON TUS FUNCIONES REALES DE GESTIÓN DE DATOS**
    # Si ya tienes estas funciones definidas en otra parte, no las redefinas,
    # solo asegúrate de que find_card_by_id esté disponible.
    try:
        user_data = get_user_data(user_id) 
        inventory = user_data.get('inventory', {})
        inventory[card_id] = inventory.get(card_id, 0) + amount
        user_data['inventory'] = inventory
        save_data()
    except NameError:
        print("ADVERTENCIA: Las funciones get_user_data/save_data/add_card_to_inventory no están definidas.")
        # Manejo de error si las funciones no existen
        pass

    # ----------------------------
# VISTAS PARA ELECCIÓN DE CARTA
# ----------------------------

class CardChoiceView(discord.ui.View):
    def __init__(self, user_id, cards_data, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        # cards_data: Lista de [card_id, card_name, card_rareza]
        self.cards_data = cards_data 
        self.chosen_card_id = None
        self._create_choice_buttons()

    def _create_choice_buttons(self):
        """Crea los botones de elección iniciales."""
        self.clear_items()
        for card in self.cards_data:
            card_id, card_name, _ = card
            button = discord.ui.Button(
                label=f"Elegir {card_name}",
                style=discord.ButtonStyle.primary,
                custom_id=f"card_choice_{card_id}",
                row=0
            )
            # Usar lambda para pasar el card_id al callback
            button.callback = lambda interaction, cid=card_id: self.choice_callback(interaction, cid)
            self.add_item(button)

    async def confirm_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Esta elección es solo para ti.", ephemeral=True)

        if not self.chosen_card_id:
            return await interaction.response.send_message("❌ No has seleccionado una carta aún.", ephemeral=True)
        
        # 🛑 NUEVA LÓGICA DE RECLAMO GLOBAL 🛑
        if self.user_id in users_claimed_global_choice:
             # Doble verificación por seguridad, aunque el comando !eleccion_recompensa ya la hace
            self.clear_items()
            self.stop()
            return await interaction.response.edit_message(content="🛑 Ya has reclamado esta recompensa.", embed=None, view=None)

        # 1. Procesar recompensa (añadir al inventario)
        add_card_to_inventory(self.user_id, self.chosen_card_id)
        
        # 2. Marcar al usuario como reclamante
        users_claimed_global_choice.add(self.user_id)
        
        chosen_card = find_card_by_id(self.chosen_card_id)
        chosen_name = chosen_card['nombre']
        
        # 3. Actualizar mensaje final
        self.clear_items()
        self.stop()
        
        embed = interaction.message.embeds[0]
        embed.title = "🎉 ¡Recompensa Reclamada!"
        embed.description = f"Has elegido exitosamente **{chosen_name}** ({self.chosen_card_id}) y se ha añadido a tu inventario."
        embed.color = discord.Color.green()
        embed.set_footer(text="¡Disfruta tu nueva carta!")
        
        await interaction.response.edit_message(embed=embed, view=self)


    async def confirm_callback(self, interaction: discord.Interaction):
        """Maneja la confirmación final de la elección."""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Esta elección es solo para ti.", ephemeral=True)

        if not self.chosen_card_id:
            return await interaction.response.send_message("❌ No has seleccionado una carta aún.", ephemeral=True)
        
        # 1. Procesar recompensa (añadir al inventario)
        add_card_to_inventory(self.user_id, self.chosen_card_id)
        
        # 2. Limpiar oferta del estado global
        if self.user_id in card_choice_offers:
            del card_choice_offers[self.user_id]
        
        chosen_card = find_card_by_id(self.chosen_card_id)
        chosen_name = chosen_card['nombre']
        
        # 3. Actualizar mensaje final
        self.clear_items()
        self.stop() # Detener la vista
        
        embed = interaction.message.embeds[0]
        embed.title = "🎉 ¡Recompensa Reclamada!"
        embed.description = f"Has elegido exitosamente **{chosen_name}** ({self.chosen_card_id}) y se ha añadido a tu inventario."
        embed.color = discord.Color.green()
        embed.set_footer(text="¡Disfruta tu nueva carta!")
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel_callback(self, interaction: discord.Interaction):
        """Maneja la cancelación y vuelve a la vista de elección inicial."""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Esta elección es solo para ti.", ephemeral=True)

        # Restaurar la vista original
        self.chosen_card_id = None
        self._create_choice_buttons()

        embed = interaction.message.embeds[0]
        embed.set_footer(text="Selecciona una de las cartas ofrecidas.")

        await interaction.response.edit_message(embed=embed, view=self)

# ----------------------------
# COMANDO DE USUARIO: !eleccion_recompensa y !eleccion_carta
# ----------------------------

# ----------------------------
# COMANDOS DE ELECCIÓN DE CARTA (¡Colócalos a nivel superior!)
# ----------------------------

@bot.command(name="eleccion_carta")
@commands.has_permissions(administrator=True)
async def eleccion_carta(ctx, card_id1: str, card_id2: str): 
    """
    [ADMIN] Establece una elección global entre dos cartas para todos los usuarios.
    Uso: !eleccion_carta <id_carta1> <id_carta2>
    """
    global current_global_choice, users_claimed_global_choice

    if current_global_choice:
        return await ctx.send("❌ Error: Ya existe una elección de carta global activa. Usa `!cancelar_eleccion` para limpiarla antes de crear una nueva.")
        
    card1 = find_card_by_id(card_id1)
    card2 = find_card_by_id(card_id2)

    if not card1 or not card2:
        error_msg = "❌ Error: Una o ambas IDs de carta no son válidas. No se ha creado la elección."
        return await ctx.send(error_msg)

    # Almacenar la oferta global y resetear la lista de reclamantes
    current_global_choice = [card_id1, card_id2]
    users_claimed_global_choice.clear() 

    # ... (Resto del código para el embed) ...
    embed = discord.Embed(
        title="✨ ¡Elección de Carta Global ACTIVADA!",
        description="Una nueva recompensa de elección ha sido establecida. **Cualquier usuario puede usar `!eleccion_recompensa` para reclamarla (una sola vez por usuario).**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Opción 1", value=f"{card1['nombre']} ({card1['rareza']})", inline=True)
    embed.add_field(name="Opción 2", value=f"{card2['nombre']} ({card2['rareza']})", inline=True)
    embed.set_footer(text="¡Date prisa y reclama tu carta!")

    await ctx.send(embed=embed)

# ----------------------------
# COMANDO DE USUARIO: !eleccion_recompensa
# ----------------------------

@bot.command(name="eleccion_recompensa")
async def eleccion_recompensa(ctx):
    """
    Permite al usuario reclamar una carta de la elección global ofrecida mediante texto.
    """
    user_id = ctx.author.id
    global current_global_choice, users_claimed_global_choice

    if not current_global_choice:
        return await ctx.send("❌ Actualmente **no hay** una elección de carta global activa para reclamar. ¡Consulta a un administrador!")

    if user_id in users_claimed_global_choice:
        return await ctx.send("🛑 Ya has reclamado tu recompensa de elección de carta global.")

    card_id1, card_id2 = current_global_choice
    card1 = find_card_by_id(card_id1)
    card2 = find_card_by_id(card_id2)

    if not card1 or not card2:
        return await ctx.send("❌ Error interno: La oferta global es inválida. Contacta al administrador.")

    embed = discord.Embed(
        title="💌 ¡Reclama tu Elección Global!",
        description=f"**{ctx.author.mention}**, selecciona una de estas dos cartas. **Solo puedes elegir una vez.**\n\n**¡Responde a este mensaje con `opcion 1` o `opcion 2` para hacer tu elección!**",
        color=discord.Color.gold()
    )
    
    # Mostrar detalles de las cartas
    embed.add_field(
        name=f"1. {card1['nombre']} ({card1['rareza']})",
        value=f"**Opción 1** | ID: `{card_id1}`",
        inline=False
    )
    embed.add_field(
        name=f"2. {card2['nombre']} ({card2['rareza']})",
        value=f"**Opción 2** | ID: `{card_id2}`",
        inline=False
    )

    embed.set_footer(text="Tienes 30 segundos para responder con 'opcion 1' o 'opcion 2'.")

    # Enviar el mensaje y esperar la respuesta
    await ctx.send(embed=embed)
    
    def check(m):
        # Verifica que el mensaje provenga del mismo usuario, en el mismo canal
        # y que el contenido sea 'opcion 1' o 'opcion 2' (sin importar mayúsculas)
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['opcion 1', 'opcion 2']

    try:
        # Esperar la respuesta del usuario por 30 segundos
        msg = await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        return await ctx.send("⏳ Tiempo agotado. No seleccionaste una carta a tiempo. La oferta sigue activa.")

    # Procesar la elección
    eleccion = msg.content.lower()
    
    if eleccion == 'opcion 1':
        chosen_card_id = card_id1
        chosen_card_name = card1['nombre']
    elif eleccion == 'opcion 2':
        chosen_card_id = card_id2
        chosen_card_name = card2['nombre']
    else:
        # Esto no debería ocurrir gracias a la función check
        return await ctx.send("❌ Elección inválida. Inténtalo de nuevo con `!eleccion_recompensa`.")

    # ******* Lógica de confirmación y reclamo *******
    
    # 1. Añadir la carta al inventario (usando la función que ya tienes)
    chosen_card = find_card_by_id(chosen_card_id)
    if chosen_card:
        add_to_inventory(user_id, chosen_card) 
    
    # 2. Marcar al usuario como reclamante
    users_claimed_global_choice.add(user_id)

    # Mensaje de confirmación final
    embed_final = discord.Embed(
        title="🎉 ¡Recompensa Reclamada!",
        description=f"Has elegido exitosamente **{chosen_card_name}** (`{chosen_card_id}`) y se ha añadido a tu inventario.\n\nLa elección global ha sido registrada para ti.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed_final)

    # ----------------------------
# COMANDO DE ADMINISTRACIÓN: !cancelar_eleccion
# ----------------------------

@bot.command(name="cancelar_eleccion")
@commands.has_permissions(administrator=True)
async def cancelar_eleccion(ctx):
    """
    [ADMIN] Cancela la elección de carta global actual y resetea los reclamantes.
    """
    global current_global_choice, users_claimed_global_choice

    if not current_global_choice:
        return await ctx.send("⚠️ No hay ninguna elección de carta global activa para cancelar.")
    
    current_global_choice = None
    reclamantes = len(users_claimed_global_choice)
    users_claimed_global_choice.clear()
    
    await ctx.send(f"✅ La elección de carta global ha sido **CANCELADA**.\nSe resetearon los datos de **{reclamantes}** usuarios que ya habían reclamado.")

    # Se debe guardar el estado de estas variables globales para que persista
    # entre reinicios del bot.



# ----------------------------
# COMANDO RAPIDO PARA VER RATES
# ----------------------------
@bot.command()
async def rates(ctx):
    """Muestra las probabilidades actuales del gacha"""
    
    embed = discord.Embed(
        title="🎰 Probabilidades del Gacha",
        description="Estas son las probabilidades actuales de obtener cada rareza:",
        color=discord.Color.gold()
    )
    
    # Mostrar probabilidades en orden de rareza
    rarities_order = ["G", "SP", "UR", "SSR", "R", "N"]
    
    for rarity in rarities_order:
        prob = rarity_probabilities.get(rarity, 0)
        percentage = prob * 100
        emoji = get_rarity_emoji(rarity)
        
        embed.add_field(
            name=f"{emoji} {rarity}",
            value=f"{percentage:.3f}%",
            inline=True
        )
    
    embed.add_field(
        name="📊 Total",
        value=f"{sum(rarity_probabilities.values()) * 100:.3f}%",
        inline=False
    )
    
    embed.set_footer(text="Usa !modificar_rates (admin) para cambiar las probabilidades")
    
    await ctx.send(embed=embed)


    # ----------------------------
# RECOMPENSA FIJA DE GEMAS (ADMIN)
# ----------------------------
active_gem_reward = {
    "amount": 0,
    "expires_at": 0,
    "claimed_users": set()
}

@bot.command()
@commands.has_permissions(administrator=True)
async def gemas_fijas(ctx, cantidad: int, tiempo_horas: float):
    """Establece una recompensa fija de gemas con límite de tiempo (solo admins)"""
    global active_gem_reward
    if cantidad <= 0 or tiempo_horas <= 0:
        await ctx.send("❌ Usa valores válidos. Ejemplo: `!gemas_fijas 100 2` (100 gemas por 2 horas)")
        return

    expires_at = time.time() + tiempo_horas * 3600
    active_gem_reward = {
        "amount": cantidad,
        "expires_at": expires_at,
        "claimed_users": set()
    }

    embed = discord.Embed(
        title="💎 Recompensa Fija Activada",
        description=f"Los usuarios pueden reclamar **{cantidad} gemas** usando `!recibir_gemas` durante las próximas **{tiempo_horas} horas**.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Comando exclusivo de administradores")
    await ctx.send(embed=embed)

@bot.command()
async def recibir_gemas(ctx):
    """Permite reclamar la recompensa fija de gemas activa"""
    global active_gem_reward
    user_id = str(ctx.author.id)
    now = time.time()

    if active_gem_reward["amount"] == 0 or now > active_gem_reward["expires_at"]:
        await ctx.send("❌ No hay recompensas activas actualmente.")
        return

    if user_id in active_gem_reward["claimed_users"]:
        await ctx.send("⚠️ Ya reclamaste esta recompensa.")
        return

    # Dar gemas
    add_balance(ctx.author.id, active_gem_reward["amount"])
    active_gem_reward["claimed_users"].add(user_id)

    embed = discord.Embed(
        title="🎁 ¡Recompensa Reclamada!",
        description=f"Has recibido **{active_gem_reward['amount']} gemas** 💎",
        color=discord.Color.green()
    )
    embed.set_footer(text="Sigue participando para más recompensas.")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def estado_gemas_fijas(ctx):
    """Muestra el estado actual de la recompensa fija (solo admins)"""
    global active_gem_reward
    if active_gem_reward["amount"] == 0 or time.time() > active_gem_reward["expires_at"]:
        await ctx.send("❌ No hay recompensas activas actualmente.")
        return

    restante = int((active_gem_reward["expires_at"] - time.time()) / 60)
    await ctx.send(
        f"💎 **Recompensa activa:** {active_gem_reward['amount']} gemas\n"
        f"⏰ **Tiempo restante:** {restante} minutos\n"
        f"👥 **Usuarios que reclamaron:** {len(active_gem_reward['claimed_users'])}"
    )

    # ----------------------------
# COMANDO PARA CANCELAR RECOMPENSA FIJA DE GEMAS
# ----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def cancelar_gemas_fijas(ctx):
    """Cancela la recompensa fija de gemas activa (solo admins)"""
    global active_gem_reward
    
    # Verificar si hay una recompensa activa
    if active_gem_reward.get("amount", 0) == 0:
        await ctx.send("❌ No hay ninguna recompensa fija de gemas activa.")
        return
    
    # Guardar información de la recompensa cancelada para el mensaje
    cantidad = active_gem_reward["amount"]
    expira_en = active_gem_reward["expires_at"]
    ahora = time.time()
    
    # Calcular tiempo restante
    if expira_en > ahora:
        tiempo_restante = expira_en - ahora
        horas = int(tiempo_restante // 3600)
        minutos = int((tiempo_restante % 3600) // 60)
        tiempo_texto = f"{horas}h {minutos}m restantes"
    else:
        tiempo_texto = "Ya expirada"
    
    # Cancelar la recompensa
    usuarios_que_reclamaron = len(active_gem_reward.get("claimed_users", set()))
    
    # Resetear la recompensa
    active_gem_reward = {
        "amount": 0,
        "expires_at": 0,
        "claimed_users": set()
    }
    
    # Crear embed de confirmación
    embed = discord.Embed(
        title="❌ Recompensa Fija Cancelada",
        description=f"Se ha cancelado la recompensa fija de {cantidad} gemas.",
        color=discord.Color.red()
    )
    
    embed.add_field(
        name="📊 Estadísticas",
        value=(
            f"**Cantidad:** {cantidad} gemas\n"
            f"**Tiempo restante:** {tiempo_texto}\n"
            f"**Usuarios que reclamaron:** {usuarios_que_reclamaron}"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Efecto",
        value="Los usuarios ya no podrán reclamar esta recompensa con `!reward_gemas`",
        inline=False
    )
    
    embed.set_footer(text=f"Cancelada por {ctx.author.display_name}")
    
    await ctx.send(embed=embed) 



# ----------------------------
# UTILIDAD PARA BOTONES (Ejecutar Comandos) - VERSIÓN FINAL Y ROBUSTA
# ----------------------------

async def invoke_command_from_interaction(bot, interaction: discord.Interaction, command_name: str, args=None):
    """
    Simula la ejecución de un comando (e.g., !gacha) a partir de una interacción de botón/modal.
    """
    
    # 1. Diferir la respuesta (HACERLA PÚBLICA EXPLÍCITAMENTE)
    try:
        if interaction.response.is_done():
            # Usamos followup para mensajes de modal o si ya fue respondido.
            await interaction.followup.defer(ephemeral=False) 
        else:
            # Usamos response.defer para la primera respuesta del botón.
            await interaction.response.defer(ephemeral=False)
    except Exception as e:
        # Si el defer falla por algún motivo (ej: ya se ha respondido más de una vez), 
        # seguimos intentando ejecutar el comando.
        print(f"Advertencia: Falló el defer, intentando invocar de todos modos: {e}")
    
    # 2. Crear un objeto de mensaje simulado
    class SimulatedMessage(discord.Message):
        def __init__(self, interaction, content, author, bot):
            self.id = interaction.message.id if interaction.message else 0 
            self.channel = interaction.channel
            self.guild = interaction.guild
            self.author = author
            self.content = content 
            self.attachments = []
            self.embeds = []
            self.flags = discord.MessageFlags()
            
            # ATRIBUTOS CRÍTICOS PARA discord.py
            self._state = bot._connection 
            self._client = bot # <--- CORRECCIÓN ADICIONAL DEFENSIVA
            
    # Construir el contenido simulado del comando
    simulated_content = f"!{command_name}"
    if args:
        if isinstance(args, list):
            simulated_content += " " + " ".join(map(str, args))
        else:
            simulated_content += f" {args}"
    
    # Crear el objeto de mensaje y contexto
    simulated_message = SimulatedMessage(interaction, simulated_content, interaction.user, bot) 
    ctx = await bot.get_context(simulated_message)
    
    # 3. Invocar el comando
    if not ctx.command:
        # Usamos followup porque response ya fue usada por response.defer()
        await interaction.followup.send(
            f"❌ Error: El comando `!{command_name}` no está cargado o no se pudo invocar.", 
            ephemeral=True
        )
        return

    try:
        # Redirigir ctx.send para que la respuesta vaya a la interacción (públicamente)
        ctx.send = interaction.followup.send
        
        await bot.invoke(ctx)
        
    except commands.CommandOnCooldown as e:
        # Los errores de cooldown se envían de forma efímera
        await interaction.followup.send(
            f"⏰ **¡Espera!** Este comando tiene un tiempo de reutilización. Inténtalo de nuevo en **{e.retry_after:.2f} segundos**.", 
            ephemeral=True
        )
    except Exception as e:
        print(f"Error al ejecutar comando por botón/modal ({command_name}): {e}")
        # En caso de un error inesperado, el usuario ve un mensaje efímero
        await interaction.followup.send(
            f"❌ Ocurrió un error inesperado al ejecutar `!{command_name}`.", 
            ephemeral=True
        )

# ----------------------------
# FIN UTILIDAD
# ----------------------------


# ----------------------------
# MODALES (Ventanas emergentes para inputs)
# ----------------------------

class GachaBuyModal(discord.ui.Modal, title="🛒 Comprar Tiradas de Gacha"):
    """Modal para recoger la cantidad de tiradas a comprar."""
    
    amount = discord.ui.TextInput(
        label="Cantidad de Tiradas",
        placeholder="Introduce un número (Ej: 10)",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Intentar convertir la cantidad a entero
        try:
            quantity = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message("❌ La cantidad debe ser un número entero válido.", ephemeral=True)
            return
            
        # Ejecutar el comando !gacha_comprar con el argumento
        await invoke_command_from_interaction(interaction.client, interaction, "gacha_comprar", args=quantity)


class CardSellModal(discord.ui.Modal, title="💰 Vender Cartas Duplicadas"):
    """Modal para recoger la rareza y cantidad de cartas a vender."""
    
    rarity = discord.ui.TextInput(
        label="Rareza de la Carta (Ej: C, N, R)",
        placeholder="Solo la letra de la rareza (Ej: C, N, R)",
        required=True,
        max_length=3
    )
    
    amount = discord.ui.TextInput(
        label="Cantidad a vender (O 'all')",
        placeholder="Introduce un número o la palabra 'all'",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Ejecutar el comando !vender con los dos argumentos
        rarity_input = self.rarity.value.upper()
        amount_input = self.amount.value.lower()
        
        # Validar la rareza rápidamente (C, N, R, etc.)
        if rarity_input not in ['N', 'R', 'SSR', 'UR', 'SP', 'G']: 
            await interaction.response.send_message("❌ Rareza no reconocida. Usa N, R, SSR, UR, SP o G.", ephemeral=True)
            return

        # El comando !vender debe manejar la lógica de 'all' y la validación numérica
        await invoke_command_from_interaction(interaction.client, interaction, "vender", args=[rarity_input, amount_input])

# ----------------------------
# FIN MODALES
# ----------------------------

# ----------------------------
# SISTEMA DE MENÚ (BOTONES - EJECUTORES Y MODALES)
# ----------------------------

class GachaMenuView(View):
    def __init__(self, author_id, timeout=180):
        super().__init__(timeout=timeout)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo el autor del comando puede usar estos botones.", ephemeral=True)
            return False
        return True

    # --- FILA 1: GACHA Y GANANCIAS ---

    # 🎯 EJECUCIÓN DIRECTA: !gacha
    @discord.ui.button(label="🎲 Tirada Gratis", style=discord.ButtonStyle.green, row=0)
    async def gacha_free_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await invoke_command_from_interaction(interaction.client, interaction, "gacha")

    # 🚀 MODAL: !gacha_comprar
    @discord.ui.button(label="🛒 Comprar Tiradas", style=discord.ButtonStyle.blurple, row=0)
    async def gacha_comprar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Muestra el modal para pedir la cantidad
        await interaction.response.send_modal(GachaBuyModal())

    # 🎯 EJECUCIÓN DIRECTA: !trabajar
    @discord.ui.button(label="💼 Trabajar", style=discord.ButtonStyle.gray, row=0)
    async def trabajar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await invoke_command_from_interaction(interaction.client, interaction, "trabajar")

    # 🎯 EJECUCIÓN DIRECTA: !pesca
    @discord.ui.button(label="🎣 Pesca", style=discord.ButtonStyle.secondary, emoji="🎣", row=0)
    async def pesca_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await invoke_command_from_interaction(interaction.client, interaction, "pesca")


    # --- FILA 2: INVENTARIO Y ECONOMÍA ---
    
    # 🎯 EJECUCIÓN DIRECTA: !diaria
    @discord.ui.button(label="🎁 Diaria", style=discord.ButtonStyle.red, row=1)
    async def daily_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await invoke_command_from_interaction(interaction.client, interaction, "diaria")

    # 🎯 EJECUCIÓN DIRECTA: !inventario
    @discord.ui.button(label="📦 Mi Inventario", style=discord.ButtonStyle.primary, row=1)
    async def inventory_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await invoke_command_from_interaction(interaction.client, interaction, "inventario")
        
    # 🚀 MODAL: !vender
    @discord.ui.button(label="💰 Vender Cartas", style=discord.ButtonStyle.secondary, row=1)
    async def sell_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Muestra el modal para pedir la rareza y cantidad
        await interaction.response.send_modal(CardSellModal())

    # --- FILA 3: SOCIAL Y AYUDA ---

    # ⚠️ PROMPT: !intercambio (Demasiado complejo para modal: requiere @mención)
    @discord.ui.button(label="🤝 Intercambiar", style=discord.ButtonStyle.danger, row=2)
    async def trade_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Usa `!intercambio <@usuario>` para iniciar un intercambio. ¡Este necesita una mención!", ephemeral=True)
        
    # 🎯 EJECUCIÓN DIRECTA: !ayuda
    @discord.ui.button(label="❓ Ayuda y Guía", style=discord.ButtonStyle.primary, row=2)
    async def help_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await invoke_command_from_interaction(interaction.client, interaction, "ayuda")


@bot.command(aliases=['menu', 'gachamenu'])
async def menu_principal(ctx):
    """Muestra el menú principal con botones y modales para acciones básicas."""
    
    try:
        # Asumo que tienes definida la función get_balance
        current_gems = get_balance(ctx.author.id)
        balance_text = f"💎 **{current_gems:,}** gemas"
    except NameError:
        balance_text = "N/A (Error al cargar balance)"
        
    embed = discord.Embed(
        title="🕹️ Menú Rápido: Gacha y Economía",
        description=f"¡Hola, {ctx.author.display_name}! Usa estos botones para interactuar con el bot **sin escribir comandos**.",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="💰 Tu Balance", value=balance_text, inline=False)
    
    embed.add_field(
        name="Tipos de Interacción", 
        value=(
            "**🎯 Ejecución Directa:** Ejecuta el comando inmediatamente.\n"
            "**🚀 Modal:** Abrirá una ventana para introducir datos (Ej: cantidad).\n"
            "**⚠️ Requiere Texto:** Solo te indicará el comando (necesita mención o texto complejo)."
        ), 
        inline=False
    )
    
    embed.set_footer(text=f"Menú solicitado por {ctx.author.display_name}")

    view = GachaMenuView(ctx.author.id)
    await ctx.send(embed=embed, view=view)


# ----------------------------
# COMANDO !PESCA CORREGIDO
# ----------------------------
@bot.command()
async def pesca(ctx):
    """Permite al usuario intentar pescar y ganar gemas."""
    user_id = ctx.author.id
    now = time.time()
    
    # 1. Verificar Cooldown (Lógica idéntica a !casino)
    if user_id in user_last_pesca and now - user_last_pesca[user_id] < COOLDOWN_PESCA:
        time_remaining = COOLDOWN_PESCA - (now - user_last_pesca[user_id])
        await ctx.send(f"❌ ¡Aún no pican! Debes esperar **{format_cooldown(time_remaining)}** para volver a pescar.")
        return

    # IMPORTANTE: Registramos el uso AQUÍ, justo después de la verificación.
    user_last_pesca[user_id] = now  # <--- Registro de Cooldown (COMO EN !CASINO)

    # 2. Inicializar balance del usuario si no existe
    if user_id not in user_balances:
        user_balances[user_id] = 0

    # 3. Lógica de Pesca (30% de Error)
    
    # Simula un pequeño tiempo de espera (para darle emoción)
    message = await ctx.send("🎣 Lanzando la caña... esperando que piquen... (2 segundos)")
    await asyncio.sleep(2)
    
    success_roll = random.random() # Número entre 0.0 y 1.0

    if success_roll < 0.30:  # 30% de probabilidad de fallo
        
        fail_messages = [
            "El pez era demasiado rápido y se escapó. 😭",
            "Tu sedal se rompió. ¡Qué frustración! 💢",
            "Solo sacaste una bota vieja y con algas. 🥾",
            "Un pájaro se llevó tu carnada. 🐦",
            "El río está vacío. Vuelve más tarde.",
        ]
        
        await message.edit(content=f"🎣 ¡Oh no! {random.choice(fail_messages)}")
        
    else: # 70% de probabilidad de éxito
        
        # Recompensa entre 15 y 25 gemas
        winnings = random.randint(15, 25)
        user_balances[user_id] += winnings

        success_messages = [
            f"¡Woooow! Sacaste un **salmón gigante** y ganas **💎 {winnings}**.",
            f"¡Picó! Pescaste una **trucha brillante** y ganas **💎 {winnings}**.",
            f"¡Éxito! Lograste atrapar un **pez dorado** y ganas **💎 {winnings}**.",
            f"Tu caña se dobló. Pescaste algo valioso y ganas **💎 {winnings}**.",
        ]

        await message.edit(content=f"🎉 ¡Felicidades! {random.choice(success_messages)}")
        
    # 4. Guardar Datos (Aseguramos que el balance se guarde)
    # El registro del cooldown ya se hizo arriba, antes de la lógica de pesca.
    save_data()


# ----------------------------
# COMANDO !MINAR
# ----------------------------

@bot.command()
async def minar(ctx):
    """
    Intenta minar gemas. 
    1% de éxito (40 gemas) y 99% de fallo (1 gema), con cooldown de 1 minuto.
    """
    user_id = ctx.author.id
    now = time.time()
    
    # Cooldown de 1 minuto (60 segundos) - Usa la constante definida arriba
    COOLDOWN = COOLDOWN_MINAR 
    
    # 1. Verificar cooldown
    if user_id in user_last_minar and now - user_last_minar[user_id] < COOLDOWN:
        time_remaining = COOLDOWN - (now - user_last_minar[user_id])
        await ctx.send(f"⛏️ **¡Espera!** Debes esperar {format_cooldown(time_remaining)} antes de volver a minar.")
        return

    # Actualizar el tiempo de uso
    user_last_minar[user_id] = now
    
    # 2. Determinar el resultado
    # 1% de probabilidad de éxito (0.01)
    if random.random() <= 0.01:
        # Éxito (1% de probabilidad)
        reward_amount = 40
        
        add_balance(user_id, reward_amount)
        save_data() # Guardar datos
        
        embed = discord.Embed(
            title="💎 ¡ÉXITO! ¡VETA DE CRISTAL RARO!",
            description=f"{ctx.author.mention} ha picado con éxito y encontrado **{format_gems(reward_amount)}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Ganancia", value=f"+ {format_gems(reward_amount)}", inline=True)
        embed.add_field(name="Balance Actual", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo !minar en {format_cooldown(COOLDOWN)}")
        await ctx.send(embed=embed)
        
    else:
        # Fallo (99% de probabilidad)
        reward_amount = 1 # 1 gema por intento fallido
        
        add_balance(user_id, reward_amount)
        save_data() # Guardar datos
        
        fail_messages = [
            "Solo encontraste algo de grava.",
            "La roca estaba muy dura, pero al menos tienes una gema por el esfuerzo.",
            "Tu pico se rompió, pero lograste recuperar una pequeña gema.",
            "No encontraste nada valioso, solo una gema por la suerte."
        ]
        
        embed = discord.Embed(
            title="⛏️ Intento Fallido...",
            description=f"{ctx.author.mention}, {random.choice(fail_messages)}",
            color=discord.Color.red()
        )
        embed.add_field(name="Consuelo", value=f"+ {format_gems(reward_amount)}", inline=True)
        embed.add_field(name="Balance Actual", value=format_gems(get_balance(user_id)), inline=True)
        embed.set_footer(text=f"Próximo !minar en {format_cooldown(COOLDOWN)}")
        await ctx.send(embed=embed)


# ----------------------------
# SISTEMA DE JEFE SEMANAL
# ----------------------------

# Tiempos / cooldowns
COOLDOWN_JEFE_VICTORIA = 7 * 24 * 60 * 60  # 7 días en segundos
COOLDOWN_JEFE_DERROTA = 3 * 60  # 3 minutos en segundos

# Variables globales para el jefe semanal
user_last_jefe = {}  # user_id -> {'timestamp': tiempo, 'resultado': 'victoria'/'derrota'}
user_selections = {}

# Lista de atributos para el jefe
JEFE_ATRIBUTOS = ["Evasion", "Fuerza", "Reacción", "Defensa", "Velocidad", "IQ", "Carisma", "Precisión", "Energia", "Suerte"]

# Diccionario para mapear atributos con/sin acentos
ATRIBUTO_MAP = {
    "Reacción": "Reaccion",
    "Reaccion": "Reacción",
    "Precisión": "Precision", 
    "Precision": "Precisión"
}

# Orden de rareza de mayor a menor
ORDEN_RAREZA = {
    'S': 0,     # Sombra (más rara)
    'E': 1,     # Edición Especial
    'G': 2,
    'SP': 3,
    'UR': 4,
    'SSR': 5,
    'R': 6,
    'N': 7      # Normal (menos rara)
}

def obtener_valor_atributo(card, atributo):
    """Obtiene el valor de un atributo de una carta, manejando diferencias de nombres"""
    stats = card.get("stats", {})
    
    # Intentar con el nombre exacto
    if atributo in stats:
        return stats[atributo]
    
    # Si no está, buscar nombre alternativo
    nombre_alternativo = ATRIBUTO_MAP.get(atributo)
    if nombre_alternativo and nombre_alternativo in stats:
        return stats[nombre_alternativo]
    
    # Si no se encuentra, devolver 1 (valor por defecto)
    return 1

def format_cooldown(seconds):
    """Formatea un tiempo en segundos a una cadena legible."""
    if seconds < 60:
        return f"{int(seconds)} segundos"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds %= 60
        return f"{int(minutes)} minutos y {int(seconds)} segundos"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{int(hours)} horas y {int(minutes)} minutos"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{int(days)} días y {int(hours)} horas"

@bot.command()
async def jefe_semanal(ctx):
    """Desafía al jefe semanal con una de tus cartas. ¡Recompensa: 1000 gemas!"""
    user_id = ctx.author.id
    now = time.time()
    
    # 1. Verificar cooldown
    if user_id in user_last_jefe:
        last_data = user_last_jefe[user_id]
        tiempo_pasado = now - last_data['timestamp']
        
        # Determinar el cooldown según el resultado anterior
        if last_data['resultado'] == 'victoria':
            cooldown_necesario = COOLDOWN_JEFE_VICTORIA
        else:  # derrota
            cooldown_necesario = COOLDOWN_JEFE_DERROTA
        
        if tiempo_pasado < cooldown_necesario:
            tiempo_restante = cooldown_necesario - tiempo_pasado
            await ctx.send(f"⏳ **¡Debes esperar!** Ya has desafiado al jefe semanal recientemente.\n"
                          f"Vuelve a intentarlo en **{format_cooldown(tiempo_restante)}**.")
            return
    
    # 2. Verificar que el usuario tenga cartas
    inventory = get_inventory(user_id)
    if not inventory:
        await ctx.send("❌ **No tienes cartas** para enfrentar al jefe semanal.\n"
                      "Usa `!gacha` para obtener cartas primero.")
        return
    
    # 3. ORDENAR CARTAS POR RAREZA (de más rara a menos rara)
    for card in inventory:
        if 'rareza' not in card:
            card['rareza'] = 'N'
    
    inventory_ordenado = sorted(
        inventory,
        key=lambda x: ORDEN_RAREZA.get(x['rareza'], 8)
    )
    
    # 4. Mensaje de introducción
    intro_embed = discord.Embed(
        title="👑 HAS DECIDIDO DESAFIAR A AQUEL QUE SE ALZA POR ENCIMA DE TODAS LAS RAZAS",
        description=(
            "Un silencio sepulcral desciende sobre el campo de batalla. "
            "El aire se espesa con una energía ancestral mientras una figura monumental emerge de las sombras.\n\n"
            "**『Yo soy el equilibrio, el juicio final, la prueba definitiva.』**\n"
            "**『Mi poder trasciende lo concebible... excepto en un único aspecto.』**\n\n"
            "¿Serás capaz de descubrir su debilidad y reclamar la gloria eterna?"
        ),
        color=discord.Color.dark_purple()
    )
    intro_embed.set_footer(text="Tienes 2 minutos para seleccionar tu carta")
    
    await ctx.send(embed=intro_embed)
    
    # 5. Generar jefe con debilidad aleatoria (pero no mostrarla aún)
    debilidad = random.choice(JEFE_ATRIBUTOS)
    jefe_stats = {atributo: 99 for atributo in JEFE_ATRIBUTOS}
    jefe_stats[debilidad] = 1
    
    # 6. Mostrar lista de cartas ordenadas por rareza
    lista_cartas = "**Tus cartas (ordenadas por rareza):**\n"
    for i, card in enumerate(inventory_ordenado[:25]):
        nombre = card['nombre']
        rareza = card.get('rareza', 'N')
        
        emoji_rareza = {
            'S': '👻',
            'E': '🎃',
            'G': '💎',
            'SP': '✨',
            'UR': '🔥',
            'SSR': '⭐',
            'R': '🔹',
            'N': '⚪'
        }.get(rareza, '⚪')
        
        nombre_display = nombre
        if len(nombre) > 20:
            nombre_display = nombre[:17] + "..."
        
        lista_cartas += f"**{i+1}.** {emoji_rareza} **{nombre_display}** ({rareza})\n"
    
    if len(inventory_ordenado) > 25:
        lista_cartas += f"\n*(Mostrando 25 de {len(inventory_ordenado)} cartas)*"
    
    # 7. Crear embed principal SIN mostrar stats del jefe
    embed = discord.Embed(
        title="⚔️ ELECCIÓN DE LA CARTA LEGENDARIA",
        description=(
            f"{lista_cartas}\n\n"
            f"**{ctx.author.display_name}**, para seleccionar una carta, usa:\n"
            f"```!eleccion_jefe <número>```\n"
            f"**Ejemplo:** `!eleccion_jefe 1` para seleccionar la primera carta\n\n"
            f"**El jefe tiene una debilidad oculta, pero la batalla se decidirá por una estadística aleatoria.**\n"
            f"**Recompensa por victoria:** {format_gems(1000)}\n\n"
            f"**Cancelar desafío:** `!cancelar_jefe`"
        ),
        color=discord.Color.dark_gold()
    )
    
    embed.set_footer(text="Tienes 2 minutos para seleccionar tu carta")
    
    await ctx.send(embed=embed)
    
    # 8. Guardar información para procesar la elección
    user_selections[user_id] = {
        'inventory': inventory_ordenado,
        'jefe_stats': jefe_stats,
        'jefe_debilidad': debilidad,
        'timestamp': now,
        'channel_id': ctx.channel.id
    }

@bot.command()
async def eleccion_jefe(ctx, numero_carta: int):
    """Selecciona una carta para enfrentar al jefe semanal"""
    user_id = ctx.author.id
    
    # Verificar que el usuario tenga una selección activa
    if user_id not in user_selections:
        await ctx.send("❌ No tienes un desafío activo al jefe semanal. Usa `!jefe_semanal` primero.")
        return
    
    selection_data = user_selections[user_id]
    
    # Verificar que el canal sea el correcto
    if selection_data['channel_id'] != ctx.channel.id:
        await ctx.send(f"❌ Debes seleccionar tu carta en el mismo canal donde iniciaste el desafío.")
        return
    
    # Verificar tiempo (2 minutos)
    if time.time() - selection_data['timestamp'] > 120:
        await ctx.send("⏰ ¡Tiempo agotado! El desafío al jefe semanal ha expirado.")
        del user_selections[user_id]
        return
    
    inventory_ordenado = selection_data['inventory']
    jefe_stats = selection_data['jefe_stats']
    debilidad = selection_data['jefe_debilidad']
    
    # Verificar que el número sea válido
    if numero_carta < 1 or numero_carta > len(inventory_ordenado):
        await ctx.send(f"❌ Número inválido. Debes seleccionar un número entre 1 y {len(inventory_ordenado)}.")
        return
    
    # Obtener la carta seleccionada
    selected_card = inventory_ordenado[numero_carta - 1]
    
    # 1. PRIMERO: Elegir una stat ALEATORIA para la batalla (no siempre la débil)
    stat_batalla = random.choice(JEFE_ATRIBUTOS)
    
    # 2. Obtener valores para la comparación
    valor_jefe = jefe_stats[stat_batalla]  # Puede ser 99 o 1 (si coincide con la debilidad)
    valor_carta = obtener_valor_atributo(selected_card, stat_batalla)
    
    # 3. Comparación: El jugador gana si su carta tiene MÁS puntos en esa stat
    gana = valor_carta > valor_jefe
    
    # Limpiar la selección
    del user_selections[user_id]
    
    # Crear embed de comparación
    stats_jefe_str = "\n".join([f"• {atributo}: {valor}" for atributo, valor in jefe_stats.items()])
    
    embed_comparacion = discord.Embed(
        title="⚔️ COMPARACIÓN DE ESTADÍSTICAS",
        description=(
            f"**Jefe Semanal - Estadísticas:**\n"
            f"```\n{stats_jefe_str}\n```\n"
            f"**Debilidad del jefe:** **{debilidad}** (valor: 1)\n"
            f"**Stat de batalla (ALEATORIA):** **{stat_batalla}**\n"
            f"**Valor del jefe en {stat_batalla}:** {valor_jefe}\n\n"
            f"**Tu carta - {selected_card['nombre']} ({selected_card.get('rareza', 'N')})**\n"
            f"**Tu valor en {stat_batalla}:** {valor_carta}\n\n"
        ),
        color=discord.Color.blue()
    )
    
    await ctx.send(embed=embed_comparacion)
    
    # 4. Determinar resultado y aplicar cooldown correspondiente
    if gana:
        # VICTORIA - Cooldown: 1 semana
        recompensa = 1000
        add_balance(user_id, recompensa)
        
        embed_victoria = discord.Embed(
            title="🎉 ¡VICTORIA CONTRA EL JEFE SEMANAL!",
            description=(
                f"**{ctx.author.mention} ha derrotado al jefe supremo!**\n\n"
                f"Tu carta **{selected_card['nombre']}** ({selected_card.get('rareza', 'N')}) "
                f"superó al jefe en **{stat_batalla}** ({valor_carta} > {valor_jefe}).\n\n"
                f"**¡Recompensa obtenida: {format_gems(recompensa)}!**\n"
                f"Nuevo balance: {format_gems(get_balance(user_id))}\n\n"
                f"**Cooldown hasta el próximo desafío: 7 días**"
            ),
            color=discord.Color.gold()
        )
        
        # Intentar mostrar la imagen de la carta si está disponible
        try:
            if "imagen" in selected_card and selected_card["imagen"]:
                embed_victoria.set_thumbnail(url=selected_card["imagen"])
        except:
            pass
        
        await ctx.send(embed=embed_victoria)
        
        # Guardar resultado con timestamp y cooldown
        user_last_jefe[user_id] = {
            'timestamp': time.time(),
            'resultado': 'victoria'
        }
        
    else:
        # DERROTA - Cooldown: 3 minutos
        embed_derrota = discord.Embed(
            title="💀 Derrota ante el Jefe Semanal",
            description=(
                f"**{ctx.author.mention} ha sido derrotado...**\n\n"
                f"Tu carta **{selected_card['nombre']}** ({selected_card.get('rareza', 'N')}) "
                f"no pudo superar al jefe en **{stat_batalla}** ({valor_carta} <= {valor_jefe}).\n\n"
                f"El jefe semanal permanece invicto. ¡Vuelve a intentarlo en **3 minutos**!"
            ),
            color=discord.Color.dark_red()
        )
        
        await ctx.send(embed=embed_derrota)
        
        # Guardar resultado con timestamp y cooldown
        user_last_jefe[user_id] = {
            'timestamp': time.time(),
            'resultado': 'derrota'
        }

@bot.command()
async def cancelar_jefe(ctx):
    """Cancela el desafío al jefe semanal"""
    user_id = ctx.author.id
    
    if user_id in user_selections:
        del user_selections[user_id]
        embed = discord.Embed(
            title="❌ Desafío Cancelado",
            description="Has cancelado el desafío al jefe semanal.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ No tienes un desafío activo al jefe semanal.")

# ----------------------------
# EVENTO DE INICIO
# ----------------------------
@bot.event
async def on_ready():
    print(f'✅ {bot.user} está listo!')
    print(f'🎮 Comandos cargados: ayuda, gacha, gacha_comprar, trabajar, inventario, vender, intercambio, diaria, adivina, rob, cancelar_intercambio, espera (cd), casino, pesca')
    print(f'👑 Comandos de admin: givegems, removegems, clear_inventory, remove_card, givecard, reset_data, clear, interfaz')

# ----------------------------
# Arrancar el bot (no compartas tu token)
# ----------------------------
if __name__ == "__main__":
    import config  # asegúrate de que en config.py está DISCORD_TOKEN
    bot.run(config.DISCORD_TOKEN)