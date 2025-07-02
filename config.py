# config.py

# --- CONFIGURAÇÕES DE GAME DESIGN ---
XP_PER_LEVEL_BASE = 150
XP_PER_MESSAGE_COOLDOWN_SECONDS = 60
ATTRIBUTE_POINTS_PER_LEVEL = 2
CRITICAL_CHANCE = 0.10
CRITICAL_MULTIPLIER = 1.5
INITIAL_MONEY = 100
INITIAL_HP = 100
INITIAL_ATTACK = 10
INITIAL_SPECIAL_ATTACK = 20
REVIVE_COST = 55
BOUNTY_PERCENTAGE = 0.20
TRANSFORM_COST = 2
MAX_ENERGY = 10
STARTING_LOCATION = "Abrigo dos Foras-da-Lei"


CUSTOM_EMOJIS = {
    "espada_rpg": "<:espada_rpg:123456789012345678>",  # Substitua pelo ID real
    "moeda_ouro": "<:moeda_ouro:987654321098765432>",  # Substitua pelo ID real
    "vida_hp": "<:vida_hp:112233445566778899>",  # Substitua pelo ID real
    "transform": "<a:aura:1389688598139371631>",
    "machado_guerreiro": "<:machado_guerreiro:123123123123123123>",  # Exemplo
    "escudo_defesa": "<:escudo_defesa:456456456456456456>",  # Exemplo
    "xp_estrela": "<:xp_estrela:789789789789789789>",  # Exemplo para XP
    "olho_secreto": "<:olho_secreto:123456789012345678>",  # Exemplo para sneaks
    "ferramentas_dev": "<:ferramentas_dev:987654321098765432>",  # Outro exemplo para sneaks
}


# --- DADOS GLOBAIS DO JOGO ---
ITEMS_DATA = {
    "pocao": {"name": "Poção de Vida", "heal": 50, "price": 75, "emoji": "🧪"},
    "super_pocao": {"name": "Super Poção", "heal": 120, "price": 150, "emoji": "🍶"},
    "invocador": {"name": "Invocador do Colosso", "price": 1000, "emoji": "🔮"},
    "amuleto_de_pedra": {
        "name": "Amuleto de Pedra",
        "effect": "second_chance",
        "emoji": "🪨",
    },
    "cajado_curandeiro": {
        "name": "Cajado do Curandeiro",
        "price": 5000,
        "class_restriction": "Curandeiro",
        "effect_multiplier": 1.20,
        "emoji": "⚕️",
    },
    "manopla_lutador": {
        "name": "Manopla do Lutador",
        "price": 5000,
        "class_restriction": "Lutador",
        "attack_bonus_percent": 0.05,
        "hp_bonus_flat": 20,
        "emoji": "🥊",
    },
    "mira_semi_automatica": {
        "name": "Mira Semi-Automática",
        "price": 5000,
        "class_restriction": "Atirador",
        "cooldown_reduction_percent": 0.40,
        "emoji": "🎯",
    },
    "espada_fantasma": {
        "name": "Espada Fantasma",
        "price": 5000,
        "class_restriction": "Espadachim",
        "attack_bonus_percent": 0.10,
        "hp_penalty_percent": 0.20,
        "emoji": "🗡️",
    },
    "habilidade_inata": {
        "xp_multiplier_passive": 0.10,
        "attack_bonus_passive_percent": 0.05,
    },
    "bencao_dracula": {
        "name": "Bênção de Drácula",
        "price": 1000,
        "class_restriction": "Vampiro",
        "cost_energy": 3,
        "duration_seconds": 5 * 60,
        "evasion_chance": 0.15,
        "hp_steal_percent_on_evade": 0.25,
        "emoji": "🦇",
    },
    "bencao_rei_henrique": {
        "name": "Benção do Rei Henrique",
        "price": 1000,
        "style_restriction": "Aura",
        "cost_energy": 5,
        "duration_seconds": 10 * 60,
        "attack_multiplier": 1.20,
        "special_attack_multiplier": 1.20,
        "max_hp_multiplier": 1.20,
        "cooldown_reduction_percent": 0.10,
        "emoji": "✨",
    },
}

