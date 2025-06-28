# config.py

import discord
import os

# --- CONFIGURAÇÕES GERAIS ---
# O token é carregado de forma segura a partir das variáveis de ambiente (arquivo .env)
TOKEN = os.getenv("DISCORD_TOKEN")

# Verificação para garantir que o token foi carregado
if TOKEN is None:
    raise ValueError(
        "Erro: O DISCORD_TOKEN não foi encontrado. Verifique seu arquivo .env"
    )

PREFIXO = "/"
DONO_ID = 123456789
STATUS_BOT = discord.Game(name="outlaw-rpg.com | /ficha")
COR_EMBED_PADRAO = 0x2B2D31
COR_EMBED_SUCESSO = 0x57F287
COR_EMBED_ERRO = 0xED4245
COR_EMBED_AVISO = 0x0FEE75C
COR_EMBED_CHEFE = 0x992D22

# --- ARQUIVOS DE DADOS ---
FICHAS_DB_FILE = "data/fichas.json"
GIFS_DB_FILE = "data/gifs.json"
BOSS_DB_FILE = "data/boss_data.json"

# --- CONSTANTES DE JOGO ---
ENERGIA_MAXIMA = 100
REGEN_ENERGIA = 5
MOEDA_NOME = "Dólar"
MOEDA_EMOJI = "💵"

# --- COOLDOWNS (em segundos) ---
COOLDOWN_TRABALHAR = 3600
COOLDOWN_CRIME = 1800
COOLDOWN_CACAR = 300
COOLDOWN_BATALHAR = 600
COOLDOWN_REVIVER = 120
COOLDOWN_AFK = 10800  # 3 horas
COOLDOWN_DAILY = 86400  # 24 horas

# --- RECOMPENSAS E CUSTOS ---
CUSTO_REVIVER = 150
RECOMPENSA_DAILY_DINHEIRO = 500
RECOMPENSA_DAILY_XP = 250
BOUNTY_BASE = 200
BOUNTY_PERCENTUAL_VITIMA = 0.1  # 10% do dinheiro da vítima

# --- SISTEMA DE APRIMORAMENTO ---
APRIMORAMENTO_CUSTO_BASE_ATK = 500
APRIMORAMENTO_CUSTO_MULTIPLICADOR_ATK = 1.5
APRIMORAMENTO_CUSTO_BASE_DEF = 400
APRIMORAMENTO_CUSTO_MULTIPLICADOR_DEF = 1.6
APRIMORAMENTO_MAX_LEVEL = 20


# --- NÍVEIS E XP ---
def xp_para_level_up(level):
    return 5 * (level**2) + (50 * level) + 100


# --- ESTILOS DE LUTA (HABILIDADES) ---
HABILIDADES = {
    "Lutador (Mãos)": {
        "stats_base": {"hp": 110, "atk": 12, "defesa": 8},
        "emoji": "🥊",
    },
    "Espadachim (Espadas)": {
        "stats_base": {"hp": 100, "atk": 10, "defesa": 10},
        "emoji": "⚔️",
    },
    "Atirador (Armas de Fogo)": {
        "stats_base": {"hp": 90, "atk": 15, "defesa": 6},
        "emoji": "🔫",
    },
}

# --- LOJA DE ITENS ---
# Ponto de Atenção: O erro no seu log mencionava 'LOJA_ITENS', mas a variável aqui é 'ITENS_LOJA'.
# Garanta que todos os seus arquivos (como cogs/items.py) importem 'ITENS_LOJA' para manter o padrão.
ITENS_LOJA = {
    "consumiveis": {
        "pocao_vida": {
            "id": "pocao_vida",
            "nome": "Poção de Vida",
            "emoji": "🧪",
            "descricao": "Restaura 75 pontos de vida.",
            "preco": 150,
            "efeito": {"tipo": "cura", "valor": 75},
        },
        "adrenalina": {
            "id": "adrenalina",
            "nome": "Injeção de Adrenalina",
            "emoji": "💉",
            "descricao": "Aumenta seu ATK em 20 por 2 min.",
            "preco": 250,
            "efeito": {"tipo": "buff", "stat": "atk", "valor": 20, "duracao": 120},
        },
    },
    "especiais": {
        "invocador_colosso": {
            "id": "invocador_colosso",
            "nome": "Invocador do Colosso",
            "emoji": "👹",
            "descricao": "Invoca o Colosso de Obsidiana, um chefe mundial.",
            "preco": 5000,
        },
    },
}

# --- INIMIGOS PVE ---
INIMIGOS = {
    "cacar": [
        {
            "nome": "Lobo Selvagem",
            "hp": 30,
            "atk": 10,
            "defesa": 3,
            "xp": 10,
            "dinheiro": 15,
        },
        {
            "nome": "Urso Pardo",
            "hp": 80,
            "atk": 12,
            "defesa": 8,
            "xp": 20,
            "dinheiro": 40,
        },
    ],
    "batalhar": [
        {
            "nome": "Cavaleiro Recruta",
            "hp": 50,
            "atk": 8,
            "defesa": 5,
            "xp": 15,
            "dinheiro": 25,
        },
        {
            "nome": "Cavaleiro de Elite",
            "hp": 100,
            "atk": 15,
            "defesa": 10,
            "xp": 30,
            "dinheiro": 60,
        },
    ],
}

# --- CHEFE MUNDIAL ---
BOSS_INFO = {
    "id": "colosso_obsidiana",
    "nome": "Colosso de Obsidiana",
    "hp_total": 10000,
    "atk": 50,
    "defesa": 30,
    "recompensas": {
        "top_1_dmg": {"dinheiro": 10000, "xp": 2000},
        "top_2_dmg": {"dinheiro": 5000, "xp": 1000},
        "top_3_dmg": {"dinheiro": 2500, "xp": 500},
        "participacao": {"dinheiro": 500, "xp": 100},
    },
}
