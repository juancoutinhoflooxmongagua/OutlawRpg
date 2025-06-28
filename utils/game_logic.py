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
    if user_id not in bot.fichas_db:
        return None
    return bot.fichas_db[user_id]


def get_hp_max(player_data):
    if not player_data:
        return 100
    estilo = player_data.get("estilo_luta")
    hp_base = HABILIDADES.get(estilo, {}).get("stats_base", {}).get("hp", 100)
    level = player_data.get("level", 1)
    return hp_base + (level * 10)


def get_stat(player_data, stat: str):
    """
    Calcula o valor total de um atributo (stat), somando o valor base,
    o bónus de nível e os pontos de aprimoramento.
    """
    if not player_data:
        return 0

    # Valor base do estilo de luta
    estilo = player_data.get("estilo_luta")
    base_val = HABILIDADES.get(estilo, {}).get("stats_base", {}).get(stat, 0)

    # Bónus adquirido por nível
    level_bonus = (player_data.get("level", 1) - 1) // 2

    # Bónus adquirido por aprimoramentos
    aprimoramento_bonus = player_data.get("aprimoramentos", {}).get(stat, 0)

    return base_val + level_bonus + aprimoramento_bonus


def check_cooldown(player_data, command):
    now = int(time.time())
    cooldown_end = player_data.get("cooldowns", {}).get(command)

    if not cooldown_end:
        return 0

    if isinstance(cooldown_end, str):
        try:
            cooldown_end = int(datetime.fromisoformat(cooldown_end).timestamp())
        except ValueError:
            return 0

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
        # Bónus de HP ao subir de nível
        player_data["hp"] = get_hp_max(player_data)
        return player_data["level"]
    return None


def get_boss_data():
    return carregar_dados(BOSS_DB_FILE)


def save_boss_data(data):
    salvar_dados(data, BOSS_DB_FILE)
