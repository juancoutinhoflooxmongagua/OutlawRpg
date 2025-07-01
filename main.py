import discord
from discord.ext import commands, tasks
from discord import app_commands, Embed, Color, Interaction, ui, ButtonStyle
import json
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_DATA_FILE = os.path.join(SCRIPT_DIR, "outlaws_data.json")
GUILD_ID = 0  # COLOQUE O ID DO SEU SERVIDOR AQUI PARA TESTES RÁPIDOS

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
    "mira_semi_automatica": {  # Reused for Atirador cooldown reduction value
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
    "habilidade_inata": {  # Not a purchasable item, but used for passive buffs
        "xp_multiplier_passive": 0.10,
        "attack_bonus_passive_percent": 0.05,
    },
    "bencao_dracula": {  # NEW ITEM FOR VAMPIRE BUFF
        "name": "Bênção de Drácula",
        "price": 1000,  # Preço para desbloquear na loja
        "class_restriction": "Vampiro",
        "cost_energy": 3,
        "duration_seconds": 5 * 60,  # 5 minutes
        "evasion_chance": 0.15,  # 15% chance to evade
        "hp_steal_percent_on_evade": 0.25,  # Steal 25% of evaded damage
        "emoji": "🦇",
    },
    "bencao_rei_henrique": {  # New item for Aura buff
        "name": "Benção do Rei Henrique",
        "price": 1000,  # Preço para desbloquear na loja, se quiser. Ou remova se for só um talento.
        "style_restriction": "Aura",
        "cost_energy": 5,
        "duration_seconds": 10 * 60,  # 10 minutes
        "attack_multiplier": 1.20,  # 20% increase
        "special_attack_multiplier": 1.20,  # 20% increase
        "max_hp_multiplier": 1.20,  # 20% increase
        "cooldown_reduction_percent": 0.10,  # 10% cooldown reduction for all skills
        "emoji": "✨",
    },
}

