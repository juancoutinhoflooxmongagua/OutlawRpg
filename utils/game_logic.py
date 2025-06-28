# /utils/game_logic.py
import json
import os
import time
from datetime import datetime
from config import HABILIDADES, xp_para_level_up, BOSS_DB_FILE


def carregar_dados(arquivo):
    if not os.path.exists(os.path.dirname(arquivo)):
        os.makedirs(os.path.dirname(arquivo))
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def salvar_dados(dados, arquivo):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4)


def get_player_data(bot, user_id):
    user_id = str(user_id)
    if user_id not in bot.fichas:
        return None
    return bot.fichas[user_id]


def get_hp_max(player_data):
    if not player_data:
        return 100
    estilo = player_data.get("estilo_luta")
    hp_base = HABILIDADES.get(estilo, {}).get("stats_base", {}).get("hp", 100)
    level = player_data.get("level", 1)
    return hp_base + (level * 10)


def get_stat(player_data, stat: str):
    if not player_data:
        return 0
    estilo = player_data.get("estilo_luta")
    base_val = HABILIDADES.get(estilo, {}).get("stats_base", {}).get(stat, 0)
    level_bonus = player_data.get("level", 1) // 2
    return base_val + level_bonus


def check_cooldown(player_data, command):
    now = int(time.time())
    if command in player_data.get("cooldowns", {}):
        cooldown_end = player_data["cooldowns"][command]
        if now < cooldown_end:
            return cooldown_end - now
    return 0


def set_cooldown(player_data, command, duration_seconds):
    player_data.setdefault("cooldowns", {})[command] = (
        int(time.time()) + duration_seconds
    )


def criar_barra(atual, maximo, tamanho=10, cor_cheia="🟩", cor_vazia="🟥"):
    if maximo <= 0:
        return f"[{cor_vazia * tamanho}]"
    percentual = max(0, min(1.0, atual / maximo))
    cheio = int(tamanho * percentual)
    vazio = tamanho - cheio
    return f"[{cor_cheia * cheio}{cor_vazia * vazio}]"


def verificar_level_up(player_data):
    level_atual = player_data["level"]
    xp_necessario = xp_para_level_up(level_atual)

    if player_data["xp"] >= xp_necessario:
        player_data["level"] += 1
        player_data["xp"] -= xp_necessario
        return player_data["level"]
    return None


def get_boss_data():
    return carregar_dados(BOSS_DB_FILE)


def save_boss_data(data):
    salvar_dados(data, BOSS_DB_FILE)