# New dictionary for class transformations
CLASS_TRANSFORMATIONS = {
    "Espadachim": {
        "Lâmina Fantasma": {
            "emoji": "👻",
            "cost_energy": TRANSFORM_COST,
            "duration_seconds": 5 * 60,  # 5 minutes
            "attack_multiplier": 1.20,
            "special_attack_multiplier": 1.10,
            "hp_multiplier": 0.90,  # Penalty
        },
        "Lâmina Abençoada": {  # NEW BLESSED FORM
            "emoji": "🌟👻",
            "cost_energy": TRANSFORM_COST + 2,  # Higher cost
            "duration_seconds": 7 * 60,  # Longer duration
            "attack_multiplier": 1.30,
            "special_attack_multiplier": 1.20,
            "hp_multiplier": 0.95,
            "required_blessing": "bencao_rei_henrique",  # Requires Aura Blessing
        },
    },
    "Lutador": {
        "Punho de Aço": {
            "emoji": "💪",
            "cost_energy": TRANSFORM_COST,
            "duration_seconds": 5 * 60,  # 5 minutes
            "attack_multiplier": 1.15,
            "hp_multiplier": 1.15,
        },
        "Punho de Adamantium": {  # NEW BLESSED FORM
            "emoji": "💎💪",
            "cost_energy": TRANSFORM_COST + 2,
            "duration_seconds": 7 * 60,
            "attack_multiplier": 1.25,
            "hp_multiplier": 1.25,
            "required_blessing": "bencao_rei_henrique",
        },
    },
    "Atirador": {
        "Olho de Águia": {
            "emoji": "🦅",
            "cost_energy": TRANSFORM_COST,
            "duration_seconds": 5 * 60,  # 5 minutes
            "attack_multiplier": 1.05,
            "special_attack_multiplier": 1.25,
            "cooldown_reduction_percent": 0.20,  # Cooldown for special attacks
        },
        "Visão Cósmica": {  # NEW BLESSED FORM
            "emoji": "👁️‍🗨️🦅",
            "cost_energy": TRANSFORM_COST + 2,
            "duration_seconds": 7 * 60,
            "attack_multiplier": 1.10,
            "special_attack_multiplier": 1.35,
            "cooldown_reduction_percent": 0.30,
            "required_blessing": "bencao_rei_henrique",
        },
    },
    "Curandeiro": {
        "Bênção Vital": {
            "emoji": "😇",
            "cost_energy": TRANSFORM_COST,
            "duration_seconds": 5 * 60,  # 5 minutes
            "healing_multiplier": 1.25,
            "hp_multiplier": 1.10,
        },
        "Toque Divino": {  # NEW BLESSED FORM
            "emoji": "✨😇",
            "cost_energy": TRANSFORM_COST + 2,
            "duration_seconds": 7 * 60,
            "healing_multiplier": 1.35,
            "hp_multiplier": 1.20,
            "required_blessing": "bencao_rei_henrique",
        },
    },
    "Vampiro": {
        "Lorde Sanguinário": {
            "emoji": "🧛",
            "cost_energy": TRANSFORM_COST,
            "duration_seconds": 5 * 60,  # 5 minutes
            "attack_multiplier": 1.80,
            "special_attack_multiplier": 2.00,
        },
        "Rei da Noite": {  # NEW BLESSED FORM
            # CORREÇÃO AQUI: Use o CUSTOM_EMOJIS.get() como o VALOR da chave "emoji"
            "emoji": CUSTOM_EMOJIS.get(
                "transform", "✨"
            ),  # Use o emoji de transformação, com fallback para '✨'
            # OU se você quiser manter o "👑🧛" E adicionar outro emoji:
            # "emoji": "👑🧛",
            # "outro_emoji_da_transformacao": CUSTOM_EMOJIS.get("transform", "✨"),
            # Mas pelo erro, parece que essa linha foi copiada de forma indevida.
            # O mais provável é que a intenção fosse USAR o emoji de 'transform' aqui.
            "cost_energy": TRANSFORM_COST + 2,
            "duration_seconds": 7 * 60,
            "attack_multiplier": 1.90,
            "special_attack_multiplier": 2.20,
            "evasion_chance_bonus": 0.05,  # Small bonus to evasion
            "required_blessing": "bencao_rei_henrique",
        },
    },
}


BOSS_DATA = {
    "name": "Colosso de Pedra",
    "hp": 0,
    "max_hp": 5000,
    "attack": 150,
    "is_active": False,
    "participants": [],
    "channel_id": None,
    "drops": {"amuleto_de_pedra": 1},
}

WORLD_MAP = {
    "Abrigo dos Foras-da-Lei": {
        "type": "cidade",
        "emoji": "⛺",
        "conecta": ["Floresta Sussurrante"],
        "desc": "Um acampamento improvisado que serve de refúgio para os renegados.",
    },
    "Floresta Sussurrante": {
        "type": "selvagem",
        "emoji": "🌳",
        "conecta": ["Abrigo dos Foras-da-Lei", "Ruínas do Templo"],
        "desc": "Uma mata densa e perigosa, onde criaturas espreitam nas sombras.",
    },
    "Ruínas do Templo": {
        "type": "selvagem",
        "emoji": "🏛️",
        "conecta": ["Floresta Sussurrante"],
        "desc": "Os restos de um antigo local de poder, agora habitado por guardiões de pedra.",
    },
}