# New dictionary for class transformations
CLASS_TRANSFORMATIONS = {
    "Espadachim": {
        "name": "Lâmina Fantasma",
        "emoji": "👻",
        "cost_energy": TRANSFORM_COST,
        "duration_seconds": 5 * 60,  # 5 minutes
        "attack_multiplier": 1.20,
        "special_attack_multiplier": 1.10,
        "hp_multiplier": 0.90,  # Penalty
    },
    "Lutador": {
        "name": "Punho de Aço",
        "emoji": "💪",
        "cost_energy": TRANSFORM_COST,
        "duration_seconds": 5 * 60,  # 5 minutes
        "attack_multiplier": 1.15,
        "hp_multiplier": 1.15,
    },
    "Atirador": {
        "name": "Olho de Águia",
        "emoji": "🦅",
        "cost_energy": TRANSFORM_COST,
        "duration_seconds": 5 * 60,  # 5 minutes
        "attack_multiplier": 1.05,
        "special_attack_multiplier": 1.25,
        "cooldown_reduction_percent": 0.20,  # Cooldown for special attacks
    },
    "Curandeiro": {
        "name": "Bênção Vital",
        "emoji": "😇",
        "cost_energy": TRANSFORM_COST,
        "duration_seconds": 5 * 60,  # 5 minutes
        "healing_multiplier": 1.25,
        "hp_multiplier": 1.10,
    },
    "Vampiro": {
        "name": "Lorde Sanguinário",
        "emoji": "🧛",
        "cost_energy": TRANSFORM_COST,
        "duration_seconds": 5 * 60,  # 5 minutes
        "attack_multiplier": 1.80,  # Already defined in code, but centralizing
        "special_attack_multiplier": 2.00,  # Already defined in code
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


# --- GERENCIAMENTO DE DADOS ---
def load_data():
    if not os.path.exists(PLAYER_DATA_FILE):
        return {}
    try:
        with open(PLAYER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


player_database = load_data()


def save_data():
    try:
        with open(PLAYER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(player_database, f, indent=4)
    except IOError as e:
        print(f"ERRO CRÍTICO AO SALVAR DADOS: {e}")


def get_player_data(user_id):
    """Retrieves raw player data from the database."""
    return player_database.get(str(user_id))


# Helper function to create XP bar
def create_xp_bar(current_xp: int, needed_xp: int, length: int = 10) -> str:
    if needed_xp == 0:
        return "`" + "█" * length + "`"
    progress = min(current_xp / needed_xp, 1.0)
    filled_length = int(length * progress)
    bar = "█" * filled_length + "░" * (length - filled_length)
    return f"`{bar}`"


# Helper function to process level-ups
async def check_and_process_levelup(
    member: discord.Member,
    player_data: dict,
    send_target: Interaction | discord.TextChannel,
):
    level = player_data.get("level", 1)
    xp_needed = int(XP_PER_LEVEL_BASE * (level**1.2))

    while player_data["xp"] >= xp_needed:
        player_data["level"] += 1
        player_data["xp"] -= xp_needed
        player_data["attribute_points"] = (
            player_data.get("attribute_points", 0) + ATTRIBUTE_POINTS_PER_LEVEL
        )
        player_data["max_hp"] += 10
        player_data["hp"] = player_data["max_hp"]  # Restore HP on level up

        embed = Embed(
            title="🌟 LEVEL UP! 🌟",
            description=f"Parabéns, {member.mention}! Você alcançou o **Nível {player_data['level']}**!",
            color=Color.gold(),
        )
        embed.set_thumbnail(
            url="https://media.tenor.com/drxH1lO9cfEAAAAi/dark-souls-bonfire.gif"
        )
        embed.add_field(
            name="Recompensas",
            value=f"🔹 **{ATTRIBUTE_POINTS_PER_LEVEL}** Pontos de Atributo\n🔹 Vida totalmente restaurada!",
            inline=False,
        )
        embed.set_footer(text="Use /distribuir_pontos para ficar mais forte!")

        if isinstance(send_target, Interaction):
            try:
                await send_target.followup.send(embed=embed)
            except:
                await send_target.channel.send(embed=embed)
        else:
            await send_target.send(embed=embed)

        xp_needed = int(XP_PER_LEVEL_BASE * (player_data["level"] ** 1.2))


def calculate_effective_stats(raw_player_data: dict) -> dict:
    """Calculates a player's effective stats based on their base stats, transformation, and inventory items.
    Does NOT modify the original raw_player_data.
    """
    effective_data = raw_player_data.copy()

    # Apply passive bonuses from "Habilidade Inata" source of power
    if "habilidade_inata" in ITEMS_DATA:
        effective_data["attack_bonus_passive_percent"] = ITEMS_DATA["habilidade_inata"][
            "attack_bonus_passive_percent"
        ]
    else:
        effective_data["attack_bonus_passive_percent"] = 0.0  # Default if not defined

    # Initialize current attack/special_attack/max_hp with base values
    effective_data["attack"] = raw_player_data["base_attack"]
    effective_data["special_attack"] = raw_player_data["base_special_attack"]
    effective_data["max_hp"] = raw_player_data["max_hp"]  # Start with raw max_hp
    effective_data["healing_multiplier"] = 1.0  # Default for healing

    # Apply class transformations (including Vampire Lorde Sanguinário)
    if (
        effective_data.get("is_transformed")
        and effective_data["class"] in CLASS_TRANSFORMATIONS
    ):
        transform_info = CLASS_TRANSFORMATIONS[effective_data["class"]]
        effective_data["attack"] = int(
            effective_data["attack"] * transform_info.get("attack_multiplier", 1.0)
        )
        effective_data["special_attack"] = int(
            effective_data["special_attack"]
            * transform_info.get("special_attack_multiplier", 1.0)
        )
        effective_data["max_hp"] = int(
            effective_data["max_hp"] * transform_info.get("hp_multiplier", 1.0)
        )
        effective_data["healing_multiplier"] = effective_data[
            "healing_multiplier"
        ] * transform_info.get("healing_multiplier", 1.0)

    # Apply Aura-specific transformation (King Henry's Blessing)
    if (
        effective_data.get("aura_blessing_active")
        and "bencao_rei_henrique" in ITEMS_DATA
    ):
        blessing_info = ITEMS_DATA["bencao_rei_henrique"]
        effective_data["attack"] = int(
            effective_data["attack"] * blessing_info["attack_multiplier"]
        )
        effective_data["special_attack"] = int(
            effective_data["special_attack"]
            * blessing_info["special_attack_multiplier"]
        )
        effective_data["max_hp"] = int(
            effective_data["max_hp"] * blessing_info["max_hp_multiplier"]
        )

    # Apply item bonuses based on inventory (after transformations for proper stacking)
    inventory = effective_data.get("inventory", {})

    # Manopla do Lutador: Increases attack and HP
    if (
        inventory.get("manopla_lutador", 0) > 0
        and effective_data["class"] == "Lutador"
        and "manopla_lutador" in ITEMS_DATA
    ):
        effective_data["attack"] = int(
            effective_data["attack"]
            * (1 + ITEMS_DATA["manopla_lutador"]["attack_bonus_percent"])
        )
        effective_data["max_hp"] = int(
            effective_data["max_hp"] + ITEMS_DATA["manopla_lutador"]["hp_bonus_flat"]
        )

    # Espada Fantasma: Attack bonus and HP penalty
    if (
        inventory.get("espada_fantasma", 0) > 0
        and effective_data["class"] == "Espadachim"
        and "espada_fantasma" in ITEMS_DATA
    ):
        effective_data["attack"] = int(
            effective_data["attack"]
            * (1 + ITEMS_DATA["espada_fantasma"]["attack_bonus_percent"])
        )
        # Apply penalty to the calculated max_hp based on previous buffs
        effective_data["max_hp"] = int(
            effective_data["max_hp"]
            * (1 - ITEMS_DATA["espada_fantasma"]["hp_penalty_percent"])
        )
        effective_data["hp"] = min(
            effective_data["hp"], effective_data["max_hp"]
        )  # Adjust current HP

    # Cajado do Curandeiro: Increases healing effectiveness
    if (
        inventory.get("cajado_curandeiro", 0) > 0
        and effective_data["class"] == "Curandeiro"
        and "cajado_curandeiro" in ITEMS_DATA
    ):
        effective_data["healing_multiplier"] = (
            effective_data["healing_multiplier"]
            * ITEMS_DATA["cajado_curandeiro"]["effect_multiplier"]
        )

    # Apply passive attack bonus from "Habilidade Inata" (final layer)
    effective_data["attack"] = int(
        effective_data["attack"]
        * (1 + effective_data.get("attack_bonus_passive_percent", 0.0))
    )

    return effective_data


# --- SETUP DO BOT ---
class OutlawsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        auto_save.start()
        energy_regeneration.start()
        boss_attack_loop.start()
        await self.tree.sync()
        print("Comandos sincronizados!")

    async def on_ready(self):
        print(f"Bot {self.user} está online!")
        print(f"Dados de {len(player_database)} jogadores carregados.")

    async def close(self):
        print("Desligando e salvando dados...")
        save_data()
        await super().close()


bot = OutlawsBot()


# Custom checks for app commands
def is_in_city(i: Interaction):
    p = get_player_data(i.user.id)
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "cidade":
        return True
    raise NotInCity("Este comando só pode ser usado em uma cidade.")


def is_in_wilderness(i: Interaction):
    p = get_player_data(i.user.id)
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "selvagem":
        return True
    raise NotInWilderness("Este comando só pode ser usado em áreas selvagens.")


def check_player_exists(i: Interaction):
    p = get_player_data(i.user.id)
    return p and p.get("status") != "afk"


async def run_turn_based_combat(
    interaction: Interaction,
    raw_player_data: dict,
    enemy: dict,
    initial_attack_style: str = "basico",
):
    log = []
    player_hp = raw_player_data["hp"]
    enemy_hp = enemy["hp"]
    amulet_activated_this_combat = False

    player_stats = calculate_effective_stats(raw_player_data)

    embed = Embed(title=f"⚔️ Batalha Iniciada! ⚔️", color=Color.orange())
    embed.set_thumbnail(url=enemy.get("thumb"))
    embed.add_field(
        name=interaction.user.display_name,
        value=f"❤️ {player_hp}/{player_stats['max_hp']}",
        inline=True,
    )
    embed.add_field(
        name=enemy["name"], value=f"❤️ {enemy_hp}/{enemy['hp']}", inline=True
    )

    # Defer the initial response if not already deferred by the calling command
    if not interaction.response.is_done():
        await interaction.response.defer()

    battle_message = await interaction.edit_original_response(embed=embed)

    turn = 1
    while player_hp > 0 and enemy_hp > 0:
        await asyncio.sleep(2.5)

        # --- Player's Turn ---
        player_dmg = 0
        attack_type_name = ""
        crit_msg = ""

        if turn == 1:
            if initial_attack_style == "basico":
                player_dmg = random.randint(
                    player_stats["attack"] // 2, player_stats["attack"]
                )
                attack_type_name = "Ataque Básico"
                if raw_player_data["class"] == "Vampiro":
                    heal_from_vampire_basic = int(player_dmg * 0.5)
                    raw_player_data["hp"] = min(
                        raw_player_data["max_hp"],
                        raw_player_data["hp"] + heal_from_vampire_basic,
                    )
                    log.append(
                        f"🩸 Você sugou `{heal_from_vampire_basic}` HP do inimigo!"
                    )
            elif initial_attack_style == "especial":
                player_dmg = random.randint(
                    int(player_stats["special_attack"] * 0.8),
                    int(player_stats["special_attack"] * 1.5),
                )
                attack_type_name = "Ataque Especial"
                # Energy cost for special attack
                cost_energy_special = TRANSFORM_COST

                # Apply Aura Blessing cooldown reduction
                if (
                    raw_player_data.get("aura_blessing_active")
                    and "bencao_rei_henrique" in ITEMS_DATA
                ):
                    cost_energy_special = max(
                        1,
                        int(
                            cost_energy_special
                            * (
                                1
                                - ITEMS_DATA["bencao_rei_henrique"][
                                    "cooldown_reduction_percent"
                                ]
                            )
                        ),
                    )
                # Apply Atirador transformation cooldown reduction
                if (
                    raw_player_data.get("is_transformed")
                    and raw_player_data["class"] == "Atirador"
                    and "cooldown_reduction_percent"
                    in CLASS_TRANSFORMATIONS["Atirador"]
                ):
                    cost_energy_special = max(
                        1,
                        int(
                            cost_energy_special
                            * (
                                1
                                - CLASS_TRANSFORMATIONS["Atirador"][
                                    "cooldown_reduction_percent"
                                ]
                            )
                        ),
                    )

                raw_player_data["energy"] = max(
                    0, raw_player_data["energy"] - cost_energy_special
                )

                if raw_player_data["class"] == "Vampiro":
                    heal_from_vampire_special = int(player_dmg * 0.75)
                    raw_player_data["hp"] = min(
                        raw_player_data["max_hp"],
                        raw_player_data["hp"] + heal_from_vampire_special,
                    )
                    log.append(
                        f"🧛 Você sugou `{heal_from_vampire_special}` HP do inimigo com seu ataque especial!"
                    )
        else:  # Subsequent turns are always basic attack in current design
            player_dmg = random.randint(
                player_stats["attack"] // 2, player_stats["attack"]
            )
            attack_type_name = "Ataque Básico"
            if raw_player_data["class"] == "Vampiro":
                heal_from_vampire_basic = int(player_dmg * 0.5)
                raw_player_data["hp"] = min(
                    raw_player_data["max_hp"],
                    raw_player_data["hp"] + heal_from_vampire_basic,
                )
                log.append(f"🩸 Você sugou `{heal_from_vampire_basic}` HP do inimigo!")

        if random.random() < CRITICAL_CHANCE:
            player_dmg = int(player_dmg * CRITICAL_MULTIPLIER)
            crit_msg = "💥 **CRÍTICO!** "

        enemy_hp -= player_dmg
        log.append(
            f"➡️ **Turno {turn}**: {crit_msg}Você usou **{attack_type_name}** e causou `{player_dmg}` de dano."
        )
        if len(log) > 5:
            log.pop(0)

        player_hp = raw_player_data["hp"]  # Update player_hp after potential healing

        embed.description = "\n".join(log)
        embed.set_field_at(
            0,
            name=interaction.user.display_name,
            value=f"❤️ {max(0, player_hp)}/{player_stats['max_hp']}",
            inline=True,
        )
        embed.set_field_at(
            1,
            name=enemy["name"],
            value=f"❤️ {max(0, enemy_hp)}/{enemy['hp']}",
            inline=True,
        )
        await interaction.edit_original_response(embed=embed)

        if enemy_hp <= 0:
            break

        await asyncio.sleep(2.5)

        # --- Turno do Inimigo ---
        enemy_dmg = random.randint(enemy["attack"] // 2, enemy["attack"])

        # Lógica da Bênção de Drácula (Vampiro)
        if (
            raw_player_data["class"] == "Vampiro"
            and raw_player_data.get("bencao_dracula_active", False)
            and "bencao_dracula" in ITEMS_DATA
            and random.random() < ITEMS_DATA["bencao_dracula"]["evasion_chance"]
        ):
            hp_stolen_on_evade = int(
                enemy_dmg * ITEMS_DATA["bencao_dracula"]["hp_steal_percent_on_evade"]
            )
            raw_player_data["hp"] = min(
                raw_player_data["max_hp"], raw_player_data["hp"] + hp_stolen_on_evade
            )

            log.append(
                f"👻 **DESVIADO!** {enemy['name']} errou o ataque! Você sugou `{hp_stolen_on_evade}` HP!"
            )
            if len(log) > 5:
                log.pop(0)
            player_hp = raw_player_data["hp"]  # Update player_hp after evasion heal
            embed.description = "\n".join(
                log
            )  # Update embed description for evasion message
            embed.set_field_at(  # Update player HP field
                0,
                name=interaction.user.display_name,
                value=f"❤️ {max(0, player_hp)}/{player_stats['max_hp']}",
                inline=True,
            )
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(1.5)
            continue  # Skip normal damage if evaded

        player_hp -= enemy_dmg
        raw_player_data["hp"] = (
            player_hp  # Ensure raw_player_data is updated for amulet check
        )

        # Lógica do Amuleto de Pedra (uma vez por combate E uma vez por vida)
        if (
            player_hp <= 0
            and raw_player_data["inventory"].get("amuleto_de_pedra", 0) > 0
            and not amulet_activated_this_combat
            and not raw_player_data.get("amulet_used_since_revive", False)
        ):
            player_hp = 1
            raw_player_data["hp"] = 1  # Update raw data
            amulet_activated_this_combat = True
            raw_player_data["amulet_used_since_revive"] = True
            log.append("✨ **Amuleto de Pedra ativado!** Você sobreviveu por um triz!")
            if len(log) > 5:
                log.pop(0)
            embed.description = "\n".join(log)
            embed.set_field_at(
                0,
                name=interaction.user.display_name,
                value=f"❤️ {max(0, player_hp)}/{player_stats['max_hp']}",
                inline=True,
            )
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(1.5)

        log.append(f"⬅️ {enemy['name']} ataca e causa `{enemy_dmg}` de dano.")
        if len(log) > 5:
            log.pop(0)

        embed.description = "\n".join(log)
        embed.set_field_at(
            0,
            name=interaction.user.display_name,
            value=f"❤️ {max(0, player_hp)}/{player_stats['max_hp']}",
            inline=True,
        )
        await interaction.edit_original_response(embed=embed)

        turn += 1

    # --- End of Battle ---
    final_embed = Embed()
    raw_player_data["hp"] = max(0, player_hp)  # Final update to raw data

    if player_hp <= 0:
        final_embed.title = "☠️ Você Foi Derrotado!"
        final_embed.color = Color.dark_red()
        raw_player_data["status"] = "dead"
        raw_player_data["deaths"] += 1
        final_embed.description = f"O {enemy['name']} foi muito forte para você."
    else:
        final_embed.title = "🏆 Vitória! 🏆"
        final_embed.color = Color.green()
        final_embed.description = f"Você derrotou o {enemy['name']}!"

        xp_gain_raw = enemy["xp"]
        # Apply passive XP bonus from Habilidade Inata (after all other multipliers)
        xp_multiplier_passive = ITEMS_DATA.get("habilidade_inata", {}).get(
            "xp_multiplier_passive", 0.0
        )

        if raw_player_data.get("xptriple") is True:
            xp_gain = xp_gain_raw * 3
            xp_message = f"✨ +{xp_gain} XP (triplicado!)"
        else:
            xp_gain = xp_gain_raw
            xp_message = f"✨ +{xp_gain} XP"

        if (
            raw_player_data.get("style") == "Habilidade Inata"
            and xp_multiplier_passive > 0
        ):
            original_xp_gain = xp_gain
            xp_gain = int(xp_gain * (1 + xp_multiplier_passive))
            xp_message += f" (Habilidade Inata: +{int(xp_multiplier_passive*100)}%!)"
            if (
                "triplicado" in xp_message
            ):  # Ensure description is clear if both are active
                xp_message = f"✨ +{xp_gain} XP (triplicado + Habilidade Inata: +{int(xp_multiplier_passive*100)}%!)"

        money_gain_raw = enemy["money"]
        if raw_player_data.get("money_double") is True:
            money_gain = money_gain_raw * 2
            money_message = f"💰 +${money_gain} (duplicado!)"
        else:
            money_gain = money_gain_raw
            money_message = f"💰 +${money_gain}"

        final_embed.add_field(
            name="Recompensas", value=f"{money_message}\n{xp_message}"
        )

        raw_player_data["money"] += money_gain
        raw_player_data["xp"] += xp_gain

        if enemy["name"] == BOSS_DATA["name"]:
            for item, quantity in BOSS_DATA.get("drops", {}).items():
                if item == "amuleto_de_pedra":
                    if raw_player_data["inventory"].get("amuleto_de_pedra", 0) == 0:
                        raw_player_data["inventory"]["amuleto_de_pedra"] = 1
                        final_embed.add_field(
                            name="Item Encontrado!",
                            value=f"Você encontrou **{ITEMS_DATA[item]['name']}**!",
                            inline=False,
                        )
                    else:
                        final_embed.add_field(
                            name="Amuleto de Pedra (Já Possuído)",
                            value=f"Você já possui o **{ITEMS_DATA[item]['name']}**. Não é possível obter mais de um.",
                            inline=False,
                        )
                else:
                    raw_player_data["inventory"][item] = (
                        raw_player_data["inventory"].get(item, 0) + quantity
                    )
                    final_embed.add_field(
                        name="Item Encontrado!",
                        value=f"Você encontrou **{ITEMS_DATA[item]['name']}**!",
                        inline=False,
                    )

        await check_and_process_levelup(interaction.user, raw_player_data, interaction)

    save_data()
    await interaction.edit_original_response(embed=final_embed)


# --- VIEWS DA INTERFACE (BOTÕES E MENUS) ---


class ClassChooserView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.chosen_class = None
        self.chosen_style = None

    @ui.select(
        placeholder="Escolha sua Classe...",
        options=[
            discord.SelectOption(label="Espadachim", emoji="⚔️"),
            discord.SelectOption(label="Lutador", emoji="🥊"),
            discord.SelectOption(label="Atirador", emoji="🏹"),
            discord.SelectOption(label="Curandeiro", emoji="🩹"),
            discord.SelectOption(label="Vampiro", emoji="🧛"),
        ],
    )
    async def class_select(self, i: Interaction, s: ui.Select):
        self.chosen_class = s.values[0]
        # Defer the update to keep the interaction alive for the next select or button
        await i.response.send_message(
            f"Classe: **{self.chosen_class}**. Agora, a fonte de poder.", ephemeral=True
        )

    @ui.select(
        placeholder="Escolha sua Fonte de Poder...",
        options=[
            discord.SelectOption(label="Habilidade Inata", emoji="💪"),
            discord.SelectOption(label="Aura", emoji="✨"),
        ],
    )
    async def style_select(self, i: Interaction, s: ui.Select):
        self.chosen_style = s.values[0]
        await i.response.send_message(
            f"Fonte de Poder: **{self.chosen_style}**.", ephemeral=True
        )

    @ui.button(label="Confirmar Criação", style=ButtonStyle.success, row=2)
    async def confirm_button(self, i: Interaction, b: ui.Button):
        if not self.chosen_class or not self.chosen_style:
            await i.response.send_message(
                "Escolha uma classe e um estilo!", ephemeral=True
            )
            return
        user_id = str(i.user.id)
        if user_id in player_database:
            await i.response.send_message("Você já possui uma ficha!", ephemeral=True)
            return
        base_stats = {
            "hp": INITIAL_HP,
            "attack": INITIAL_ATTACK,
            "special_attack": INITIAL_SPECIAL_ATTACK,
        }
        if self.chosen_class == "Lutador":
            base_stats["hp"] += 20
            base_stats["attack"] += 5
        elif self.chosen_class == "Espadachim":
            base_stats["attack"] += 10
            base_stats["special_attack"] -= 5
        elif self.chosen_class == "Atirador":
            base_stats["hp"] -= 10
            base_stats["special_attack"] += 10
        elif self.chosen_class == "Curandeiro":
            base_stats["special_attack"] += 5
        elif self.chosen_class == "Vampiro":
            base_stats["hp"] += 30
            base_stats["attack"] += 8
            base_stats["special_attack"] += 15

        player_database[user_id] = {
            "name": i.user.display_name,
            "class": self.chosen_class,
            "style": self.chosen_style,
            "xp": 0,
            "level": 1,
            "money": INITIAL_MONEY,
            "hp": base_stats["hp"],
            "max_hp": base_stats["hp"],
            "base_attack": base_stats["attack"],
            "base_special_attack": base_stats["special_attack"],
            "inventory": {},
            "cooldowns": {},
            "status": "online",
            "bounty": 0,
            "kills": 0,
            "deaths": 0,
            "energy": MAX_ENERGY,
            "is_transformed": False,
            "transform_end_time": 0,  # New field for generic class transformation
            "aura_blessing_active": False,
            "aura_blessing_end_time": 0,
            "bencao_dracula_active": False,
            "bencao_dracula_end_time": 0,
            "amulet_used_since_revive": False,
            "attribute_points": 0,
            "location": STARTING_LOCATION,
            "transform_name": CLASS_TRANSFORMATIONS.get(self.chosen_class, {}).get(
                "name", "Super Forma"
            ),
            "xptriple": False,
            "money_double": False,
        }
        save_data()
        embed = Embed(
            title=f"Ficha de {i.user.display_name} Criada!",
            description=f"Bem-vindo ao mundo de OUTLAWS, **{self.chosen_class}** que usa **{self.chosen_style}**!",
            color=Color.green(),
        )
        embed.set_thumbnail(
            url=i.user.avatar.url if i.user.avatar else discord.Embed.Empty
        )
        embed.set_footer(text="Use /perfil para ver seus status.")
        await i.response.edit_message(content=None, embed=embed, view=None)
        self.stop()


class ProfileView(ui.View):
    def __init__(
        self,
        user: discord.Member,
        bot_user: discord.ClientUser,
        original_interaction: Interaction,
    ):
        super().__init__(timeout=180)
        self.user = user
        self.bot_user = bot_user
        self.original_interaction = (
            original_interaction  # Store the original interaction
        )

    def create_profile_embed(self) -> discord.Embed:
        raw_player_data = get_player_data(self.user.id)
        if (
            not raw_player_data
        ):  # Should not happen with check_player_exists but for safety
            return Embed(
                title="Erro",
                description="Dados do jogador não encontrados.",
                color=Color.red(),
            )

        player_stats = calculate_effective_stats(raw_player_data)

        embed_color = (
            Color.orange()
            if raw_player_data.get("is_transformed", False)
            or raw_player_data.get("aura_blessing_active", False)
            or raw_player_data.get("bencao_dracula_active", False)
            else self.user.color
        )
        title_prefix_list = []
        if raw_player_data.get("is_transformed"):
            # Use the stored transform_name for the actual class transformation
            transform_name = CLASS_TRANSFORMATIONS.get(
                raw_player_data["class"], {}
            ).get("name", "Transformado")
            title_prefix_list.append(f"🔥 {transform_name}")
        if raw_player_data.get("aura_blessing_active"):
            title_prefix_list.append(
                f"✨ {ITEMS_DATA.get('bencao_rei_henrique', {}).get('name', 'Bênção da Aura')}"
            )
        if raw_player_data.get("bencao_dracula_active"):
            title_prefix_list.append(
                f"🦇 {ITEMS_DATA.get('bencao_dracula', {}).get('name', 'Bênção do Vampiro')}"
            )

        title_prefix = " | ".join(title_prefix_list) + (
            " | " if title_prefix_list else ""
        )

        embed = Embed(
            title=f"{title_prefix}Perfil de {self.user.display_name}", color=embed_color
        )
        embed.set_thumbnail(
            url=self.user.avatar.url if self.user.avatar else discord.Embed.Empty
        )
        embed.set_image(url="https://c.tenor.com/twwaRu0KGWoAAAAC/tenor.gif")
        location = raw_player_data.get("location", "Desconhecido")
        location_info = WORLD_MAP.get(location, {})
        status_map = {"online": "🟢 Online", "dead": "💀 Morto", "afk": "🌙 AFK"}
        embed.add_field(
            name="📍 Localização & Status",
            value=f"**{location_info.get('emoji', '❓')} {location}**\n*Status: {status_map.get(raw_player_data['status'], '?')}*",
            inline=True,
        )
        xp_needed = int(XP_PER_LEVEL_BASE * (raw_player_data["level"] ** 1.2))
        xp_bar = create_xp_bar(raw_player_data["xp"], xp_needed)
        embed.add_field(
            name="⚔️ Classe & Nível",
            value=f"**{raw_player_data['class']}** | Nível **{raw_player_data['level']}**\n{xp_bar} `{raw_player_data['xp']}/{xp_needed}`",
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(
            name="❤️ Vida",
            value=f"**{raw_player_data['hp']}/{player_stats['max_hp']}**",
            inline=True,
        )

        attack_display = f"**{player_stats['attack']}**"
        special_attack_display = f"**{player_stats['special_attack']}**"

        # General transformation display (Lorde Sanguinário is handled by is_transformed)
        if raw_player_data.get("is_transformed"):
            attack_display += f" (Base: {raw_player_data['base_attack']})"
            special_attack_display += (
                f" (Base: {raw_player_data['base_special_attack']})"
            )
        else:
            if raw_player_data["base_attack"] > INITIAL_ATTACK:
                attack_display += f" (Aprimorado)"
            if raw_player_data["base_special_attack"] > INITIAL_SPECIAL_ATTACK:
                special_attack_display += f" (Aprimorado)"

        # Item bonuses
        if (
            raw_player_data.get("inventory", {}).get("manopla_lutador", 0) > 0
            and raw_player_data["class"] == "Lutador"
            and "manopla_lutador" in ITEMS_DATA
        ):
            attack_display += " (+Manopla)"

        if (
            raw_player_data.get("inventory", {}).get("espada_fantasma", 0) > 0
            and raw_player_data["class"] == "Espadachim"
            and "espada_fantasma" in ITEMS_DATA
        ):
            attack_display += " (+Espada Fantasma)"

        embed.add_field(name="🗡️ Ataque", value=attack_display, inline=True)
        embed.add_field(
            name="✨ Atq. Especial", value=special_attack_display, inline=True
        )

        embed.add_field(
            name="🌟 Pontos de Atributo",
            value=f"**{raw_player_data.get('attribute_points', 0)}**",
            inline=True,
        )
        embed.add_field(
            name="⚡ Energia",
            value=f"**{raw_player_data['energy']}/{MAX_ENERGY}**",
            inline=True,
        )
        embed.add_field(
            name="💰 Dinheiro", value=f"**${raw_player_data['money']}**", inline=True
        )
        xp_triple_status = (
            "✅ Ativo" if raw_player_data.get("xptriple", False) else "❌ Inativo"
        )
        embed.add_field(
            name="Boost de XP", value=f"**{xp_triple_status}**", inline=True
        )
        money_double_status = (
            "✅ Ativo" if raw_player_data.get("money_double", False) else "❌ Inativo"
        )
        embed.add_field(
            name="Boost de Dinheiro", value=f"**{money_double_status}**", inline=True
        )

        embed.set_footer(
            text=f"Outlaws RPG • Perfil gerado em", icon_url=self.bot_user.avatar.url
        )
        embed.timestamp = datetime.now()
        return embed

    def create_inventory_embed(self) -> discord.Embed:
        raw_player_data = get_player_data(self.user.id)
        if not raw_player_data:
            return Embed(
                title="Erro",
                description="Dados do jogador não encontrados.",
                color=Color.red(),
            )

        embed = Embed(
            title=f"Inventário de {self.user.display_name}", color=Color.dark_gold()
        )
        embed.set_author(
            name=self.user.display_name,
            icon_url=self.user.avatar.url if self.user.avatar else discord.Embed.Empty,
        )
        inventory_list = []
        for item_id, amount in raw_player_data["inventory"].items():
            item_name = ITEMS_DATA.get(item_id, {}).get("name", item_id.capitalize())
            emoji = ITEMS_DATA.get(item_id, {}).get("emoji", "❔")
            inventory_list.append(f"{emoji} **{item_name}** `x{amount}`")

        embed.description = (
            "\n".join(inventory_list)
            if inventory_list
            else "*Seu inventário está vazio.*"
        )
        embed.add_field(
            name="💰 Bounty", value=f"`${raw_player_data['bounty']}`", inline=True
        )
        embed.add_field(
            name="☠️ Kills", value=f"`{raw_player_data['kills']}`", inline=True
        )
        embed.set_footer(
            text=f"Outlaws RPG • Inventário", icon_url=self.bot_user.avatar.url
        )
        embed.timestamp = datetime.now()
        return embed

    @ui.button(label="Perfil", style=ButtonStyle.primary, emoji="👤", disabled=True)
    async def profile_button(self, i: Interaction, b: ui.Button):
        self.profile_button.disabled = True
        self.inventory_button.disabled = False
        await self.original_interaction.edit_original_response(
            embed=self.create_profile_embed(), view=self
        )
        await i.response.defer()  # Acknowledge the button interaction

    @ui.button(label="Inventário", style=ButtonStyle.secondary, emoji="🎒")
    async def inventory_button(self, i: Interaction, b: ui.Button):
        self.inventory_button.disabled = True
        self.profile_button.disabled = False
        await self.original_interaction.edit_original_response(
            embed=self.create_inventory_embed(), view=self
        )
        await i.response.defer()  # Acknowledge the button interaction


class TravelView(ui.View):
    def __init__(self, current_location: str, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        for dest in WORLD_MAP.get(current_location, {}).get("conecta", []):
            self.add_item(
                TravelButton(
                    label=dest, emoji=WORLD_MAP.get(dest, {}).get("emoji", "❓")
                )
            )


class TravelButton(ui.Button):
    def __init__(self, label: str, emoji: str):
        super().__init__(label=label, style=ButtonStyle.secondary, emoji=emoji)

    async def callback(self, i: Interaction):
        player_data = get_player_data(self.view.user_id)
        if not player_data:
            await i.response.send_message(
                "Erro ao encontrar sua ficha.", ephemeral=True
            )
            return
        player_data["location"] = self.label
        save_data()
        await i.response.edit_message(
            embed=Embed(
                title=f"✈️ Viagem Concluída",
                description=f"Você viajou e chegou em **{self.label}**.",
                color=Color.blue(),
            ),
            view=None,
        )
        self.view.stop()  # Stop the view after successful travel


class HelpView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @ui.select(
        placeholder="Escolha uma categoria da Wiki...",
        options=[
            discord.SelectOption(label="Introdução", emoji="📜"),
            discord.SelectOption(label="Comandos Gerais", emoji="👤"),
            discord.SelectOption(label="Comandos de Ação", emoji="⚔️"),
            discord.SelectOption(label="Sistema de Classes", emoji="🛡️"),
            discord.SelectOption(label="Sistema de Combate", emoji="💥"),
            discord.SelectOption(label="Itens Especiais", emoji="💎"),
        ],
    )
    async def select_callback(self, i: Interaction, s: ui.Select):
        topic = s.values[0]
        embed = Embed(title=f"📜 Wiki OUTLAWS - {topic}", color=Color.blurple())
        if topic == "Introdução":
            embed.description = "Bem-vindo a OUTLAWS, um mundo impiedoso onde apenas os mais fortes sobrevivem..."
        elif topic == "Comandos Gerais":
            embed.add_field(name="/perfil", value="Mostra seu perfil.", inline=False)
            embed.add_field(
                name="/distribuir_pontos", value="Melhora atributos.", inline=False
            )
            embed.add_field(name="/reviver", value="Volta à vida.", inline=False)
            embed.add_field(
                name="/ranking", value="Mostra os mais mortais.", inline=False
            )
            embed.add_field(
                name="/afk | /voltar", value="Entra/sai do modo Ausente.", inline=False
            )
        elif topic == "Comandos de Ação":
            embed.add_field(
                name="/cacar | /batalhar",
                value="Inicia um combate por turnos.",
                inline=False,
            )
            embed.add_field(name="/atacar", value="Ataca outro jogador.", inline=False)
            embed.add_field(
                name="/trabalhar", value="Ganha dinheiro e XP.", inline=False
            )
            embed.add_field(name="/viajar", value="Move-se pelo mundo.", inline=False)
            embed.add_field(
                name="/loja | /aprimorar", value="Disponíveis em cidades.", inline=False
            )
            embed.add_field(
                name="/usar [item]", value="Usa um item do inventário.", inline=False
            )
            embed.add_field(
                name="/curar [alvo]",
                value="[Curandeiro] Cura um aliado ou a si mesmo.",
                inline=False,
            )
            embed.add_field(
                name="/transformar [forma]",
                value="Ativa uma transformação de classe/estilo (ex: Lorde Sanguinário, Benção do Rei Henrique, Bênção de Drácula).",
                inline=False,
            )
            embed.add_field(
                name="/destransformar [forma]",
                value="Desativa uma transformação específica.",
                inline=False,
            )
            embed.add_field(
                name="/ativar_bencao_aura",
                value="[Aura] Ativa diretamente a Benção do Rei Henrique.",
                inline=False,
            )
            embed.add_field(
                name="/atacar_boss", value="Ataca o boss global.", inline=False
            )
        elif topic == "Sistema de Classes":
            embed.description = "**Espadachim**: Equilibrado. Pode se transformar em **Lâmina Fantasma** (Aumenta ataque e ataque especial, penaliza vida).\n**Lutador**: Mais vida/ataque. Pode se transformar em **Punho de Aço** (Aumenta ataque e vida).\n**Atirador**: Mestre do dano especial. Pode se transformar em **Olho de Águia** (Aumenta ataque especial, reduz cooldown).\n**Curandeiro**: Pode curar com `/curar`. Pode se transformar em **Bênção Vital** (Aumenta cura e vida).\n**Vampiro**: Rouba vida e se transforma em uma besta sanguinária. Pode ativar a **Bênção de Drácula** para desviar e sugar HP! Sua transformação se chama **Lorde Sanguinário** (Aumenta muito ataque e ataque especial)."
        elif topic == "Sistema de Combate":
            embed.description = "Batalhas são por turnos. Acertos Críticos (10% de chance) causam 50% a mais de dano!"
        elif topic == "Itens Especiais":
            # Added checks for item existence
            potion_info = ITEMS_DATA.get(
                "pocao", {"emoji": "❔", "name": "Poção de Vida", "heal": 0, "price": 0}
            )
            super_potion_info = ITEMS_DATA.get(
                "super_pocao",
                {"emoji": "❔", "name": "Super Poção", "heal": 0, "price": 0},
            )
            amulet_info = ITEMS_DATA.get(
                "amuleto_de_pedra", {"emoji": "❔", "name": "Amuleto de Pedra"}
            )
            healer_staff_info = ITEMS_DATA.get(
                "cajado_curandeiro",
                {
                    "emoji": "❔",
                    "name": "Cajado do Curandeiro",
                    "effect_multiplier": 1.0,
                },
            )
            fighter_gauntlet_info = ITEMS_DATA.get(
                "manopla_lutador",
                {
                    "emoji": "❔",
                    "name": "Manopla do Lutador",
                    "attack_bonus_percent": 0.0,
                    "hp_bonus_flat": 0,
                },
            )
            shooter_sight_info = ITEMS_DATA.get(
                "mira_semi_automatica",
                {
                    "emoji": "❔",
                    "name": "Mira Semi-Automática",
                    "cooldown_reduction_percent": 0.0,
                },
            )
            ghost_sword_info = ITEMS_DATA.get(
                "espada_fantasma",
                {
                    "emoji": "❔",
                    "name": "Espada Fantasma",
                    "attack_bonus_percent": 0.0,
                    "hp_penalty_percent": 0.0,
                },
            )
            dracula_blessing_info = ITEMS_DATA.get(
                "bencao_dracula",
                {
                    "emoji": "❔",
                    "name": "Bênção de Drácula",
                    "evasion_chance": 0.0,
                    "hp_steal_percent_on_evade": 0.0,
                    "cost_energy": 0,
                    "duration_seconds": 0,
                },
            )
            king_henry_blessing_info = ITEMS_DATA.get(
                "bencao_rei_henrique",
                {
                    "emoji": "❔",
                    "name": "Benção do Rei Henrique",
                    "attack_multiplier": 1.0,
                    "special_attack_multiplier": 1.0,
                    "max_hp_multiplier": 1.0,
                    "cooldown_reduction_percent": 0.0,
                    "cost_energy": 0,
                    "duration_seconds": 0,
                },
            )

            embed.add_field(
                name=f"{potion_info['emoji']} {potion_info['name']} & {super_potion_info['emoji']} {super_potion_info['name']}",
                value="Restauram HP para continuar a jornada.",
                inline=False,
            )
            embed.add_field(
                name=f"{amulet_info['emoji']} {amulet_info['name']}",
                value="Item raro dropado pelo Colosso de Pedra. Concede uma segunda chance em combate, salvando-o da morte iminente uma vez por batalha. Este item é **permanente** e não é consumido.",
                inline=False,
            )
            embed.add_field(
                name="Equipamentos de Classe",
                value=(
                    f"Itens poderosos que fornecem bônus passivos para classes específicas quando no inventário. "
                    f"Ex: **{healer_staff_info['emoji']} {healer_staff_info['name']}** (Curandeiro) aumenta cura em {int(healer_staff_info['effect_multiplier'] * 100 - 100)}%, "
                    f"**{fighter_gauntlet_info['emoji']} {fighter_gauntlet_info['name']}** (Lutador) aumenta ataque base em {int(fighter_gauntlet_info['attack_bonus_percent'] * 100)}% e vida máxima em {fighter_gauntlet_info['hp_bonus_flat']}, "
                    f"**{shooter_sight_info['emoji']} {shooter_sight_info['name']}** (Atirador) reduz cooldown de ataque especial em {int(shooter_sight_info['cooldown_reduction_percent'] * 100)}%, "
                    f"**{ghost_sword_info['emoji']} {ghost_sword_info['name']}** (Espadachim) concede +{int(ghost_sword_info['attack_bonus_percent'] * 100)}% de ataque, mas penaliza -{int(ghost_sword_info['hp_penalty_percent'] * 100)}% do HP total."
                ),
                inline=False,
            )
            embed.add_field(
                name=f"{dracula_blessing_info['emoji']} {dracula_blessing_info['name']}",
                value=(
                    f"[Vampiro] Ativa uma bênção que concede {int(dracula_blessing_info['evasion_chance'] * 100)}% de chance de desviar de ataques inimigos e roubar {int(dracula_blessing_info['hp_steal_percent_on_evade'] * 100)}% do HP que seria o dano. "
                    f"Custa {dracula_blessing_info['cost_energy']} energia e dura {dracula_blessing_info['duration_seconds'] // 60} minutos."
                ),
                inline=False,
            )
            embed.add_field(
                name=f"{king_henry_blessing_info['emoji']} {king_henry_blessing_info['name']}",
                value=(
                    f"[Aura] Ativa uma bênção poderosa com +{int(king_henry_blessing_info['attack_multiplier'] * 100 - 100)}% ATQ/ATQ Especial/HP e -{int(king_henry_blessing_info['cooldown_reduction_percent'] * 100)}% nos cooldowns. "
                    f"Custa {king_henry_blessing_info['cost_energy']} energia e dura {king_henry_blessing_info['duration_seconds'] // 60} minutos."
                ),
                inline=False,
            )
        await i.response.edit_message(embed=embed)


class ShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        # Ensure items exist in ITEMS_DATA before adding to view
        if "pocao" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="pocao",
                    price=ITEMS_DATA["pocao"]["price"],
                    label="Comprar Poção",
                    emoji=ITEMS_DATA["pocao"]["emoji"],
                )
            )
        if "super_pocao" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="super_pocao",
                    price=ITEMS_DATA["super_pocao"]["price"],
                    label="Comprar Super Poção",
                    emoji=ITEMS_DATA["super_pocao"]["emoji"],
                )
            )
        if "invocador" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="invocador",
                    price=ITEMS_DATA["invocador"]["price"],
                    label="Comprar Invocador",
                    emoji=ITEMS_DATA["invocador"]["emoji"],
                )
            )
        if "cajado_curandeiro" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="cajado_curandeiro",
                    price=ITEMS_DATA["cajado_curandeiro"]["price"],
                    label=ITEMS_DATA["cajado_curandeiro"]["name"],
                    emoji=ITEMS_DATA["cajado_curandeiro"]["emoji"],
                )
            )
        if "manopla_lutador" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="manopla_lutador",
                    price=ITEMS_DATA["manopla_lutador"]["price"],
                    label=ITEMS_DATA["manopla_lutador"]["name"],
                    emoji=ITEMS_DATA["manopla_lutador"]["emoji"],
                )
            )
        if "mira_semi_automatica" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="mira_semi_automatica",
                    price=ITEMS_DATA["mira_semi_automatica"]["price"],
                    label=ITEMS_DATA["mira_semi_automatica"]["name"],
                    emoji=ITEMS_DATA["mira_semi_automatica"]["emoji"],
                )
            )
        if "espada_fantasma" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="espada_fantasma",
                    price=ITEMS_DATA["espada_fantasma"]["price"],
                    label=ITEMS_DATA["espada_fantasma"]["name"],
                    emoji=ITEMS_DATA["espada_fantasma"]["emoji"],
                )
            )
        # Adiciona a Bênção de Drácula na loja (para "desbloquear" a transformação)
        if "bencao_dracula" in ITEMS_DATA:
            self.add_item(
                self.BuyButton(
                    item_id="bencao_dracula",
                    price=ITEMS_DATA["bencao_dracula"]["price"],
                    label="Desbloquear Bênção Drácula",
                    emoji=ITEMS_DATA["bencao_dracula"]["emoji"],
                )
            )

    class BuyButton(ui.Button):
        def __init__(self, item_id: str, price: int, label: str, emoji: str):
            super().__init__(label=label, style=ButtonStyle.primary, emoji=emoji)
            self.item_id, self.price = item_id, price

        async def callback(self, i: Interaction):
            player_data = get_player_data(i.user.id)
            if not player_data:
                await i.response.send_message(
                    "Crie uma ficha primeiro!", ephemeral=True
                )
                return

            item_info = ITEMS_DATA.get(self.item_id)
            if not item_info:
                await i.response.send_message(
                    "Este item não é reconhecido.", ephemeral=True
                )
                return

            # Special handling for class/style restricted UNLOCKABLE items (not regular gear)
            if self.item_id == "bencao_dracula":
                if player_data["class"] != "Vampiro":
                    await i.response.send_message(
                        "Somente Vampiros podem desbloquear a Bênção de Drácula.",
                        ephemeral=True,
                    )
                    return
                if player_data["inventory"].get("bencao_dracula", 0) > 0:
                    await i.response.send_message(
                        "Você já desbloqueou a Bênção de Drácula!", ephemeral=True
                    )
                    return
            elif self.item_id == "bencao_rei_henrique":  # If you ever add this to shop
                if player_data["style"] != "Aura":
                    await i.response.send_message(
                        "Somente usuários de Aura podem desbloquear a Benção do Rei Henrique.",
                        ephemeral=True,
                    )
                    return
                if player_data["inventory"].get("bencao_rei_henrique", 0) > 0:
                    await i.response.send_message(
                        "Você já desbloqueou a Benção do Rei Henrique!", ephemeral=True
                    )
                    return
            elif (
                item_info and "class_restriction" in item_info
            ):  # For regular gear with class restriction
                if player_data["class"] != item_info["class_restriction"]:
                    await i.response.send_message(
                        f"Este item é exclusivo para a classe **{item_info['class_restriction']}**!",
                        ephemeral=True,
                    )
                    return

            if player_data["money"] < self.price:
                await i.response.send_message("Dinheiro insuficiente!", ephemeral=True)
                return

            # Prevent buying multiple unique class items / blessings
            if self.item_id in [
                "cajado_curandeiro",
                "manopla_lutador",
                "mira_semi_automatica",
                "espada_fantasma",
                "bencao_dracula",
                "bencao_rei_henrique",  # Add this if you put it in shop
            ]:
                if player_data["inventory"].get(self.item_id, 0) > 0:
                    await i.response.send_message(
                        f"Você já possui o(a) **{ITEMS_DATA[self.item_id]['name']}**!",
                        ephemeral=True,
                    )
                    return

            player_data["money"] -= self.price
            player_data["inventory"][self.item_id] = (
                player_data["inventory"].get(self.item_id, 0) + 1
            )

            # --- Aplicação de bônus/penalidades de HP na compra ---
            if (
                self.item_id == "manopla_lutador"
                and player_data["class"] == "Lutador"
                and "manopla_lutador" in ITEMS_DATA
            ):
                hp_gain_from_item = ITEMS_DATA["manopla_lutador"]["hp_bonus_flat"]
                player_data["max_hp"] += hp_gain_from_item
                player_data["hp"] = min(
                    player_data["hp"] + hp_gain_from_item, player_data["max_hp"]
                )
            elif (
                self.item_id == "espada_fantasma"
                and player_data["class"] == "Espadachim"
                and "espada_fantasma" in ITEMS_DATA
            ):
                hp_penalty_from_item = int(
                    player_data["max_hp"]
                    * ITEMS_DATA["espada_fantasma"]["hp_penalty_percent"]
                )
                player_data["max_hp"] = max(
                    1, player_data["max_hp"] - hp_penalty_from_item
                )
                player_data["hp"] = min(player_data["hp"], player_data["max_hp"])
            # --- FIM DA APLICAÇÃO DE BÔNUS/PENALIDADES DE HP ---

            save_data()
            await i.response.send_message(
                f"**{i.user.display_name}** comprou 1x {ITEMS_DATA[self.item_id]['name']}!"
            )


