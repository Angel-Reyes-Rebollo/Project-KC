# cards_catalog.py

cards = {
    "E": {  # Evento (0%, solo admin)
        "prob": 0.0,
        "list": [
            {"name": "Dragón del Festival", "rarity": "E", "image": "url_evento.png"}
        ]
    },
    "M": {  # Mítico 0.1%
        "prob": 0.001,
        "list": [
            {"name": "Fénix Eterno", "rarity": "M", "image": "url_mitico.png"}
        ]
    },
    "L": {  # Leyenda 0.2%
        "prob": 0.002,
        "list": [
            {"name": "Caballero de la Luz", "rarity": "L", "image": "url_leyenda.png"}
        ]
    },
    "F": {  # Fun 1%
        "prob": 0.01,
        "list": [
            {"name": "Patito Cósmico", "rarity": "F", "image": "url_fun.png"}
        ]
    },
    "SP": {  # Special 1.5%
        "prob": 0.015,
        "list": [
            {"name": "Espada Celestial", "rarity": "SP", "image": "url_special.png"}
        ]
    },
    "UR": {  # Ultra Raro 2%
        "prob": 0.02,
        "list": [
            {"name": "Bestia Carmesí", "rarity": "UR", "image": "url_ur.png"}
        ]
    },
    "SSR": {  # Super Super Raro 3%
        "prob": 0.03,
        "list": [
            {"name": "Dragón Marino", "rarity": "SSR", "image": "url_ssr.png"}
        ]
    },
    "SR": {  # Super Raro 6%
        "prob": 0.06,
        "list": [
            {"name": "Mago del Relámpago", "rarity": "SR", "image": "url_sr.png"}
        ]
    },
    "N": {  # Normal 26.2%
        "prob": 0.262,
        "list": [
            {"name": "Guerrero Novato", "rarity": "N", "image": "url_normal.png"}
        ]
    }
}