ENEMIES = {
    "Floresta Sussurrante": [
        {
            "name": "Lobo Faminto",
            "hp": 60,
            "attack": 12,
            "xp": 25,
            "money": 15,
            "thumb": "https://c.tenor.com/v5Ik3wkrjlwAAAAC/tenor.gif",
        },
        {
            "name": "Aranha Gigante",
            "hp": 50,
            "attack": 15,
            "xp": 30,
            "money": 20,
            "thumb": "https://c.tenor.com/cBKUDbUVHSAAAAAC/tenor.gif",
        },
        {
            "name": "Dragão de Komodo",
            "hp": 70,
            "attack": 10,
            "xp": 28,
            "money": 18,
            "thumb": "https://c.tenor.com/gIzmfcS1-rcAAAAC/tenor.gif",
        },
    ],
    "Ruínas do Templo": [
        {
            "name": "Guardião de Pedra",
            "hp": 400,
            "attack": 38,
            "xp": 260,
            "money": 200,
            "thumb": "https://c.tenor.com/NLQ2AoVfEQUAAAAd/tenor.gif",
        },
        {
            "name": "Espectro Antigo",
            "hp": 90,
            "attack": 102,
            "xp": 80,
            "money": 160,
            "thumb": "https://c.tenor.com/tTXMqhKPCFwAAAAd/tenor.gif",
        },
        {
            "name": "Gárgula Vingativa",
            "hp": 220,
            "attack": 50,
            "xp": 65,
            "money": 165,
            "thumb": "https://c.tenor.com/Ub7Nd2q36RYAAAAd/tenor.gif",
        },
    ],
}


PROFILE_IMAGES = {
    # Imagens das Classes Base
    "Espadachim": "https://i.imgur.com/RC3rJNc.png",
    "Lutador": "https://media.discordapp.net/attachments/1388860166648369184/1389495865567084605/Picsart_25-07-01_03-17-21-028.png?ex=6864d45d&is=686382dd&hm=73f2f3896118d1901ec30b0c8b7ef6739d400e6f06294d98891698e4f16622b6&=&format=webp&quality=lossless&width=608&height=608",
    "Atirador": "https://media.tenor.com/hYzJPjRmvWAAAAAM/clown.gif",  # Placeholder - Consider finding a more suitable image
    "Curandeiro": "https://media.tenor.com/hYzJPjRmvWAAAAAM/clown.gif",  # Placeholder - Consider finding a more suitable image
    "Vampiro": "https://i.imgur.com/X0E6qQL.png",
    # Imagens das Transformações (precisam corresponder EXATAMENTE ao "name" em CLASS_TRANSFORMATIONS)
    "Lâmina Fantasma": "https://i.imgur.com/CnDR7eP.png",
    "Punho de Aço": "https://i.imgur.com/mDsfNyi.png",
    "Olho de Águia": "https://media.tenor.com/hYzJPjRmvWAAAAAM/clown.gifI",  # Placeholder - Consider finding a more suitable image
    "Bênção Vital": "https://media.tenor.com/hYzJPjRmvWAAAAAM/clown.gif",  # Placeholder - Consider finding a more suitable image
    "Lorde Sanguinário": "https://i.imgur.com/eTaWLjx.png",
    # Bônus: Imagem para a Bênção da Aura
    "Benção do Rei Henrique": "https://media.tenor.com/hYzJPjRmvWAAAAAM/clown.gifI",  # Placeholder - Consider finding a more suitable image
    # NOVAS IMAGENS PARA AS FORMAS ABENÇOADAS (PLACEHOLDERS)
    "Lâmina Abençoada": "https://example.com/blade_blessed.png",  # **IMPORTANT: Replace with your actual image URL**
    "Punho de Adamantium": "https://example.com/adamantium_fist.png",  # **IMPORTANT: Replace with your actual image URL**
    "Visão Cósmica": "https://example.com/cosmic_sight.png",  # **IMPORTANT: Replace with your actual image URL**
    "Toque Divino": "https://example.com/divine_touch.png",  # **IMPORTANT: Replace with your actual image URL**
    "Rei da Noite": "https://example.com/night_king.png",  # **IMPORTANT: Replace with your actual image URL**
}


LEVEL_ROLES = {
    2: 1389604381069938738,
    5: 1389604398103269376,
    10: 1389604405078134894,
    20: 1389604420702048417,
    35: 1389604431317827604,
    50: 1389604749233487923,
}

NEW_CHARACTER_ROLE_ID = 1388628499182518352