# --- COMANDOS DO BOT ---


## Comandos de Personagem e Status
@bot.tree.command(
    name="criar_ficha", description="Cria sua ficha de personagem no mundo de OUTLAWS."
)
async def criar_ficha(i: Interaction):
    if get_player_data(i.user.id):
        await i.response.send_message("Você já possui uma ficha!", ephemeral=True)
        return
    await i.response.send_message(
        embed=Embed(
            title="Criação de Personagem",
            description="Escolha os fundamentos do seu personagem.",
            color=Color.blurple(),
        ),
        view=ClassChooserView(),
    )


@bot.tree.command(
    name="perfil",
    description="Mostra seu perfil de fora-da-lei com um layout profissional.",
)
@app_commands.check(check_player_exists)
async def perfil(i: Interaction, membro: discord.Member = None):
    target_user = membro or i.user
    if not get_player_data(target_user.id):
        await i.response.send_message(
            "Essa pessoa ainda não é um fora-da-lei.", ephemeral=True
        )
        return

    await i.response.defer()  # Defer the response to allow time for embed and view creation

    view = ProfileView(target_user, bot.user, i)  # Pass the interaction to the view
    await i.edit_original_response(
        embed=view.create_profile_embed(),
        view=view,
    )


@bot.tree.command(name="reviver", description="Pague uma taxa para voltar à vida.")
@app_commands.check(check_player_exists)
async def reviver(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["status"] != "dead":
        await i.response.send_message("Você já está vivo!", ephemeral=True)
        return
    if player_data["money"] < REVIVE_COST:
        await i.response.send_message(
            f"Você precisa de ${REVIVE_COST} para reviver.", ephemeral=True
        )
        return
    player_data["money"] -= REVIVE_COST
    player_data["hp"] = player_data["max_hp"]
    player_data["status"] = "online"
    player_data["amulet_used_since_revive"] = False
    save_data()
    await i.response.send_message(
        embed=Embed(
            title="✨ De Volta à Vida",
            description=f"Você pagou ${REVIVE_COST} e trapaceou a morte.",
            color=Color.light_grey(),
        )
    )


@bot.tree.command(
    name="distribuir_pontos",
    description="Use seus pontos de atributo para fortalecer seu personagem.",
)
@app_commands.describe(
    atributo="Onde você quer investir seus pontos.",
    quantidade="Quantos pontos quer usar.",
)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name="💪 Força (Ataque)", value="attack"),
        app_commands.Choice(
            name="✨ Agilidade (Atq. Especial)", value="special_attack"
        ),
        app_commands.Choice(name="❤️ Vitalidade (HP)", value="hp"),
    ]
)
async def distribuir_pontos(
    i: Interaction, atributo: app_commands.Choice[str], quantidade: int
):
    player_data = get_player_data(i.user.id)
    available_points = player_data.get("attribute_points", 0)
    if quantidade <= 0:
        await i.response.send_message("A quantidade deve ser positiva.", ephemeral=True)
        return
    if available_points < quantidade:
        await i.response.send_message(
            f"Você só tem {available_points} pontos.", ephemeral=True
        )
        return
    player_data["attribute_points"] -= quantidade
    if atributo.value == "attack":
        player_data["base_attack"] += quantidade * 2
    elif atributo.value == "special_attack":
        player_data["base_special_attack"] += quantidade * 3
    elif atributo.value == "hp":
        player_data["max_hp"] += quantidade * 5
        player_data["hp"] += quantidade * 5
    save_data()
    await i.response.send_message(
        embed=Embed(
            title="📈 Atributos Aprimorados",
            description=f"Você investiu **{quantidade}** pontos em **{atributo.name}**.",
            color=Color.green(),
        )
    )


