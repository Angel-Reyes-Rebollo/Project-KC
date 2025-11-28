import json
import os
import time
from datetime import datetime

# Intentar importar Flask
try:
    from flask import Flask, jsonify
    FLASK_AVAILABLE = True
    print("✅ Flask está disponible - Servidor web ACTIVADO")
except ImportError:
    FLASK_AVAILABLE = False
    print("⚠️  Flask no disponible - Servidor web DESACTIVADO")

# Variables globales (se llenarán desde el bot principal)
user_inventories = {}
user_balances = {}
catalog_cards = []
cards_catalog = {}
pending_trades = {}
user_last_trabajar = {}
user_last_daily = {}
user_last_gacha = {}
user_last_adivina = {}
user_last_rob = {}
user_rob_penalties = {}

# Crear app solo si Flask está disponible
if FLASK_AVAILABLE:
    app = Flask(__name__)
else:
    app = None

class BotStatus:
    def __init__(self):
        self.start_time = time.time()
        self.active_trades = 0
        self.last_update = datetime.now()
        self.status = "online" if FLASK_AVAILABLE else "offline"

    def update_stats(self):
        try:
            self.active_trades = len(pending_trades)
            self.last_update = datetime.now()
        except Exception:
            self.active_trades = 0

bot_status = BotStatus()

def get_uptime():
    """Calcular el tiempo de actividad del servidor"""
    uptime_seconds = int(time.time() - bot_status.start_time)
    
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

# Solo definir rutas si Flask está disponible
if FLASK_AVAILABLE:
    @app.route('/')
    def index():
        """Página principal del dashboard"""
        bot_status.update_stats()
        
        stats = {
            'total_users': len(user_balances),
            'total_cards': len(catalog_cards),
            'active_trades': bot_status.active_trades,
            'uptime': get_uptime(),
            'last_update': bot_status.last_update.strftime('%Y-%m-%d %H:%M:%S'),
            'status': bot_status.status
        }
        
        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Project-KC APP - Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #1e1e1e; color: white; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: #7289da; padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .stat-card {{ background: #2c2f33; padding: 25px; border-radius: 10px; text-align: center; border-left: 4px solid #7289da; }}
                .stat-number {{ font-size: 2.5em; font-weight: bold; color: #7289da; margin: 10px 0; }}
                .stat-label {{ color: #b9bbbe; font-size: 1.1em; }}
                .section {{ background: #2c2f33; padding: 25px; border-radius: 10px; margin-bottom: 25px; }}
                .api-list {{ list-style: none; padding: 0; }}
                .api-list li {{ margin: 15px 0; padding: 10px; background: #40444b; border-radius: 5px; }}
                .api-list a {{ color: #7289da; text-decoration: none; font-weight: bold; }}
                .status-online {{ color: #43b581; }}
                .last-update {{ color: #72767d; font-style: italic; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎮 Project-KC APP Dashboard</h1>
                    <p>Bot de cartas de Haikyuu!! - Estado en tiempo real</p>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_users']}</div>
                        <div class="stat-label">👥 Usuarios Registrados</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_cards']}</div>
                        <div class="stat-label">🃏 Cartas en Catálogo</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['active_trades']}</div>
                        <div class="stat-label">🔄 Intercambios Activos</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['uptime']}</div>
                        <div class="stat-label">⏰ Tiempo Activo</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📊 Estado del Sistema</h2>
                    <p><strong>Status:</strong> <span class="status-online">● {stats['status']}</span></p>
                    <p class="last-update">Última actualización: {stats['last_update']}</p>
                </div>
                
                <div class="section">
                    <h2>🔗 APIs Disponibles</h2>
                    <ul class="api-list">
                        <li>📊 <a href="/api/stats" target="_blank">/api/stats</a> - Estadísticas generales del bot</li>
                        <li>👥 <a href="/api/users" target="_blank">/api/users</a> - Lista de usuarios y balances</li>
                        <li>🃏 <a href="/api/cards" target="_blank">/api/cards</a> - Estadísticas de cartas por rareza</li>
                        <li>🔄 <a href="/api/trades" target="_blank">/api/trades</a> - Intercambios pendientes</li>
                        <li>❤️ <a href="/health" target="_blank">/health</a> - Estado de salud del servidor</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

    @app.route('/api/stats')
    def api_stats():
        """API para obtener estadísticas en JSON"""
        bot_status.update_stats()
        
        stats = {
            'status': 'online',
            'uptime': get_uptime(),
            'total_users': len(user_balances),
            'total_cards': len(catalog_cards),
            'active_trades': bot_status.active_trades,
            'total_inventories': len(user_inventories),
            'server_time': datetime.now().isoformat(),
            'deployment': 'render'
        }
        
        return jsonify(stats)

    @app.route('/api/users')
    def api_users():
        """API para obtener lista de usuarios"""
        users_data = []
        
        for user_id, balance in user_balances.items():
            inventory_count = len(user_inventories.get(user_id, []))
            users_data.append({
                'user_id': user_id,
                'balance': balance,
                'cards_count': inventory_count
            })
        
        users_data.sort(key=lambda x: x['balance'], reverse=True)
        
        return jsonify(users_data)

    @app.route('/api/cards')
    def api_cards():
        """API para obtener estadísticas de cartas"""
        rarity_stats = {}
        
        for rarity, cards in cards_catalog.items():
            total_cards = len(catalog_cards) if catalog_cards else 1
            percentage = (len(cards) / total_cards * 100) if total_cards > 0 else 0
            rarity_stats[rarity] = {
                'count': len(cards),
                'percentage': f"{percentage:.1f}%"
            }
        
        cards_data = {
            'total_cards': len(catalog_cards),
            'rarity_distribution': rarity_stats,
            'deployment': 'render'
        }
        
        return jsonify(cards_data)

    @app.route('/api/trades')
    def api_trades():
        """API para obtener intercambios pendientes"""
        trades_data = []
        
        for trade_id, trade_info in pending_trades.items():
            trade_data = {
                'trade_id': trade_id,
                'user1_cards_count': len(trade_info.get('user1_cards', [])),
                'user2_cards_count': len(trade_info.get('user2_cards', [])),
                'created_at': trade_info.get('created_at', 0)
            }
            trades_data.append(trade_data)
        
        return jsonify(trades_data)

    @app.route('/health')
    def health_check():
        """Endpoint de salud del servidor"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'Project-KC-bot',
            'deployment': 'render',
            'version': '1.0.0'
        })

def run_webserver():
    """Ejecutar el servidor web"""
    if not FLASK_AVAILABLE:
        print("❌ Flask no disponible - No se puede iniciar servidor web")
        return False
    
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"🌐 Iniciando servidor web en http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        return True
    except Exception as e:
        print(f"❌ Error al iniciar servidor web: {e}")
        return False

def start_webserver():
    """Iniciar el servidor web en segundo plano"""
    if not FLASK_AVAILABLE:
        return False
    
    import threading
    try:
        server_thread = threading.Thread(target=run_webserver, daemon=True)
        server_thread.start()
        return True
    except Exception as e:
        print(f"❌ Error al iniciar servidor web: {e}")
        return False

# Para Render
if __name__ == '__main__':
    run_webserver()