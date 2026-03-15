# config.py — Variables de configuración del bot
# NO subas este archivo a GitHub (agrega config.py al .gitignore)
# En Railway/Render, usa variables de entorno en lugar de este archivo.

import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "MTQzNzY1NTQ4MjY4Nzk0NjgzMw.GmlUW2.UN5ogleo8XLYqgLYlcwFrZoNb3r0pC_5lQk5lc")

# Para el sistema de backup a GitHub (opcional)
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "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")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "tu_usuario/tu_repo")  # Ej: "juan/bot-gacha"
BACKUP_BRANCH = os.getenv("BACKUP_BRANCH", "backup-data")