@bot.tree.command(
    name="ranking", description="Mostra o ranking de MVPs (Mais Abates) do servidor."
)
async def ranking(i: Interaction):
    if not player_database:
        await i.response.send_message(
            "Nenhum jogador no ranking ainda.", ephemeral=True
        )
        return

    guild_members = {member.id: member for member in i.guild.members}

    sorted_players = sorted(
        player_database.values(), key=lambda p: p.get("kills", 0), reverse=True
    )

    embed = Embed(
        title="🏆 Ranking de MVPs - OUTLAWS 🏆",
        description="Os fora-da-lei mais temidos do servidor.",
        color=Color.gold(),
    )

    rank_entries = []
    for idx, player_data in enumerate(sorted_players[:10]):
        # Safely get the user_id from the player_data dict
        player_id_str = next(
            (
                uid
                for uid, p_data_val in player_database.items()
                if p_data_val == player_data
            ),
            None,
        )

        if player_id_str:
            player_id = int(player_id_str)
            member = guild_members.get(player_id)

            player_display_name = (
                member.display_name
                if member
                else player_data.get("name", "Desconhecido")
            )

            avatar_url = (
                member.avatar.url
                if member and member.avatar
                else "https://discord.com/assets/f9bb9c17af1b5c2a048a1d13f9c646f8.png"
            )

            rank_entries.append(
                f"**{idx+1}.** [{player_display_name}]({avatar_url})\n"
                f"  **Abates:** {player_data.get('kills', 0)} | "
                f"**Mortes:** {player_data.get('deaths', 0)} | "
                f"**Recompensa:** ${player_data.get('bounty', 0)}"
            )

    if rank_entries:
        embed.description = "\n\n".join(rank_entries)
    else:
        embed.description = "Nenhum jogador no ranking ainda."

    embed.set_footer(text="A glória aguarda os mais audazes!")
    await i.response.send_message(embed=embed)


## Comandos de Ação no Mundo
@bot.tree.command(
    name="viajar", description="Viaja para uma nova localização no mundo de OUTLAWS."
)
@app_commands.check(check_player_exists)
async def viajar(i: Interaction):
    player_data = get_player_data(i.user.id)
    current_location = player_data.get("location", STARTING_LOCATION)
    view = TravelView(current_location, i.user.id)
    if not view.children:
        await i.response.send_message(
            "Não há para onde viajar a partir daqui.", ephemeral=True
        )
        return
    embed = Embed(
        title="✈️ Para Onde Vamos?",
        description=f"Você está em **{current_location}**. Escolha seu próximo destino.",
        color=Color.blue(),
    )
    await i.response.send_message(embed=embed, view=view)


@bot.tree.command(
    name="trabalhar",
    description="Faça um trabalho na cidade para ganhar dinheiro e XP.",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_city)
async def trabalhar(i: Interaction):
    player_data = get_player_data(i.user.id)
    now, cooldown_key, last_work = (
        datetime.now().timestamp(),
        "work_cooldown",
        player_data["cooldowns"].get("work_cooldown", 0),
    )
    if now - last_work < 30:
        await i.response.send_message(
            f"Você já trabalhou recentemente.", ephemeral=True
        )
        return
    job = random.choice(
        [
            {"name": "Contrabando", "money": random.randint(40, 60), "xp": 20},
            {"name": "Punga", "money": random.randint(20, 80), "xp": 30},
            {"name": "Segurança Particular", "money": random.randint(50, 55), "xp": 25},
        ]
    )

    money_gain_raw = job["money"]
    xp_gain_raw = job["xp"]

    if player_data.get("money_double") is True:
        money_gain = money_gain_raw * 2
        money_message = f"**${money_gain}** (duplicado!)"
    else:
        money_gain = money_gain_raw
        money_message = f"**${money_gain}**"

    # Apply passive XP bonus from Habilidade Inata first
    xp_multiplier_passive = ITEMS_DATA.get("habilidade_inata", {}).get(
        "xp_multiplier_passive", 0.0
    )

    if player_data.get("style") == "Habilidade Inata" and xp_multiplier_passive > 0:
        xp_gain_raw = int(xp_gain_raw * (1 + xp_multiplier_passive))

    if player_data.get("xptriple") is True:
        xp_gain = xp_gain_raw * 3
        xp_message = f"e **{xp_gain}** XP (triplicado!)"
    else:
        xp_gain = xp_gain_raw
        xp_message = f"✨ +{xp_gain} XP"

    if (
        player_data.get("style") == "Habilidade Inata"
        and xp_multiplier_passive > 0
        and not player_data.get("xptriple")
    ):
        xp_message += f" (Habilidade Inata: +{int(xp_multiplier_passive*100)}%!)"
    elif (
        player_data.get("style") == "Habilidade Inata"
        and xp_multiplier_passive > 0
        and player_data.get("xptriple")
    ):
        xp_message = f"e **{xp_gain}** XP (triplicado + Habilidade Inata: +{int(xp_multiplier_passive*100)}%!)"

    player_data["money"] += money_gain
    player_data["xp"] += xp_gain
    player_data["cooldowns"][cooldown_key] = now
    embed = Embed(
        title="💰 Bico Concluído!",
        description=f"Você realizou um trabalho de **{job['name']}**.",
        color=Color.dark_gold(),
    )
    embed.add_field(
        name="Recompensa", value=f"Você ganhou {money_message} {xp_message}."
    )
    save_data()
    await i.response.send_message(embed=embed)
    await check_and_process_levelup(i.user, player_data, i)


@bot.tree.command(
    name="loja", description="Mostra os itens disponíveis para compra na cidade."
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_city)
async def loja(i: Interaction):
    embed = Embed(
        title="🛒 Loja OUTLAWS 🛒",
        description="Itens para te ajudar em sua jornada.",
        color=Color.dark_teal(),
    )
    # Safely get item data
    potion_info = ITEMS_DATA.get("pocao", {})
    super_potion_info = ITEMS_DATA.get("super_pocao", {})
    invoker_info = ITEMS_DATA.get("invocador", {})
    healer_staff_info = ITEMS_DATA.get("cajado_curandeiro", {})
    fighter_gauntlet_info = ITEMS_DATA.get("manopla_lutador", {})
    shooter_sight_info = ITEMS_DATA.get("mira_semi_automatica", {})
    ghost_sword_info = ITEMS_DATA.get("espada_fantasma", {})
    dracula_blessing_info = ITEMS_DATA.get("bencao_dracula", {})

    if potion_info:
        embed.add_field(
            name=f"{potion_info.get('emoji', '❔')} Poção de Vida (ID: `pocao`)",
            value=f"Restaura {potion_info.get('heal', 0)} HP. Custa **${potion_info.get('price', 0)}**.",
            inline=False,
        )
    if super_potion_info:
        embed.add_field(
            name=f"{super_potion_info.get('emoji', '❔')} Super Poção (ID: `super_pocao`)",
            value=f"Restaura {super_potion_info.get('heal', 0)} HP. Custa **${super_potion_info.get('price', 0)}**.",
            inline=False,
        )
    if invoker_info:
        embed.add_field(
            name=f"{invoker_info.get('emoji', '❔')} Invocador do Colosso (ID: `invocador`)",
            value=f"Invoca o terrível boss. Custa **${invoker_info.get('price', 0)}**.",
            inline=False,
        )
    embed.add_field(name="\u200b", value="\u200b", inline=False)  # Separator

    if healer_staff_info:
        embed.add_field(
            name=f"{healer_staff_info.get('emoji', '❔')} {healer_staff_info.get('name', 'Cajado do Curandeiro')} (ID: `cajado_curandeiro`)",
            value=f"[Curandeiro] Aumenta a cura em {int(healer_staff_info.get('effect_multiplier', 1.0) * 100 - 100)}%. Custa **${healer_staff_info.get('price', 0)}**.",
            inline=False,
        )
    if fighter_gauntlet_info:
        embed.add_field(
            name=f"{fighter_gauntlet_info.get('emoji', '❔')} {fighter_gauntlet_info.get('name', 'Manopla do Lutador')} (ID: `manopla_lutador`)",
            value=f"[Lutador] Aumenta ataque base em {int(fighter_gauntlet_info.get('attack_bonus_percent', 0.0) * 100)}% e vida máxima em {fighter_gauntlet_info.get('hp_bonus_flat', 0)}. Custa **${fighter_gauntlet_info.get('price', 0)}**.",
            inline=False,
        )
    if shooter_sight_info:
        embed.add_field(
            name=f"{shooter_sight_info.get('emoji', '❔')} {shooter_sight_info.get('name', 'Mira Semi-Automatica')} (ID: `mira_semi_automatica`)",
            value=f"[Atirador] Reduz o cooldown do Ataque Especial em {int(shooter_sight_info.get('cooldown_reduction_percent', 0.0) * 100)}%. Custa **${shooter_sight_info.get('price', 0)}**.",
            inline=False,
        )
    if ghost_sword_info:
        embed.add_field(
            name=f"{ghost_sword_info.get('emoji', '❔')} {ghost_sword_info.get('name', 'Espada Fantasma')} (ID: `espada_fantasma`)",
            value=f"[Espadachim] Concede +{int(ghost_sword_info.get('attack_bonus_percent', 0.0) * 100)}% de ataque, mas penaliza -{int(ghost_sword_info.get('hp_penalty_percent', 0.0) * 100)}% do HP total. Custa **${ghost_sword_info.get('price', 0)}**.",
            inline=False,
        )
    if dracula_blessing_info:
        embed.add_field(
            name=f"{dracula_blessing_info.get('emoji', '❔')} Desbloquear {dracula_blessing_info.get('name', 'Bênção de Drácula')}",
            value=f"[Vampiro] Desbloqueia a transformação temporária que desvia ataques e suga HP. Custa **${dracula_blessing_info.get('price', 0)}**.",
            inline=False,
        )
    await i.response.send_message(embed=embed, view=ShopView())


@bot.tree.command(
    name="aprimorar",
    description="Gaste dinheiro para fortalecer seus ataques na cidade.",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_city)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name="💪 Força (Ataque)", value="attack"),
        app_commands.Choice(
            name="✨ Agilidade (Atq. Especial)", value="special_attack"
        ),
    ]
)
async def aprimorar(i: Interaction, atributo: app_commands.Choice[str]):
    player_data = get_player_data(i.user.id)
    attr_key = f"base_{atributo.value}"

    base_stat_current = player_data[attr_key]

    cost_per_point = 20
    initial_base = INITIAL_ATTACK if "attack" in attr_key else INITIAL_SPECIAL_ATTACK
    cost = 100 + (base_stat_current - initial_base) * cost_per_point

    if player_data["money"] < cost:
        await i.response.send_message(
            f"Você precisa de ${cost} para aprimorar.", ephemeral=True
        )
        return

    player_data["money"] -= cost
    player_data[attr_key] += 2
    save_data()

    next_cost_increase = 2 * cost_per_point
    await i.response.send_message(
        f"✨ Aprimoramento concluído! Seu {atributo.name} base aumentou para `{player_data[attr_key]}`. Próximo aprimoramento custará ${cost + next_cost_increase}."
    )


## Comandos de Combate e Habilidades
@bot.tree.command(
    name="cacar",
    description="Caça uma criatura na sua localização atual (combate por turnos).",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_wilderness)
async def cacar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["status"] == "dead":
        await i.response.send_message("Mortos não caçam.", ephemeral=True)
        return

    await i.response.defer()  # Defer the response immediately

    location = player_data.get("location")
    enemy_template = random.choice(ENEMIES[location])
    enemy = enemy_template.copy()
    await run_turn_based_combat(i, player_data, enemy)


@bot.tree.command(
    name="batalhar",
    description="Enfrenta um Ex-Cavaleiro para testar sua força (combate por turnos).",
)
@app_commands.check(check_player_exists)
@app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
@app_commands.describe(
    primeiro_ataque="Escolha seu ataque inicial: Básico ou Especial."
)
@app_commands.choices(
    primeiro_ataque=[
        app_commands.Choice(name="Ataque Básico", value="basico"),
        app_commands.Choice(name="Ataque Especial", value="especial"),
    ]
)
async def batalhar(i: Interaction, primeiro_ataque: app_commands.Choice[str]):
    player_data = get_player_data(i.user.id)
    if player_data["status"] == "dead":
        await i.response.send_message("Mortos não batalham.", ephemeral=True)
        return

    if primeiro_ataque.value == "especial":
        # Adjust energy cost for Aura Blessing and Atirador transformation if active
        cooldown_cost = TRANSFORM_COST
        if (
            player_data.get("aura_blessing_active")
            and "bencao_rei_henrique" in ITEMS_DATA
        ):
            cooldown_reduction_percent = ITEMS_DATA["bencao_rei_henrique"][
                "cooldown_reduction_percent"
            ]
            cooldown_cost = max(
                1, int(cooldown_cost * (1 - cooldown_reduction_percent))
            )
        if (
            player_data.get("is_transformed")
            and player_data["class"] == "Atirador"
            and "cooldown_reduction_percent" in CLASS_TRANSFORMATIONS["Atirador"]
        ):
            cooldown_reduction_percent = CLASS_TRANSFORMATIONS["Atirador"][
                "cooldown_reduction_percent"
            ]
            cooldown_cost = max(
                1, int(cooldown_cost * (1 - cooldown_reduction_percent))
            )

        if player_data.get("energy", 0) < cooldown_cost:
            await i.response.send_message(
                f"Você não tem energia suficiente ({cooldown_cost}) para um Ataque Especial inicial! Use Ataque Básico ou recupere energia.",
                ephemeral=True,
            )
            return

    await i.response.defer()  # Defer the response immediately

    enemy = {
        "name": "Ex-Cavaleiro Renegado",
        "hp": 320,
        "attack": 95,
        "xp": 390,
        "money": 400,
        "thumb": "https://c.tenor.com/ebFt6wJWEu8AAAAC/tenor.gif",
    }
    await run_turn_based_combat(i, player_data, enemy, primeiro_ataque.value)


@bot.tree.command(name="atacar", description="Ataca outro jogador em um duelo.")
@app_commands.check(check_player_exists)
@app_commands.describe(
    alvo="O jogador que você quer atacar.", estilo="O tipo de ataque a ser usado."
)
@app_commands.choices(
    estilo=[
        app_commands.Choice(name="Ataque Básico", value="basico"),
        app_commands.Choice(name="Ataque Especial", value="especial"),
    ]
)
async def atacar(
    i: Interaction, alvo: discord.Member, estilo: app_commands.Choice[str]
):
    attacker_id, target_id = str(i.user.id), str(alvo.id)
    if attacker_id == target_id:
        await i.response.send_message(
            "Você não pode atacar a si mesmo!", ephemeral=True
        )
        return

    raw_attacker_data = get_player_data(attacker_id)
    raw_target_data = get_player_data(target_id)

    if not raw_target_data:
        await i.response.send_message("Este jogador não tem uma ficha!", ephemeral=True)
        return
    if raw_attacker_data["status"] == "dead" or raw_target_data["status"] == "dead":
        await i.response.send_message("Um dos jogadores está morto.", ephemeral=True)
        return

    # Ensure they are in the same location for PvP, or remove this check if you want global PvP
    if raw_attacker_data.get("location") != raw_target_data.get("location"):
        await i.response.send_message(
            "Você precisa estar na mesma localização para atacar outro jogador!",
            ephemeral=True,
        )
        return

    attacker_stats = calculate_effective_stats(raw_attacker_data)
    target_stats = calculate_effective_stats(raw_target_data)

    now = datetime.now().timestamp()
    cooldown_key = f"{estilo.value}_attack_cooldown"
    cooldown_duration = 10 if estilo.value == "basico" else 30

    # Apply Aura Blessing cooldown reduction
    if (
        raw_attacker_data.get("aura_blessing_active")
        and "bencao_rei_henrique" in ITEMS_DATA
    ):
        cooldown_duration = int(
            cooldown_duration
            * (1 - ITEMS_DATA["bencao_rei_henrique"]["cooldown_reduction_percent"])
        )
    # Apply Atirador transformation cooldown reduction
    if (
        raw_attacker_data.get("is_transformed")
        and raw_attacker_data["class"] == "Atirador"
        and "cooldown_reduction_percent" in CLASS_TRANSFORMATIONS["Atirador"]
    ):
        cooldown_duration = int(
            cooldown_duration
            * (1 - CLASS_TRANSFORMATIONS["Atirador"]["cooldown_reduction_percent"])
        )

    if now - raw_attacker_data["cooldowns"].get(cooldown_key, 0) < cooldown_duration:
        await i.response.send_message(
            f"Seu {estilo.name} está em cooldown! Tente novamente em **{cooldown_duration - (now - raw_attacker_data['cooldowns'].get(cooldown_key, 0)):.2f}s**.",
            ephemeral=True,
        )
        return

    damage = (
        random.randint(
            attacker_stats["attack"] // 2, int(attacker_stats["attack"] * 1.2)
        )
        if estilo.value == "basico"
        else random.randint(
            int(attacker_stats["special_attack"] * 0.8),
            int(attacker_stats["special_attack"] * 1.5),
        )
    )
    crit_msg = ""
    if random.random() < CRITICAL_CHANCE:
        damage = int(damage * CRITICAL_MULTIPLIER)
        crit_msg = "💥 **ACERTO CRÍTICO!** "

    # Vampire's basic attack heal (PvP)
    heal_info_msg = ""
    if raw_attacker_data["class"] == "Vampiro":
        if estilo.value == "basico":
            heal_amount = int(damage * 0.5)
            raw_attacker_data["hp"] = min(
                raw_attacker_data["max_hp"],
                raw_attacker_data["hp"] + heal_amount,
            )
            heal_info_msg = (
                f" (🩸 Você sugou `{heal_amount}` HP de {alvo.display_name}!)"
            )
        elif estilo.value == "especial":
            heal_amount = int(damage * 0.75)
            raw_attacker_data["hp"] = min(
                raw_attacker_data["max_hp"],
                raw_attacker_data["hp"] + heal_amount,
            )
            heal_info_msg = f" (🧛 Você sugou `{heal_amount}` HP de {alvo.display_name} com seu ataque especial!)"

    # Apply damage to the target (before evasion/amulet check for initial damage value)
    initial_target_hp = raw_target_data["hp"]
    raw_target_data["hp"] -= damage

    embed = Embed(color=Color.red())

    # Lógica da Bênção de Drácula em PvP (para o ALVO que está sendo atacado)
    # Check if target would die OR is currently below 0
    if raw_target_data["hp"] <= 0:
        if (
            raw_target_data["class"] == "Vampiro"
            and raw_target_data.get("bencao_dracula_active", False)
            and "bencao_dracula" in ITEMS_DATA
            and random.random() < ITEMS_DATA["bencao_dracula"]["evasion_chance"]
        ):
            hp_stolen_on_evade = int(
                damage * ITEMS_DATA["bencao_dracula"]["hp_steal_percent_on_evade"]
            )
            # Restore HP to what it was before this attack, then add stolen HP
            raw_target_data["hp"] = min(
                target_stats["max_hp"], initial_target_hp + hp_stolen_on_evade
            )  # Healing is from the damage evaded

            embed.title = f"⚔️ Duelo de Fora-da-Lei ⚔️"
            embed.description = (
                f"{crit_msg}{i.user.display_name} usou **{estilo.name}** em {alvo.display_name} e causou **{damage}** de dano!{heal_info_msg}\n"
                f"👻 **DESVIADO!** {alvo.display_name} (Vampiro) ativou a Bênção de Drácula e sugou `{hp_stolen_on_evade}` HP!\n"
                f"{alvo.display_name} agora tem **{raw_target_data['hp']}/{target_stats['max_hp']}** HP."
            )
        elif raw_target_data["inventory"].get(
            "amuleto_de_pedra", 0
        ) > 0 and not raw_target_data.get("amulet_used_since_revive", False):
            raw_target_data["hp"] = 1
            raw_target_data["amulet_used_since_revive"] = True
            embed.title = f"⚔️ Duelo de Fora-da-Lei ⚔️"
            embed.description = (
                f"{crit_msg}{i.user.display_name} usou **{estilo.name}** em {alvo.display_name} e causou **{damage}** de dano!{heal_info_msg}\n"
                f"✨ **Amuleto de Pedra ativado!** {alvo.display_name} sobreviveu com 1 HP!\n"
                f"{alvo.display_name} agora tem **{raw_target_data['hp']}/{target_stats['max_hp']}** HP."
            )
        else:
            raw_target_data["hp"] = 0
            raw_target_data["status"] = "dead"
            raw_target_data["deaths"] += 1
            # Bounty is only reset if the player is defeated, not just for having a bounty.
            # Only transfer bounty if the target actually had one.
            bounty_claimed = raw_target_data.get("bounty", 0)
            raw_target_data["bounty"] = 0  # Reset target's bounty upon defeat

            money_stolen = int(raw_target_data["money"] * BOUNTY_PERCENTAGE)
            raw_attacker_data["money"] += money_stolen + bounty_claimed
            raw_attacker_data["kills"] += 1  # Attacker gets a kill
            raw_attacker_data[
                "bounty"
            ] += 100  # Attacker gets a bounty for defeating someone

            embed.title = (
                f"☠️ ABATE! {i.user.display_name} derrotou {alvo.display_name}!"
            )
            embed.description = f"{crit_msg}{i.user.display_name} usou **{estilo.name}** e causou **{damage}** de dano, finalizando o oponente.{heal_info_msg}\n\n"
            if bounty_claimed > 0:
                embed.description += (
                    f"Uma recompensa de **${bounty_claimed}** foi clamada!\n"
                )
            embed.description += f"**${money_stolen}** (20%) foram roubados.\n"
            embed.description += f"{i.user.display_name} agora tem uma recompensa de **${raw_attacker_data['bounty']}** por sua cabeça."
    else:  # Target did not die
        embed.title = f"⚔️ Duelo de Fora-da-Lei ⚔️"
        embed.description = f"{crit_msg}{i.user.display_name} usou **{estilo.name}** em {alvo.display_name} e causou **{damage}** de dano!{heal_info_msg}\n{alvo.display_name} agora tem **{raw_target_data['hp']}/{target_stats['max_hp']}** HP."

    raw_attacker_data["cooldowns"][
        cooldown_key
    ] = now  # Apply cooldown after the attack
    save_data()
    await i.response.send_message(embed=embed)


@bot.tree.command(
    name="atacar_boss", description="Ataca o boss global quando ele estiver ativo."
)
@app_commands.check(check_player_exists)
@app_commands.choices(
    estilo=[
        app_commands.Choice(name="Ataque Básico", value="basico"),
        app_commands.Choice(name="Ataque Especial", value="especial"),
    ]
)
async def atacar_boss(i: Interaction, estilo: app_commands.Choice[str]):
    if not BOSS_DATA["is_active"]:
        await i.response.send_message("Não há nenhum boss ativo.", ephemeral=True)
        return

    player_id = str(i.user.id)
    raw_player_data = get_player_data(player_id)

    if raw_player_data["status"] == "dead":
        await i.response.send_message(
            "Você não pode atacar o boss enquanto estiver morto.", ephemeral=True
        )
        return

    if player_id not in BOSS_DATA["participants"]:
        BOSS_DATA["participants"].append(player_id)

    now = datetime.now().timestamp()
    cooldown_key = f"boss_{estilo.value}_cooldown"
    cooldown_duration = 5 if estilo.value == "basico" else 15

    # Apply Aura Blessing cooldown reduction
    if (
        raw_player_data.get("aura_blessing_active")
        and "bencao_rei_henrique" in ITEMS_DATA
    ):
        cooldown_duration = int(
            cooldown_duration
            * (1 - ITEMS_DATA["bencao_rei_henrique"]["cooldown_reduction_percent"])
        )
    # Apply Atirador transformation cooldown reduction
    if (
        raw_player_data.get("is_transformed")
        and raw_player_data["class"] == "Atirador"
        and "cooldown_reduction_percent" in CLASS_TRANSFORMATIONS["Atirador"]
    ):
        cooldown_duration = int(
            cooldown_duration
            * (1 - CLASS_TRANSFORMATIONS["Atirador"]["cooldown_reduction_percent"])
        )

    last_attack = raw_player_data["cooldowns"].get(cooldown_key, 0)

    if now - last_attack < cooldown_duration:
        await i.response.send_message(
            f"Seu {estilo.name} contra o boss está em cooldown! Tente novamente em **{cooldown_duration - (now - last_attack):.2f}s**.",
            ephemeral=True,
        )
        return

    player_stats = calculate_effective_stats(raw_player_data)

    damage = (
        random.randint(player_stats["attack"], int(player_stats["attack"] * 1.5))
        if estilo.value == "basico"
        else random.randint(
            player_stats["special_attack"], int(player_stats["special_attack"] * 1.8)
        )
    )
    crit_msg = ""
    if random.random() < CRITICAL_CHANCE:
        damage = int(damage * CRITICAL_MULTIPLIER)
        crit_msg = "💥 **CRÍTICO!** "

    BOSS_DATA["hp"] -= damage
    raw_player_data["cooldowns"][cooldown_key] = now
    save_data()

    await i.response.send_message(
        f"{crit_msg}Você atacou o {BOSS_DATA['name']} e causou `{damage}` de dano! Vida restante: `{max(0, BOSS_DATA['hp'])}/{BOSS_DATA['max_hp']}`."
    )
    if BOSS_DATA["hp"] <= 0:
        embed = Embed(
            title=f"🎉 O {BOSS_DATA['name']} FOI DERROTADO! 🎉",
            description="Recompensas foram distribuídas!",
            color=Color.green(),
        )
        # Check if channel_id is valid before sending
        if BOSS_DATA["channel_id"]:
            boss_channel = bot.get_channel(BOSS_DATA["channel_id"])
            if boss_channel:
                await boss_channel.send(embed=embed)
        else:
            await i.channel.send(
                embed=embed
            )  # Fallback to current channel if boss channel not set

        for p_id in BOSS_DATA["participants"]:
            if p_data := get_player_data(p_id):
                boss_money_raw = 5000
                if p_data.get("money_double") is True:
                    boss_money = boss_money_raw * 2
                else:
                    boss_money = boss_money_raw
                p_data["money"] += boss_money

                boss_xp_raw = 1000
                # Apply passive XP bonus from Habilidade Inata first
                xp_multiplier_passive = ITEMS_DATA.get("habilidade_inata", {}).get(
                    "xp_multiplier_passive", 0.0
                )

                if (
                    p_data.get("style") == "Habilidade Inata"
                    and xp_multiplier_passive > 0
                ):
                    boss_xp_raw = int(boss_xp_raw * (1 + xp_multiplier_passive))

                if p_data.get("xptriple") is True:
                    boss_xp = boss_xp_raw * 3
                else:
                    boss_xp = boss_xp_raw

                p_data["xp"] += boss_xp

                for item_drop, quantity_drop in BOSS_DATA.get("drops", {}).items():
                    if item_drop == "amuleto_de_pedra":
                        if p_data["inventory"].get("amuleto_de_pedra", 0) == 0:
                            p_data["inventory"]["amuleto_de_pedra"] = 1
                    else:
                        p_data["inventory"][item_drop] = (
                            p_data["inventory"].get(item_drop, 0) + quantity_drop
                        )

                await check_and_process_levelup(
                    bot.get_user(int(p_id)) or i.user, p_data, i
                )  # Pass the actual user object or fallback
        BOSS_DATA.update(
            {"is_active": False, "hp": 0, "participants": [], "channel_id": None}
        )
        save_data()


@bot.tree.command(name="usar", description="Usa um item do seu inventário.")
@app_commands.check(check_player_exists)
async def usar(i: Interaction, item_id: str):
    item_id = item_id.lower()
    raw_player_data = get_player_data(i.user.id)

    if (
        item_id not in raw_player_data["inventory"]
        or raw_player_data["inventory"][item_id] < 1
    ):
        await i.response.send_message("Você não possui este item!", ephemeral=True)
        return

    item_info = ITEMS_DATA.get(item_id)
    if not item_info:
        await i.response.send_message("Este item não é reconhecido.", ephemeral=True)
        return

    # Check if item is an equipable item that gives passive bonuses (and shouldn't be "used")
    if item_id in [
        "cajado_curandeiro",
        "manopla_lutador",
        "mira_semi_automatica",
        "espada_fantasma",
        "amuleto_de_pedra",
    ]:
        await i.response.send_message(
            f"Você tem o(a) **{item_info['name']}** no seu inventário! Seus efeitos são aplicados automaticamente.",
            ephemeral=True,
        )
        return

    # Check if item is a blessing unlock (and shouldn't be "used" after purchase)
    if item_id in ["bencao_dracula", "bencao_rei_henrique"]:
        await i.response.send_message(
            f"Você já desbloqueou a **{item_info['name']}**! Use `/transformar` ou `/ativar_bencao_aura` para ativá-la.",
            ephemeral=True,
        )
        return

    if item_id == "pocao":
        raw_player_data["hp"] = min(
            raw_player_data["max_hp"], raw_player_data["hp"] + item_info["heal"]
        )
        raw_player_data["inventory"]["pocao"] -= 1
        await i.response.send_message(
            f"{item_info['emoji']} Você usou uma poção e recuperou {item_info['heal']} HP! Vida atual: `{raw_player_data['hp']}/{raw_player_data['max_hp']}`."
        )
    elif item_id == "super_pocao":
        raw_player_data["hp"] = min(
            raw_player_data["max_hp"], raw_player_data["hp"] + item_info["heal"]
        )
        raw_player_data["inventory"]["super_pocao"] -= 1
        await i.response.send_message(
            f"{item_info['emoji']} Você usou uma Super Poção e recuperou {item_info['heal']} HP! Vida atual: `{raw_player_data['hp']}/{raw_player_data['max_hp']}`."
        )
    elif item_id == "invocador":
        if BOSS_DATA["is_active"]:
            await i.response.send_message("O Colosso já está ativo!", ephemeral=True)
            return
        raw_player_data["inventory"]["invocador"] -= 1
        BOSS_DATA.update(
            {
                "is_active": True,
                "hp": BOSS_DATA["max_hp"],
                "participants": [str(i.user.id)],
                "channel_id": i.channel.id,
            }
        )
        embed = Embed(
            title=f"{item_info['emoji']} O {BOSS_DATA['name']} APARECEU! {item_info['emoji']}",
            description=f"Invocado por **{i.user.display_name}**! Usem `/atacar_boss`!",
            color=Color.dark_red(),
        )
        embed.add_field(
            name="Vida do Boss", value=f"`{BOSS_DATA['hp']}/{BOSS_DATA['max_hp']}`"
        ).set_thumbnail(url="https://c.tenor.com/TgVgrdOEIIYAAAAd/tenor.gif")
        await i.response.send_message(embed=embed)

    # Only decrement inventory count for consumable items
    if item_id in ["pocao", "super_pocao", "invocador"]:
        if raw_player_data["inventory"].get(item_id) == 0:
            del raw_player_data["inventory"][item_id]
    save_data()


@bot.tree.command(
    name="curar",
    description="[Curandeiro] Usa seus poderes para restaurar a vida de um alvo.",
)
@app_commands.check(check_player_exists)
async def curar(i: Interaction, alvo: discord.Member):
    raw_player_data = get_player_data(i.user.id)
    player_stats = calculate_effective_stats(raw_player_data)

    if raw_player_data["class"] != "Curandeiro":
        await i.response.send_message(
            "Apenas Curandeiros podem usar este comando.", ephemeral=True
        )
        return

    raw_target_data = get_player_data(alvo.id)
    if not raw_target_data:
        await i.response.send_message(
            f"{alvo.display_name} não possui uma ficha.", ephemeral=True
        )
        return

    target_stats = calculate_effective_stats(raw_target_data)

    now, cooldown_key, last_heal = (
        datetime.now().timestamp(),
        "heal_cooldown",
        raw_player_data["cooldowns"].get("heal_cooldown", 0),
    )

    # Apply Aura Blessing cooldown reduction
    cooldown_healing = 45  # Base cooldown
    if (
        raw_player_data.get("aura_blessing_active")
        and "bencao_rei_henrique" in ITEMS_DATA
    ):
        cooldown_healing = int(
            cooldown_healing
            * (1 - ITEMS_DATA["bencao_rei_henrique"]["cooldown_reduction_percent"])
        )

    if now - last_heal < cooldown_healing:
        await i.response.send_message(
            f"Sua cura está em cooldown! Tente novamente em **{cooldown_healing - (now - last_heal):.2f}s**.",
            ephemeral=True,
        )
        return

    heal_amount = random.randint(
        int(player_stats["special_attack"] * 1.5),
        int(player_stats["special_attack"] * 2.5),
    )

    # Apply Curandeiro item/transformation bonuses to healing
    if player_stats.get("healing_multiplier", 1.0) > 1.0:
        heal_amount = int(heal_amount * player_stats["healing_multiplier"])

    original_hp = raw_target_data["hp"]
    raw_target_data["hp"] = min(
        raw_target_data["max_hp"], raw_target_data["hp"] + heal_amount
    )
    healed_for = raw_target_data["hp"] - original_hp

    raw_player_data["cooldowns"][cooldown_key] = now

    embed = Embed(title="✨ Bênção Vital ✨", color=Color.from_rgb(139, 212, 181))
    if i.user.id == alvo.id:
        embed.description = (
            f"Você se concentrou e curou a si mesmo em **{healed_for}** HP."
        )
    else:
        embed.description = (
            f"Você usou seus poderes para curar {alvo.mention} em **{healed_for}** HP."
        )
    embed.set_footer(
        text=f"Vida de {alvo.display_name}: {raw_target_data['hp']}/{target_stats['max_hp']}"
    )
    save_data()
    await i.response.send_message(embed=embed)


@bot.tree.command(
    name="transformar",
    description="Usa sua energia para entrar em um estado mais poderoso ou na Benção da Aura.",
)
@app_commands.choices(
    forma=[
        app_commands.Choice(name="Lâmina Fantasma (Espadachim)", value="esp_transform"),
        app_commands.Choice(name="Punho de Aço (Lutador)", value="lut_transform"),
        app_commands.Choice(name="Olho de Águia (Atirador)", value="ati_transform"),
        app_commands.Choice(name="Bênção Vital (Curandeiro)", value="cur_transform"),
        app_commands.Choice(name="Lorde Sanguinário (Vampiro)", value="vamp_transform"),
        app_commands.Choice(name="Bênção de Drácula (Vampiro)", value="bencao_dracula"),
    ]
)
@app_commands.check(check_player_exists)
async def transformar(i: Interaction, forma: app_commands.Choice[str]):
    raw_player_data = get_player_data(i.user.id)
    player_class = raw_player_data["class"]
    player_style = raw_player_data["style"]

    # Check if a class transformation is already active
    if raw_player_data.get("is_transformed") and forma.value.endswith("_transform"):
        await i.response.send_message(
            f"Você já está na forma {raw_player_data.get('transform_name', 'transformada')}! Use `/destransformar` para retornar ao normal.",
            ephemeral=True,
        )
        return

    # Handle class-specific transformations
    if forma.value.endswith("_transform"):
        target_class = {
            "esp_transform": "Espadachim",
            "lut_transform": "Lutador",
            "ati_transform": "Atirador",
            "cur_transform": "Curandeiro",
            "vamp_transform": "Vampiro",
        }.get(forma.value)

        if player_class != target_class:
            await i.response.send_message(
                f"Essa transformação é exclusiva para a classe **{target_class}**.",
                ephemeral=True,
            )
            return

        transform_info = CLASS_TRANSFORMATIONS.get(player_class)
        if not transform_info:
            await i.response.send_message(
                "Dados de transformação não encontrados para sua classe.",
                ephemeral=True,
            )
            return

        if raw_player_data["energy"] < transform_info["cost_energy"]:
            await i.response.send_message(
                f"Energia insuficiente para se transformar em {transform_info['name']} ({transform_info['cost_energy']} energia)!",
                ephemeral=True,
            )
            return

        raw_player_data["is_transformed"] = True
        raw_player_data["transform_end_time"] = (
            datetime.now().timestamp() + transform_info["duration_seconds"]
        )
        raw_player_data["energy"] -= transform_info["cost_energy"]

        embed = Embed(
            title=f"{transform_info['emoji']} TRANSFORMAÇÃO: {transform_info['name']} {transform_info['emoji']}",
            description=f"{i.user.display_name} liberou seu poder oculto e se tornou um(a) {transform_info['name']} por {transform_info['duration_seconds'] // 60} minutos!",
            color=Color.dark_red() if player_class == "Vampiro" else Color.gold(),
        )
        await i.response.send_message(embed=embed)
        save_data()
        return

    # Handle Bênção de Drácula transformation (already in original code)
    elif forma.value == "bencao_dracula":
        if player_class != "Vampiro":
            await i.response.send_message(
                "Somente Vampiros podem ativar a Bênção de Drácula.", ephemeral=True
            )
            return
        if raw_player_data["inventory"].get("bencao_dracula", 0) == 0:
            await i.response.send_message(
                "Você não desbloqueou a Bênção de Drácula! Compre-a na loja primeiro.",
                ephemeral=True,
            )
            return
        if raw_player_data.get("bencao_dracula_active"):
            await i.response.send_message(
                "A Bênção de Drácula já está ativa!", ephemeral=True
            )
            return

        dracula_info = ITEMS_DATA.get("bencao_dracula")
        if not dracula_info:  # Safety check
            await i.response.send_message(
                "Dados da Bênção de Drácula não encontrados.", ephemeral=True
            )
            return

        if raw_player_data["energy"] < dracula_info["cost_energy"]:
            await i.response.send_message(
                f"Energia insuficiente para a {dracula_info['name']} ({dracula_info['cost_energy']} energia)!",
                ephemeral=True,
            )
            return

        raw_player_data["bencao_dracula_active"] = True
        raw_player_data["energy"] -= dracula_info["cost_energy"]
        raw_player_data["bencao_dracula_end_time"] = (
            datetime.now().timestamp() + dracula_info["duration_seconds"]
        )

        embed = Embed(
            title=f"{dracula_info['emoji']} {dracula_info['name']}! {dracula_info['emoji']}",
            description=f"{i.user.display_name} invocou a bênção sombria de Drácula!\n"
            f"Você agora tem uma chance de desviar e sugar vida por {dracula_info['duration_seconds'] // 60} minutos!",
            color=Color.dark_purple(),
        )
        embed.set_thumbnail(url="https://c.tenor.com/A6j4yvK8J-oAAAAC/tenor.gif")
        await i.response.send_message(embed=embed)
        save_data()
        return

    await i.response.send_message(
        "Forma de transformação não reconhecida ou não disponível para sua classe/estilo.",
        ephemeral=True,
    )


@bot.tree.command(
    name="destransformar", description="Retorna à sua forma normal e recupera energia."
)
@app_commands.choices(
    forma=[
        app_commands.Choice(name="Lâmina Fantasma (Espadachim)", value="esp_transform"),
        app_commands.Choice(name="Punho de Aço (Lutador)", value="lut_transform"),
        app_commands.Choice(name="Olho de Águia (Atirador)", value="ati_transform"),
        app_commands.Choice(name="Bênção Vital (Curandeiro)", value="cur_transform"),
        app_commands.Choice(name="Lorde Sanguinário (Vampiro)", value="vamp_transform"),
        app_commands.Choice(name="Benção do Rei Henrique (Aura)", value="bencao_aura"),
        app_commands.Choice(name="Bênção de Drácula (Vampiro)", value="bencao_dracula"),
        app_commands.Choice(name="Todas as Transformações", value="all"),
    ]
)
@app_commands.check(check_player_exists)
async def destransformar(i: Interaction, forma: app_commands.Choice[str]):
    raw_player_data = get_player_data(i.user.id)
    deactivated_any = False
    messages = []  # Collect messages to send in one response

    if forma.value == "all":
        if raw_player_data.get("is_transformed"):
            raw_player_data["is_transformed"] = False
            raw_player_data["transform_end_time"] = 0
            deactivated_any = True
            messages.append(
                f"Você retornou à sua forma normal de {raw_player_data['class']}."
            )
        if raw_player_data.get("aura_blessing_active"):
            raw_player_data["aura_blessing_active"] = False
            raw_player_data["aura_blessing_end_time"] = 0
            deactivated_any = True
            messages.append(
                f"A {ITEMS_DATA.get('bencao_rei_henrique',{}).get('name', 'Bênção da Aura')} foi desativada."
            )
        if raw_player_data.get("bencao_dracula_active"):
            raw_player_data["bencao_dracula_active"] = False
            raw_player_data["bencao_dracula_end_time"] = 0
            deactivated_any = True
            messages.append(
                f"A {ITEMS_DATA.get('bencao_dracula',{}).get('name', 'Bênção de Drácula')} foi desativada."
            )

        if deactivated_any:
            raw_player_data["energy"] = min(MAX_ENERGY, raw_player_data["energy"] + 1)
            save_data()
            messages.append("Você recuperou 1 de energia.")
            await i.response.send_message("\n".join(messages))
        else:
            await i.response.send_message(
                "Você não tem nenhuma transformação ativa para desativar.",
                ephemeral=True,
            )
        return

    if forma.value.endswith("_transform"):
        if not raw_player_data.get("is_transformed"):
            await i.response.send_message(
                "Você não está em uma transformação de classe ativa.", ephemeral=True
            )
            return
        # Check if the requested transformation matches the currently active one (by class)
        if forma.value == {
            "Espadachim": "esp_transform",
            "Lutador": "lut_transform",
            "Atirador": "ati_transform",
            "Curandeiro": "cur_transform",
            "Vampiro": "vamp_transform",
        }.get(raw_player_data["class"]):
            raw_player_data["is_transformed"] = False
            raw_player_data["transform_end_time"] = 0
            deactivated_any = True
            messages.append(
                f"Você retornou à sua forma normal ({raw_player_data['class']})."
            )
        else:
            await i.response.send_message(
                "A transformação que você tentou desativar não é a sua transformação de classe atual.",
                ephemeral=True,
            )
            return

    elif forma.value == "bencao_aura":
        if not raw_player_data.get("aura_blessing_active"):
            await i.response.send_message(
                "A Benção do Rei Henrique não está ativa.", ephemeral=True
            )
            return
        raw_player_data["aura_blessing_active"] = False
        raw_player_data["aura_blessing_end_time"] = 0
        deactivated_any = True
        messages.append(
            f"A {ITEMS_DATA.get('bencao_rei_henrique',{}).get('name', 'Bênção da Aura')} foi desativada."
        )
    elif forma.value == "bencao_dracula":
        if not raw_player_data.get("bencao_dracula_active"):
            await i.response.send_message(
                "A Bênção de Drácula não está ativa.", ephemeral=True
            )
            return
        raw_player_data["bencao_dracula_active"] = False
        raw_player_data["bencao_dracula_end_time"] = 0
        deactivated_any = True
        messages.append(
            f"A {ITEMS_DATA.get('bencao_dracula',{}).get('name', 'Bênção de Drácula')} foi desativada."
        )

    if deactivated_any:
        raw_player_data["energy"] = min(MAX_ENERGY, raw_player_data["energy"] + 1)
        save_data()
        messages.append("Você recuperou 1 de energia.")
        await i.response.send_message("\n".join(messages))
    else:
        await i.response.send_message(
            "Não foi possível desativar a transformação solicitada.", ephemeral=True
        )


## Novo comando para ativar a Benção da Aura
@bot.tree.command(
    name="ativar_bencao_aura",
    description="[Aura] Ativa a Benção do Rei Henrique, concedendo bônus temporários.",
)
@app_commands.check(check_player_exists)
async def ativar_bencao_aura(i: Interaction):
    raw_player_data = get_player_data(i.user.id)
    if raw_player_data["style"] != "Aura":
        await i.response.send_message(
            "Somente usuários de Aura podem invocar a Benção do Rei Henrique.",
            ephemeral=True,
        )
        return
    if raw_player_data.get("aura_blessing_active"):
        await i.response.send_message(
            "A Benção do Rei Henrique já está ativa!", ephemeral=True
        )
        return

    blessing_info = ITEMS_DATA.get("bencao_rei_henrique")
    if not blessing_info:  # Safety check
        await i.response.send_message(
            "Dados da Benção do Rei Henrique não encontrados.", ephemeral=True
        )
        return

    if raw_player_data["energy"] < blessing_info["cost_energy"]:
        await i.response.send_message(
            f"Você precisa de {blessing_info['cost_energy']} de energia para invocar a {blessing_info['name']}!",
            ephemeral=True,
        )
        return

    raw_player_data["energy"] -= blessing_info["cost_energy"]
    raw_player_data["aura_blessing_active"] = True
    raw_player_data["aura_blessing_end_time"] = (
        datetime.now().timestamp() + blessing_info["duration_seconds"]
    )

    embed = Embed(
        title=f"{blessing_info['emoji']} {blessing_info['name']}! {blessing_info['emoji']}",
        description=f"O Rei Henrique da Luz concedeu sua benção a {i.user.display_name}!\n"
        f"Seus atributos e cooldowns foram aprimorados por {blessing_info['duration_seconds'] // 60} minutos!",
        color=Color.gold(),
    )
    embed.set_thumbnail(url="https://c.tenor.com/2U54k92V-i4AAAAC/tenor.gif")
    await i.response.send_message(embed=embed)
    save_data()


## Comandos Utilitários
@bot.tree.command(name="help", description="Mostra a wiki interativa do bot OUTLAWS.")
async def help(i: Interaction):
    embed = Embed(
        title="📜 Bem-vindo à Wiki de OUTLAWS",
        description="Use o menu abaixo para navegar pelos tópicos.",
        color=Color.blurple(),
    )
    embed.set_thumbnail(url="https://i.imgur.com/Sce6RIJ.png")
    await i.response.send_message(embed=embed, view=HelpView())


@bot.tree.command(
    name="afk",
    description="Entra no modo AFK. Você não pode ser alvo nem usar comandos.",
)
@app_commands.check(check_player_exists)
async def afk(i: Interaction):
    player_data = get_player_data(i.user.id)
    now, cooldown_key, last_return = (
        datetime.now().timestamp(),
        "afk_cooldown",
        player_data["cooldowns"].get("afk_cooldown", 0),
    )
    # The cooldown duration should prevent spamming AFK/online status.
    # 10800 seconds = 3 hours.
    if (
        now - last_return < 10
    ):  # Reduced for testing, change back to 10800 for production
        remaining_time = timedelta(
            seconds=10 - (now - last_return)
        )  # Adjusted for testing
        await i.response.send_message(
            f"Você não pode ficar AFK ainda. Tente novamente em {remaining_time} (Dono: {i.user.name} | Tempo de espera: 10 segundos).",
            ephemeral=True,
        )
        return

    player_data["status"] = "afk"
    save_data()
    await i.response.send_message(
        "🌙 Você entrou em modo AFK. Use `/voltar` para ficar online."
    )


@bot.tree.command(name="voltar", description="Sai do modo AFK e volta a ficar online.")
@app_commands.check(check_player_exists)
async def voltar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["status"] != "afk":
        await i.response.send_message("Você não está em modo AFK.", ephemeral=True)
        return
    player_data["status"] = "online"
    player_data["cooldowns"]["afk_cooldown"] = datetime.now().timestamp()
    save_data()
    await i.response.send_message(
        "🟢 Você está online novamente! O cooldown para usar `/afk` outra vez começou."
    )


# --- COMANDO DE ADMIN PARA CONTROLAR XP TRIPLE ---
@bot.tree.command(
    name="set_xptriple",
    description="[ADMIN] Ativa/Desativa o XP Triplo para um jogador.",
)
@app_commands.describe(
    membro="O membro para ativar/desativar o XP Triplo.",
    status="True para ativar, False para desativar.",
)
@commands.has_permissions(administrator=True)
async def set_xptriple(i: Interaction, membro: discord.Member, status: bool):
    player_data = get_player_data(membro.id)
    if not player_data:
        await i.response.send_message(
            "Este jogador não possui uma ficha.", ephemeral=True
        )
        return

    player_data["xptriple"] = status
    save_data()

    status_str = "ativado" if status else "desativado"
    await i.response.send_message(
        f"O XP Triplo para **{membro.display_name}** foi **{status_str}**."
    )


# --- NOVO COMANDO DE ADMIN PARA CONTROLAR DINHEIRO DUPLO ---
@bot.tree.command(
    name="set_money_double",
    description="[ADMIN] Ativa/Desativa o Dinheiro Duplo para um jogador.",
)
@app_commands.describe(
    membro="O membro para ativar/desativar o Dinheiro Duplo.",
    status="True para ativar, False para desativar.",
)
@commands.has_permissions(administrator=True)
async def set_money_double(i: Interaction, membro: discord.Member, status: bool):
    player_data = get_player_data(membro.id)
    if not player_data:
        await i.response.send_message(
            "Este jogador não possui uma ficha.", ephemeral=True
        )
        return

    player_data["money_double"] = status
    save_data()

    status_str = "ativado" if status else "desativado"
    await i.response.send_message(
        f"O Dinheiro Duplo para **{membro.display_name}** foi **{status_str}**."
    )


# --- COMANDO /lore ---
@bot.tree.command(name="lore", description="Mostra a história do mundo de Outlaws.")
async def lore(i: Interaction):
    lore_text = """
    No alvorecer dos tempos, a **Terra 1** era um santuário de serenidade, onde a vida florescia em harmonia e a paz reinava soberana. O seu líder, o **Rei da Luz, Luís Henrique III**, forjou essa união após incontáveis batalhas, consolidando um reino de prosperidade e tranquilidade. Naquele tempo, a magia era um conceito desconhecido, um poder adormecido que aguardava o seu despertar.

    Contudo, a inveja corroeu o coração do tio do Rei da Luz. Consumido pela ambição e seduzido pelas sombras, ele selou um pacto profano com o **Senhor da Morte**. Em troca de poder ilimitado, o ser inominável, conhecido apenas como "**o Inpronunciável**", prometeu ceifar almas e abrir caminho para a dominação multiversal, mergulhando a existência no caos.

    Após o desaparecimento do Senhor da Morte, o Inpronunciável desencadeou sua fúria em uma batalha épica contra as forças da Luz e o Rei Luís Henrique III. O confronto foi devastador, resultando na queda de ambos os líderes. Sem rei e sem proteção, a Terra 1 ficou à mercê do destino.

    Desse vácuo de poder, emergiram os **Outlaws (Foras da Lei)**. Sejam eles guiados pela virtude ou pela maldade, esses indivíduos se uniram com um único propósito: reconstruir a Terra 1. Renomeando-a para **Terra Outlaw**, eles juraram protegê-la... ou destruí-la. O futuro da Terra Outlaw agora repousa nas mãos desses enigmáticos forasteiros.
    """
    embed = Embed(
        title="📜 A Lenda da Terra Outlaw 📜",
        description=lore_text,
        color=Color.dark_purple(),
    )
    embed.set_thumbnail(
        url="https://i.imgur.com/Sce6RIJ.png"
    )  # Placeholder image, consider a more fitting one
    await i.response.send_message(embed=embed)


# --- TAREFAS EM BACKGROUND ---
@tasks.loop(seconds=60)
async def auto_save():
    save_data()


@tasks.loop(seconds=60)
async def energy_regeneration():
    for user_id, player_data in player_database.items():
        # Regenerate energy if not full
        if player_data.get("energy", 0) < MAX_ENERGY:
            player_data["energy"] += 1

        # Check if Aura Blessing has expired
        if player_data.get("aura_blessing_active"):
            if datetime.now().timestamp() > player_data.get(
                "aura_blessing_end_time", 0
            ):
                player_data["aura_blessing_active"] = False
                player_data["aura_blessing_end_time"] = 0
                user = bot.get_user(int(user_id))
                if user:
                    try:
                        await user.send(
                            f"✨ A {ITEMS_DATA.get('bencao_rei_henrique', {}).get('name', 'Bênção da Aura')} em você expirou!"
                        )
                    except discord.Forbidden:
                        pass  # Bot couldn't DM the user
                save_data()

        # Check if Dracula's Blessing has expired
        if player_data.get("bencao_dracula_active"):
            if datetime.now().timestamp() > player_data.get(
                "bencao_dracula_end_time", 0
            ):
                player_data["bencao_dracula_active"] = False
                player_data["bencao_dracula_end_time"] = 0
                user = bot.get_user(int(user_id))
                if user:
                    try:
                        await user.send(
                            f"🦇 A {ITEMS_DATA.get('bencao_dracula', {}).get('name', 'Bênção de Drácula')} em você expirou!"
                        )
                    except discord.Forbidden:
                        pass  # Bot couldn't DM the user
                save_data()

        # Check if generic class transformation has expired
        if player_data.get("is_transformed"):
            if datetime.now().timestamp() > player_data.get("transform_end_time", 0):
                player_data["is_transformed"] = False
                player_data["transform_end_time"] = 0
                user = bot.get_user(int(user_id))
                if user:
                    transform_name = CLASS_TRANSFORMATIONS.get(
                        player_data["class"], {}
                    ).get("name", "sua transformação")
                    try:
                        await user.send(
                            f"🔄 Sua transformação de {transform_name} expirou!"
                        )
                    except discord.Forbidden:
                        pass  # Bot couldn't DM the user
                save_data()


@tasks.loop(seconds=15)
async def boss_attack_loop():
    if not BOSS_DATA["is_active"] or not BOSS_DATA["channel_id"]:
        return
    channel = bot.get_channel(BOSS_DATA["channel_id"])
    if not channel:
        BOSS_DATA["is_active"] = False
        BOSS_DATA["channel_id"] = None
        return
    participants_online = [
        p_id
        for p_id in BOSS_DATA["participants"]
        if (p_data := get_player_data(p_id)) and p_data.get("status") == "online"
    ]
    if not participants_online:
        return

    targets_to_attack_ids = random.sample(
        participants_online, k=min(3, len(participants_online))
    )
    target_names = []
    for target_id in targets_to_attack_ids:
        raw_target_data = get_player_data(target_id)
        if not raw_target_data:  # Should not happen if p_id was in player_database
            continue

        damage_to_deal = random.randint(BOSS_DATA["attack"] // 2, BOSS_DATA["attack"])

        # Lógica da Bênção de Drácula (para o alvo do Boss)
        if (
            raw_target_data["class"] == "Vampiro"
            and raw_target_data.get("bencao_dracula_active", False)
            and "bencao_dracula" in ITEMS_DATA
            and random.random() < ITEMS_DATA["bencao_dracula"]["evasion_chance"]
        ):
            hp_stolen_on_evade = int(
                damage_to_deal
                * ITEMS_DATA["bencao_dracula"]["hp_steal_percent_on_evade"]
            )
            raw_target_data["hp"] = min(
                raw_target_data["max_hp"], raw_target_data["hp"] + hp_stolen_on_evade
            )

            target_names.append(
                f"**{raw_target_data['name']}** (👻 DESVIOU! Sugou `{hp_stolen_on_evade}` HP!)"
            )
        else:
            raw_target_data["hp"] -= damage_to_deal
            target_names.append(
                f"**{raw_target_data['name']}** (`{damage_to_deal}` dano)"
            )

        if raw_target_data["hp"] <= 0:
            raw_target_data["hp"] = 0
            raw_target_data["status"] = "dead"
            raw_target_data["deaths"] += 1

    if target_names:  # Only send message if someone was attacked
        attack_embed = Embed(
            title=f"👹 Fúria do {BOSS_DATA['name']}",
            description=f"O colosso ataca ferozmente! {', '.join(target_names)} foram atingidos!",
            color=Color.dark_orange(),
        )
        await channel.send(embed=attack_embed)
        save_data()


# Custom exception classes for command checks
class NotInCity(app_commands.CheckFailure):
    pass


class NotInWilderness(app_commands.CheckFailure):
    pass


# Global error handler for app commands
@bot.tree.error
async def on_app_command_error(i: Interaction, error: app_commands.AppCommandError):
    message_content = "Ocorreu um erro inesperado."
    ephemeral_status = True  # Default to ephemeral for errors

    if isinstance(error, app_commands.CommandOnCooldown):
        message_content = f"Este comando está em cooldown! Tente novamente em **{error.retry_after:.2f}s**."
    elif isinstance(error, NotInCity):
        message_content = "Este comando só pode ser usado em uma cidade. Use `/viajar` para ir para um **Abrigo dos Foras-da-Lei**."
    elif isinstance(error, NotInWilderness):
        message_content = (
            "Este comando só pode ser usado em áreas selvagens. Use `/viajar`."
        )
    elif isinstance(error, app_commands.CheckFailure):
        player_data = get_player_data(i.user.id)
        if player_data and player_data.get("status") == "afk":
            message_content = "Você não pode usar este comando enquanto estiver AFK."
        elif isinstance(error, commands.MissingPermissions):
            message_content = "Você não tem permissão para usar este comando."
        else:
            message_content = "Você ainda não tem uma ficha! Use `/criar_ficha`."
    elif isinstance(error, commands.MissingRequiredArgument):
        message_content = f"Faltando um argumento necessário: `{error.param.name}`. Por favor, verifique o comando."
    else:
        print(f"Ocorreu um erro inesperado: {error}")  # Log for debugging
        message_content = f"Ocorreu um erro inesperado: {error}"  # Keep the error message for debugging to user

    if i.response.is_done():
        try:
            await i.followup.send(message_content, ephemeral=ephemeral_status)
        except discord.errors.NotFound:
            print(
                f"Failed to send followup message for error: {error}. Interaction likely expired."
            )
    else:
        try:
            await i.response.send_message(message_content, ephemeral=ephemeral_status)
        except discord.errors.NotFound:
            print(
                f"Failed to send initial response for error: {error}. Interaction likely expired."
            )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.content.startswith(bot.command_prefix):
        return

    player_id = str(message.author.id)
    player_data = get_player_data(player_id)

    if not player_data or player_data.get("status") == "afk":
        return

    now = datetime.now().timestamp()
    cooldown_key = "message_xp_cooldown"
    last_message_xp = player_data["cooldowns"].get(cooldown_key, 0)

    if now - last_message_xp >= XP_PER_MESSAGE_COOLDOWN_SECONDS:
        xp_gain_raw = 5

        # Apply passive XP bonus from Habilidade Inata first
        xp_multiplier_passive = ITEMS_DATA.get("habilidade_inata", {}).get(
            "xp_multiplier_passive", 0.0
        )
        if player_data.get("style") == "Habilidade Inata" and xp_multiplier_passive > 0:
            xp_gain_raw = int(xp_gain_raw * (1 + xp_multiplier_passive))

        if player_data.get("xptriple") is True:
            xp_gain = xp_gain_raw * 3
        else:
            xp_gain = xp_gain_raw

        player_data["xp"] += xp_gain
        player_data["cooldowns"][cooldown_key] = now
        save_data()

        await check_and_process_levelup(message.author, player_data, message.channel)

    await bot.process_commands(message)


# --- INICIAR O BOT ---
if __name__ == "__main__":
    if TOKEN:
        try:
            bot.run(TOKEN)
        except KeyboardInterrupt:
            print("Desligando...")
            save_data()
        except discord.errors.LoginFailure as e:
            print(f"ERRO DE LOGIN: {e}\nVerifique seu DISCORD_TOKEN no arquivo .env.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado ao iniciar o bot: {e}")
    else:
        print("ERRO: O DISCORD_TOKEN não foi encontrado no arquivo .env!")
