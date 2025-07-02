import discord
from discord.ext import commands, tasks
import asyncio
from discord import app_commands, Embed, Color, Interaction, ui, ButtonStyle
import json
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import constants and data from config.py
from config import (
    XP_PER_LEVEL_BASE,
    XP_PER_MESSAGE_COOLDOWN_SECONDS,
    ATTRIBUTE_POINTS_PER_LEVEL,
    CRITICAL_CHANCE,
    CRITICAL_MULTIPLIER,
    INITIAL_MONEY,
    INITIAL_HP,
    INITIAL_ATTACK,
    INITIAL_SPECIAL_ATTACK,
    REVIVE_COST,
    BOUNTY_PERCENTAGE,
    TRANSFORM_COST,
    MAX_ENERGY,
    STARTING_LOCATION,
    ITEMS_DATA,
    CLASS_TRANSFORMATIONS,
    BOSS_DATA,
    WORLD_MAP,
    ENEMIES,
    PROFILE_IMAGES,
    LEVEL_ROLES,
    NEW_CHARACTER_ROLE_ID,
)

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_DATA_FILE = os.path.join(SCRIPT_DIR, "outlaws_data.json")
GUILD_ID = 1318938087535153152  # Consider making this dynamic or loading from config if it varies


# Custom exception classes for command checks
class NotInCity(app_commands.CheckFailure):
    """Raised when a command is used outside of a city location."""

    pass


class NotInWilderness(app_commands.CheckFailure):
    """Raised when a command is used outside of a wilderness location."""

    pass


# --- GERENCIAMENTO DE DADOS ---
def load_data():
    """Loads player data from the JSON file."""
    if not os.path.exists(PLAYER_DATA_FILE):
        return {}
    try:
        with open(PLAYER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"ERRO ao carregar dados: {e}")
        return {}


player_database = load_data()


def save_data():
    """Saves player data to the JSON file."""
    try:
        with open(PLAYER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(player_database, f, indent=4)
    except IOError as e:
        print(f"ERRO CRÍTICO AO SALVAR DADOS: {e}")


def get_player_data(user_id):
    """Retrieves raw player data from the database, initializing if necessary."""
    user_id_str = str(user_id)
    if user_id_str not in player_database:
        # Initialize default player data if not found (e.g., for /perfil on a new user)
        # This prevents KeyError if a command tries to access a non-existent player
        return None  # Or a default structure if you want to handle it differently

    # Ensure 'location' is set for existing players without it
    if "location" not in player_database[user_id_str]:
        player_database[user_id_str]["location"] = STARTING_LOCATION
        save_data()  # Save immediately after correcting old data

    return player_database.get(user_id_str)


# --- FUNÇÕES AUXILIARES GLOBAIS ---
def calculate_effective_stats(raw_player_data: dict) -> dict:
    """Calculates a player's effective stats based on their base stats, transformation, and inventory items.
    Does NOT modify the original raw_player_data.
    """
    effective_data = raw_player_data.copy()

    # Default values for bonuses/multipliers
    effective_data["attack_bonus_passive_percent"] = 0.0
    effective_data["healing_multiplier"] = 1.0
    effective_data["evasion_chance_bonus"] = 0.0  # Initialize evasion bonus

    # Apply passive bonuses from "Habilidade Inata" source of power
    habilidade_inata_info = ITEMS_DATA.get("habilidade_inata", {})
    if effective_data.get("style") == "Habilidade Inata":
        effective_data["attack_bonus_passive_percent"] = habilidade_inata_info.get(
            "attack_bonus_passive_percent", 0.0
        )

    # Initialize current attack/special_attack/max_hp with base values
    effective_data["attack"] = raw_player_data["base_attack"]
    effective_data["special_attack"] = raw_player_data["base_special_attack"]
    effective_data["max_hp"] = raw_player_data["max_hp"]  # Start with raw max_hp

    # Apply class transformations
    if effective_data.get("current_transformation"):
        transform_name = effective_data["current_transformation"]
        class_name = effective_data["class"]
        transform_info = CLASS_TRANSFORMATIONS.get(class_name, {}).get(transform_name)
        if transform_info:
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
            effective_data["healing_multiplier"] *= transform_info.get(
                "healing_multiplier", 1.0
            )

            if "evasion_chance_bonus" in transform_info:
                effective_data["evasion_chance_bonus"] += transform_info[
                    "evasion_chance_bonus"
                ]

    # Apply Aura-specific blessing (King Henry's Blessing) if active
    king_henry_blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
    if effective_data.get("aura_blessing_active"):
        effective_data["attack"] = int(
            effective_data["attack"]
            * king_henry_blessing_info.get("attack_multiplier", 1.0)
        )
        effective_data["special_attack"] = int(
            effective_data["special_attack"]
            * king_henry_blessing_info.get("special_attack_multiplier", 1.0)
        )
        effective_data["max_hp"] = int(
            effective_data["max_hp"]
            * king_henry_blessing_info.get("max_hp_multiplier", 1.0)
        )
        effective_data["healing_multiplier"] *= king_henry_blessing_info.get(
            "healing_multiplier", 1.0
        )

    # Apply item bonuses based on inventory (after transformations for proper stacking)
    inventory = effective_data.get("inventory", {})

    # Manopla do Lutador: Increases attack and HP
    manopla_lutador_info = ITEMS_DATA.get("manopla_lutador", {})
    if inventory.get("manopla_lutador", 0) > 0 and effective_data["class"] == "Lutador":
        effective_data["attack"] = int(
            effective_data["attack"]
            * (1 + manopla_lutador_info.get("attack_bonus_percent", 0.0))
        )
        effective_data["max_hp"] = int(
            effective_data["max_hp"] + manopla_lutador_info.get("hp_bonus_flat", 0)
        )

    # Espada Fantasma: Attack bonus and HP penalty
    espada_fantasma_info = ITEMS_DATA.get("espada_fantasma", {})
    if (
        inventory.get("espada_fantasma", 0) > 0
        and effective_data["class"] == "Espadachim"
    ):
        effective_data["attack"] = int(
            effective_data["attack"]
            * (1 + espada_fantasma_info.get("attack_bonus_percent", 0.0))
        )
        # Apply penalty to the calculated max_hp based on previous buffs
        effective_data["max_hp"] = int(
            effective_data["max_hp"]
            * (1 - espada_fantasma_info.get("hp_penalty_percent", 0.0))
        )
        effective_data["hp"] = min(
            effective_data["hp"], effective_data["max_hp"]
        )  # Adjust current HP

    # Cajado do Curandeiro: Increases healing effectiveness
    cajado_curandeiro_info = ITEMS_DATA.get("cajado_curandeiro", {})
    if (
        inventory.get("cajado_curandeiro", 0) > 0
        and effective_data["class"] == "Curandeiro"
    ):
        effective_data["healing_multiplier"] *= cajado_curandeiro_info.get(
            "effect_multiplier", 1.0
        )

    # Mira Semi-Automática (Handles cooldown reduction, not direct stats)
    # The effect for Mira Semi-Automática is handled directly in the cooldown calculation where needed.

    # Apply passive attack bonus from "Habilidade Inata" (final layer)
    effective_data["attack"] = int(
        effective_data["attack"]
        * (1 + effective_data.get("attack_bonus_passive_percent", 0.0))
    )

    # Ensure HP doesn't exceed new max_hp after all calculations
    effective_data["hp"] = min(raw_player_data["hp"], effective_data["max_hp"])

    return effective_data


# Helper function to process level-ups (NOW A METHOD OF OutlawsBot)
# Moved inside the class `OutlawsBot` to allow `self.bot` context
async def check_and_process_levelup_internal(
    bot_instance,  # Added this to pass the bot instance
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
            url="https://media.tenor.com/drx1lO9cfEAAAAi/dark-souls-bonfire.gif"
        )
        embed.add_field(
            name="Recompensas",
            value=f"🔹 **{ATTRIBUTE_POINTS_PER_LEVEL}** Pontos de Atributo\n🔹 Vida totalmente restaurada!",
            inline=False,
        )
        embed.set_footer(text="Use /distribuir_pontos para ficar mais forte!")

        # --- Lógica para conceder cargos a cada 10 níveis ---
        if isinstance(LEVEL_ROLES, dict):
            sorted_level_roles_keys = sorted(LEVEL_ROLES.keys(), reverse=True)

            current_role_to_assign = None
            for required_level in sorted_level_roles_keys:
                if player_data["level"] >= required_level:
                    current_role_to_assign = LEVEL_ROLES[required_level]
                    break

            guild_id_from_context = (
                send_target.guild_id
                if isinstance(send_target, Interaction)
                else send_target.guild.id
            )
            guild = bot_instance.get_guild(guild_id_from_context)  # Use bot_instance

            if guild:
                member_obj = guild.get_member(member.id)
                if member_obj:
                    roles_to_remove = []
                    for level_key, role_id in LEVEL_ROLES.items():
                        role_to_remove = guild.get_role(role_id)
                        if role_to_remove and role_to_remove in member_obj.roles:
                            roles_to_remove.append(role_to_remove)

                    if roles_to_remove:
                        try:
                            await member_obj.remove_roles(
                                *roles_to_remove,
                                reason="Level up - updating level roles",
                            )
                        except discord.Forbidden:
                            print(
                                f"Erro: Bot sem permissão para remover cargos de nível para {member.display_name}."
                            )
                        except discord.HTTPException as e:
                            print(
                                f"Erro ao remover cargos de nível para {member.display_name}: {e}"
                            )

                    if current_role_to_assign:
                        role = guild.get_role(current_role_to_assign)
                        if role and role not in member_obj.roles:
                            try:
                                await member_obj.add_roles(
                                    role,
                                    reason=f"Reached Level {player_data['level']}",
                                )
                                embed.add_field(
                                    name="🎉 Novo Cargo Desbloqueado!",
                                    value=f"Você recebeu o cargo `{role.name}`!",
                                    inline=False,
                                )
                            except discord.Forbidden:
                                print(
                                    f"Erro: Bot não tem permissão para adicionar o cargo {role.name} ao usuário {member.display_name}. Verifique as permissões do bot e a hierarquia de cargos."
                                )
                            except discord.HTTPException as e:
                                print(
                                    f"Erro ao adicionar cargo para {member.display_name}: {e}"
                                )
                        elif not role:
                            print(
                                f"Aviso: Cargo com ID {current_role_to_assign} não encontrado na guilda {guild.name}."
                            )
                else:
                    print(
                        f"Aviso: Membro {member.display_name} não encontrado na guilda para atualizar cargos."
                    )
            else:
                print(
                    f"Aviso: Guilda com ID {guild_id_from_context} não encontrada para conceder cargo de nível."
                )
        # --- FIM da Lógica para conceder cargos a cada 10 níveis ---

        if isinstance(send_target, Interaction):
            try:
                if send_target.response.is_done():
                    await send_target.followup.send(embed=embed)
                else:
                    await send_target.response.send_message(
                        embed=embed
                    )  # Initial response
            except discord.InteractionResponded:
                await send_target.channel.send(
                    embed=embed
                )  # Fallback if already responded and followup failed
            except Exception as e:
                print(f"Erro ao enviar embed de level up na interação: {e}")
        else:
            await send_target.send(embed=embed)

        xp_needed = int(XP_PER_LEVEL_BASE * (player_data["level"] ** 1.2))


# run_turn_based_combat (remains global, bot instance passed explicitly)
async def run_turn_based_combat(
    bot_instance: commands.Bot,  # Explicitly pass the bot instance
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

    if not interaction.response.is_done():
        await interaction.response.defer()

    battle_message = await interaction.edit_original_response(embed=embed)

    turn = 1
    while player_hp > 0 and enemy_hp > 0:
        await asyncio.sleep(2.5)

        player_dmg = 0
        attack_type_name = ""
        crit_msg = ""

        # Calculate energy cost for special attack with reductions
        cost_energy_special = TRANSFORM_COST

        # Aura Blessing reduction
        if raw_player_data.get("aura_blessing_active"):
            blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
            cost_energy_special = max(
                1,
                int(
                    cost_energy_special
                    * (1 - blessing_info.get("cooldown_reduction_percent", 0.0))
                ),
            )

        # Transformation reduction
        if raw_player_data.get("current_transformation"):
            transform_name = raw_player_data["current_transformation"]
            class_name = raw_player_data["class"]
            transform_info = CLASS_TRANSFORMATIONS.get(class_name, {}).get(
                transform_name
            )
            if transform_info and "cooldown_reduction_percent" in transform_info:
                cost_energy_special = max(
                    1,
                    int(
                        cost_energy_special
                        * (1 - transform_info["cooldown_reduction_percent"])
                    ),
                )

        # Mira Semi-Automática reduction
        mira_semi_automatica_info = ITEMS_DATA.get("mira_semi_automatica", {})
        if (
            raw_player_data["inventory"].get("mira_semi_automatica", 0) > 0
            and raw_player_data["class"] == "Atirador"
        ):
            cost_energy_special = max(
                1,
                int(
                    cost_energy_special
                    * (
                        1
                        - mira_semi_automatica_info.get(
                            "cooldown_reduction_percent", 0.0
                        )
                    )
                ),
            )

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
                if raw_player_data["energy"] < cost_energy_special:
                    # This should ideally be caught before starting combat, but as a fallback
                    player_dmg = random.randint(
                        player_stats["attack"] // 2, player_stats["attack"]
                    )
                    attack_type_name = (
                        "Ataque Básico (Energia Insuficiente para Especial)"
                    )
                    log.append(
                        "⚠️ Energia insuficiente para Ataque Especial. Usando Ataque Básico."
                    )
                else:
                    player_dmg = random.randint(
                        int(player_stats["special_attack"] * 0.8),
                        int(player_stats["special_attack"] * 1.5),
                    )
                    attack_type_name = "Ataque Especial"
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
        else:  # Subsequent turns always use basic attack
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

        player_hp = raw_player_data["hp"]

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

        enemy_dmg = random.randint(enemy["attack"] // 2, enemy["attack"])

        # Calculate Dracula evasion chance considering transformation bonus
        dracula_evasion_chance = ITEMS_DATA.get("bencao_dracula", {}).get(
            "evasion_chance", 0.0
        )
        if raw_player_data.get("current_transformation") == "Rei da Noite":
            vampire_blessed_transform_info = CLASS_TRANSFORMATIONS.get(
                "Vampiro", {}
            ).get("Rei da Noite", {})
            dracula_evasion_chance += vampire_blessed_transform_info.get(
                "evasion_chance_bonus", 0.0
            )

        if (
            raw_player_data["class"] == "Vampiro"
            and raw_player_data.get("bencao_dracula_active", False)
            and random.random() < dracula_evasion_chance
        ):
            hp_steal_percent_on_evade = ITEMS_DATA.get("bencao_dracula", {}).get(
                "hp_steal_percent_on_evade", 0.0
            )
            hp_stolen_on_evade = int(enemy_dmg * hp_steal_percent_on_evade)
            raw_player_data["hp"] = min(
                raw_player_data["max_hp"], raw_player_data["hp"] + hp_stolen_on_evade
            )

            log.append(
                f"👻 **DESVIADO!** {enemy['name']} errou o ataque! Você sugou `{hp_stolen_on_evade}` HP!)"
            )
            if len(log) > 5:
                log.pop(0)
            player_hp = raw_player_data["hp"]
            embed.description = "\n".join(log)
            embed.set_field_at(
                0,
                name=interaction.user.display_name,
                value=f"❤️ {max(0, player_hp)}/{player_stats['max_hp']}",
                inline=True,
            )
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(1.5)
            continue

        player_hp -= enemy_dmg
        raw_player_data["hp"] = player_hp

        # Amulet of Stone activation
        amulet_info = ITEMS_DATA.get("amuleto_de_pedra", {})
        if (
            player_hp <= 0
            and raw_player_data["inventory"].get("amuleto_de_pedra", 0) > 0
            and not amulet_activated_this_combat
            and not raw_player_data.get("amulet_used_since_revive", False)
        ):
            player_hp = 1
            raw_player_data["hp"] = 1
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

    final_embed = Embed()
    raw_player_data["hp"] = max(0, player_hp)

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

        # Apply passive XP bonus from Habilidade Inata first
        xp_multiplier_passive = ITEMS_DATA.get("habilidade_inata", {}).get(
            "xp_multiplier_passive", 0.0
        )
        if raw_player_data.get("style") == "Habilidade Inata":
            xp_gain_raw = int(xp_gain_raw * (1 + xp_multiplier_passive))

        if raw_player_data.get("xptriple") is True:
            xp_gain = xp_gain_raw * 3
            xp_message = f"✨ +{xp_gain} XP (triplicado!)"
        else:
            xp_gain = xp_gain_raw
            xp_message = f"✨ +{xp_gain} XP"

        # Refine XP message if Habilidade Inata is active but not trippled
        if (
            raw_player_data.get("style") == "Habilidade Inata"
            and xp_multiplier_passive > 0
            and not raw_player_data.get("xptriple")
        ):
            xp_message += f" (Habilidade Inata: +{int(xp_multiplier_passive*100)}%!)"
        elif (
            raw_player_data.get("style") == "Habilidade Inata"
            and xp_multiplier_passive > 0
            and raw_player_data.get("xptriple")
        ):
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
                item_info_drop = ITEMS_DATA.get(item)
                if not item_info_drop:  # Skip if item not defined in ITEMS_DATA
                    print(
                        f"Warning: Item '{item}' from BOSS_DATA drops is not defined in ITEMS_DATA."
                    )
                    continue

                if item == "amuleto_de_pedra":
                    if raw_player_data["inventory"].get("amuleto_de_pedra", 0) == 0:
                        raw_player_data["inventory"]["amuleto_de_pedra"] = 1
                        final_embed.add_field(
                            name="Item Encontrado!",
                            value=f"Você encontrou **{item_info_drop['name']}**!",
                            inline=False,
                        )
                    else:
                        final_embed.add_field(
                            name="Amuleto de Pedra (Já Possuído)",
                            value=f"Você já possui o **{item_info_drop['name']}**. Não é possível obter mais de um.",
                            inline=False,
                        )
                else:
                    raw_player_data["inventory"][item] = (
                        raw_player_data["inventory"].get(item, 0) + quantity
                    )
                    final_embed.add_field(
                        name="Item Encontrado!",
                        value=f"Você encontrou **{item_info_drop['name']}**!",
                        inline=False,
                    )

        await bot_instance.check_and_process_levelup(
            interaction.user, raw_player_data, interaction
        )

    save_data()
    await interaction.edit_original_response(embed=final_embed)


# --- SETUP DO BOT ---
class OutlawsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.auto_save.start()
        self.energy_regeneration.start()
        self.boss_attack_loop.start()
        await self.tree.sync()
        print("Comandos sincronizados!")
        self.sync_roles_periodically.start()
        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, interaction: Interaction, error: app_commands.AppCommandError
    ):
        """Um manipulador global de erros para todos os slash commands."""

        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏳ Este comando está em cooldown! Tente novamente em **{error.retry_after:.1f} segundos**.",
                ephemeral=True,
            )
        elif isinstance(error, NotInWilderness):
            await interaction.response.send_message(
                f"🌲 **Ação Inválida!** {error}", ephemeral=True
            )
        elif isinstance(error, NotInCity):
            await interaction.response.send_message(
                f"🏙️ **Ação Inválida!** {error}", ephemeral=True
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 Você não tem permissão para usar este comando.", ephemeral=True
            )
        elif isinstance(error, app_commands.NoPrivateMessage):
            await interaction.response.send_message(
                "Este comando não pode ser usado em mensagens privadas.", ephemeral=True
            )
        elif isinstance(error, app_commands.CheckFailure):
            # Catch all other custom check failures if needed, or let them fall through
            await interaction.response.send_message(
                f"🚫 Falha na verificação: {error}", ephemeral=True
            )
        else:
            print(f"Erro não tratado no comando '{interaction.command.name}': {error}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro inesperado ao executar este comando.",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        "❌ Ocorreu um erro inesperado ao executar este comando.",
                        ephemeral=True,
                    )
            except Exception as e:
                print(f"Erro ao tentar enviar a mensagem de erro ao usuário: {e}")

    async def on_ready(self):
        print(f"Bot {self.user} está online!")
        print(f"Dados de {len(player_database)} jogadores carregados.")

    async def close(self):
        print("Desligando e salvando dados...")
        save_data()
        await super().close()

    # Helper function to process level-ups (NOW A METHOD OF OutlawsBot)
    async def check_and_process_levelup(
        self,
        member: discord.Member,
        player_data: dict,
        send_target: Interaction | discord.TextChannel,
    ):
        # Call the internal function, passing self (the bot instance)
        await check_and_process_levelup_internal(self, member, player_data, send_target)

    # --- TAREFAS EM BACKGROUND (agora métodos da classe) ---
    @tasks.loop(seconds=60)
    async def auto_save(self):
        save_data()
        print("Dados salvos automaticamente.")  # Added for confirmation

    @tasks.loop(seconds=60)
    async def energy_regeneration(self):
        for user_id_str, player_data in player_database.items():
            user_id = int(user_id_str)  # Convert back to int for get_user
            if player_data.get("energy", 0) < MAX_ENERGY:
                player_data["energy"] += 1

            now = datetime.now().timestamp()

            # Check for Aura Blessing expiration
            if player_data.get("aura_blessing_active"):
                if now > player_data.get("aura_blessing_end_time", 0):
                    player_data["aura_blessing_active"] = False
                    player_data["aura_blessing_end_time"] = 0
                    user = self.get_user(user_id)
                    if user:
                        try:
                            await user.send(
                                f"✨ A {ITEMS_DATA.get('bencao_rei_henrique', {}).get('name', 'Bênção da Aura')} em você expirou!"
                            )
                        except discord.Forbidden:
                            pass  # Cannot send DMs
                    # save_data() # Will be saved by auto_save or next loop iteration

            # Check for Dracula Blessing expiration
            if player_data.get("bencao_dracula_active"):
                if now > player_data.get("bencao_dracula_end_time", 0):
                    player_data["bencao_dracula_active"] = False
                    player_data["bencao_dracula_end_time"] = 0
                    user = self.get_user(user_id)
                    if user:
                        try:
                            await user.send(
                                f"🦇 A {ITEMS_DATA.get('bencao_dracula', {}).get('name', 'Bênção de Drácula')} em você expirou!"
                            )
                        except discord.Forbidden:
                            pass
                    # save_data() # Will be saved by auto_save or next loop iteration

            # Check for Transformation expiration
            if player_data.get("current_transformation"):
                if now > player_data.get("transform_end_time", 0):
                    transform_name = player_data["current_transformation"]
                    player_data["current_transformation"] = None
                    player_data["transform_end_time"] = 0
                    user = self.get_user(user_id)
                    if user:
                        try:
                            await user.send(
                                f"🔄 Sua transformação de {transform_name} expirou!"
                            )
                        except discord.Forbidden:
                            pass
                    # save_data() # Will be saved by auto_save or next loop iteration
        save_data()  # Save all changes once per loop for efficiency

    @tasks.loop(seconds=15)
    async def boss_attack_loop(self):
        if not BOSS_DATA["is_active"] or not BOSS_DATA["channel_id"]:
            return
        channel = self.get_channel(BOSS_DATA["channel_id"])
        if not channel:
            BOSS_DATA["is_active"] = False
            BOSS_DATA["channel_id"] = None
            save_data()  # Save boss data changes
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
            if not raw_target_data:
                continue

            damage_to_deal = random.randint(
                BOSS_DATA["attack"] // 2, BOSS_DATA["attack"]
            )

            # Calculate total evasion chance
            dracula_evasion_chance = ITEMS_DATA.get("bencao_dracula", {}).get(
                "evasion_chance", 0.0
            )
            if raw_target_data.get("current_transformation") == "Rei da Noite":
                vampire_blessed_transform_info = CLASS_TRANSFORMATIONS.get(
                    "Vampiro", {}
                ).get("Rei da Noite", {})
                dracula_evasion_chance += vampire_blessed_transform_info.get(
                    "evasion_chance_bonus", 0.0
                )

            if (
                raw_target_data["class"] == "Vampiro"
                and raw_target_data.get("bencao_dracula_active", False)
                and random.random() < dracula_evasion_chance
            ):
                hp_steal_percent_on_evade = ITEMS_DATA.get("bencao_dracula", {}).get(
                    "hp_steal_percent_on_evade", 0.0
                )
                hp_stolen_on_evade = int(damage_to_deal * hp_steal_percent_on_evade)
                raw_target_data["hp"] = min(
                    raw_target_data["max_hp"],
                    raw_target_data["hp"] + hp_stolen_on_evade,
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

        if target_names:
            attack_embed = Embed(
                title=f"👹 Fúria do {BOSS_DATA['name']}",
                description=f"O colosso ataca ferozmente! {', '.join(target_names)} foram atingidos!",
                color=Color.dark_orange(),
            )
            await channel.send(embed=attack_embed)
            save_data()  # Save after boss attack updates

    # --- NOVA TAREFA: Sincronização de Cargos (MOVIDA PARA DENTRO DA CLASSE OutlawsBot) ---
    @tasks.loop(minutes=5)
    async def sync_roles_periodically(self):
        if GUILD_ID == 0:
            print(
                "AVISO: GUILD_ID não está configurado. A sincronização de cargos não funcionará."
            )
            return

        guild = self.get_guild(GUILD_ID)
        if not guild:
            print(
                f"AVISO: Guilda com ID {GUILD_ID} não encontrada. A sincronização de cargos não pode prosseguir."
            )
            return

        print(f"Iniciando sincronização de cargos na guilda {guild.name}...")

        if not guild.chunked:
            try:
                await guild.chunk()
                print(f"Membros da guilda {guild.name} carregados no cache.")
            except discord.HTTPException as e:
                print(f"Erro ao carregar membros da guilda {guild.name}: {e}")
                return

        total_synced = 0
        for member_id_str, player_data in player_database.items():
            member_id = int(member_id_str)
            member = guild.get_member(member_id)

            if not member:
                continue

            if player_data.get("status") == "afk":
                continue

            # 1. Handle NEW_CHARACTER_ROLE_ID
            if isinstance(NEW_CHARACTER_ROLE_ID, int) and NEW_CHARACTER_ROLE_ID > 0:
                new_char_role = guild.get_role(NEW_CHARACTER_ROLE_ID)
                if new_char_role:
                    if new_char_role not in member.roles:
                        try:
                            await member.add_roles(
                                new_char_role, reason="Sincronização de cargo inicial."
                            )
                            total_synced += 1
                        except discord.Forbidden:
                            print(
                                f"PERMISSÃO NEGADA: Não foi possível adicionar '{new_char_role.name}' a {member.display_name}."
                            )
                        except discord.HTTPException as e:
                            print(
                                f"ERRO HTTP ao adicionar '{new_char_role.name}' a {member.display_name}: {e}"
                            )

            # 2. Handle LEVEL_ROLES
            if isinstance(LEVEL_ROLES, dict):
                current_level = player_data.get("level", 1)
                highest_applicable_role_id = None

                for required_level in sorted(LEVEL_ROLES.keys(), reverse=True):
                    if current_level >= required_level:
                        highest_applicable_role_id = LEVEL_ROLES[required_level]
                        break

                all_level_role_ids = list(LEVEL_ROLES.values())

                roles_to_remove = []
                roles_to_add = []

                for existing_role in member.roles:
                    if (
                        existing_role.id in all_level_role_ids
                        and existing_role.id != highest_applicable_role_id
                    ):
                        roles_to_remove.append(existing_role)

                if highest_applicable_role_id:
                    role_to_add = guild.get_role(highest_applicable_role_id)
                    if role_to_add and role_to_add not in member.roles:
                        roles_to_add.append(role_to_add)

                if roles_to_remove:
                    try:
                        await member.remove_roles(
                            *roles_to_remove, reason="Sincronização de cargos de nível."
                        )
                        total_synced += len(roles_to_remove)
                    except discord.Forbidden:
                        print(
                            f"PERMISSÃO NEGADA: Não foi possível remover cargos de {member.display_name}."
                        )
                    except discord.HTTPException as e:
                        print(
                            f"ERRO HTTP ao remover cargos de {member.display_name}: {e}"
                        )

                if roles_to_add:
                    try:
                        await member.add_roles(
                            *roles_to_add, reason="Sincronização de cargos de nível."
                        )
                        total_synced += len(roles_to_add)
                    except discord.Forbidden:
                        print(
                            f"PERMISSÃO NEGADA: Não foi possível adicionar '{roles_to_add[0].name}' a {member.display_name}."
                        )
                    except discord.HTTPException as e:
                        print(
                            f"ERRO HTTP ao adicionar '{roles_to_add[0].name}' a {member.display_name}: {e}"
                        )

        if total_synced > 0:
            print(f"Sincronização de cargos concluída. Total de ações: {total_synced}.")
        else:
            print("Sincronização de cargos concluída. Nenhum cargo foi alterado.")

    @sync_roles_periodically.before_loop
    async def before_sync_roles_periodically(self):
        await self.wait_until_ready()


# Instantiate the bot after the class and its methods are fully defined.
bot = OutlawsBot()


# Custom checks for app commands (remain global, as they take `Interaction` directly)
def is_in_city(i: Interaction):
    p = get_player_data(i.user.id)
    if not p:  # Ensure player exists before checking location
        raise app_commands.CheckFailure("Você não possui uma ficha de personagem.")
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "cidade":
        return True
    raise NotInCity("Este comando só pode ser usado em uma cidade.")


def is_in_wilderness(i: Interaction):
    p = get_player_data(i.user.id)
    if not p:  # Ensure player exists before checking location
        raise app_commands.CheckFailure("Você não possui uma ficha de personagem.")
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "selvagem":
        return True
    raise NotInWilderness("Este comando só pode ser usado em áreas selvagens.")


def check_player_exists(i: Interaction):
    p = get_player_data(i.user.id)
    return (
        p and p.get("status") != "afk"
    )  # Removed the explicit check for `p` being `None` as get_player_data handles it


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

        # Initialize base stats with default values from config
        base_stats = {
            "hp": INITIAL_HP,
            "attack": INITIAL_ATTACK,
            "special_attack": INITIAL_SPECIAL_ATTACK,
        }

        # Apply class-specific base stat adjustments
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
            "current_transformation": None,
            "transform_end_time": 0,
            "aura_blessing_active": False,
            "aura_blessing_end_time": 0,
            "bencao_dracula_active": False,
            "bencao_dracula_end_time": 0,
            "amulet_used_since_revive": False,
            "attribute_points": 0,
            "location": STARTING_LOCATION,  # Ensure this is always set on creation
            "xptriple": False,
            "money_double": False,
        }

        # --- NOVO: Concede cargo de personagem inicial ---
        guild = i.guild
        if guild:
            if isinstance(NEW_CHARACTER_ROLE_ID, int) and NEW_CHARACTER_ROLE_ID > 0:
                new_char_role = guild.get_role(NEW_CHARACTER_ROLE_ID)
                if new_char_role:
                    try:
                        await i.user.add_roles(new_char_role)
                        print(
                            f"Adicionado o cargo '{new_char_role.name}' para {i.user.display_name}"
                        )
                    except discord.Forbidden:
                        print(
                            f"Erro: Bot não tem permissão para adicionar o cargo '{new_char_role.name}' ao usuário {i.user.display_name}. Verifique as permissões do bot e a hierarquia de cargos."
                        )
                    except discord.HTTPException as e:
                        print(f"Erro ao adicionar cargo inicial: {e}")
                else:
                    print(
                        f"Cargo inicial com ID {NEW_CHARACTER_ROLE_ID} não encontrado na guilda."
                    )
            else:
                print(
                    "NEW_CHARACTER_ROLE_ID não é um ID de cargo válido (deve ser um número inteiro positivo)."
                )
        # --- FIM NOVO: Concede cargo de personagem inicial ---

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
    """
    Uma View do Discord otimizada para exibir o perfil e o inventário de um jogador
    com uma UI/UX limpa, moderna e inspirada na interface nativa do Discord.
    """

    def __init__(
        self,
        user: discord.Member,
        bot_user: discord.ClientUser,
        original_interaction: Interaction,
    ):
        super().__init__(timeout=180)
        self.user = user
        self.bot_user = bot_user
        self.original_interaction = original_interaction

    # --- Métodos Estáticos para Barras de Progresso ---
    @staticmethod
    def create_xp_bar(current_xp: int, needed_xp: int, length: int = 10) -> str:
        if needed_xp == 0:
            return "`" + "█" * length + "`"
        progress = min(current_xp / needed_xp, 1.0)
        filled_length = int(length * progress)
        bar = "█" * filled_length + "░" * (length - filled_length)
        return f"`{bar}`"

    @staticmethod
    def create_progress_bar(current: int, total: int, length: int = 10) -> str:
        """Creates a simple text-based progress bar."""
        if total == 0:
            return "`" + "█" * length + "`"
        progress = min(current / total, 1.0)
        filled_length = int(length * progress)
        bar = "█" * filled_length + "░" * (length - filled_length)
        return f"`{bar}`"

    # --- FIM dos Métodos Estáticos ---

    def create_profile_embed(self) -> discord.Embed:
        """
        Cria o embed do perfil com layout responsivo (todas as estatísticas em um único campo).
        """
        player_data = get_player_data(self.user.id)
        if not player_data:
            return Embed(
                title="❌ Erro",
                description="Dados do jogador não encontrados.",
                color=Color.red(),
            )

        player_stats = calculate_effective_stats(player_data)

        # --- Lógica de Efeitos e Cor do Embed ---
        active_effects = []
        embed_color = self.user.color
        profile_image_url = PROFILE_IMAGES.get(player_data["class"])

        if player_data.get("current_transformation"):
            transform_name = player_data["current_transformation"]
            transform_info = CLASS_TRANSFORMATIONS.get(player_data["class"], {}).get(
                transform_name, {}
            )
            active_effects.append(
                f"{transform_info.get('emoji', '🔥')} **{transform_name}**"
            )
            profile_image_url = PROFILE_IMAGES.get(transform_name, profile_image_url)
            embed_color = Color.orange()

        if player_data.get("aura_blessing_active"):
            blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
            blessing_name = blessing_info.get("name")
            active_effects.append(
                f"{blessing_info.get('emoji', '✨')} **{blessing_name}**"
            )
            # Only change profile image/color if no transformation is active
            if not player_data.get("current_transformation"):
                profile_image_url = PROFILE_IMAGES.get(blessing_name, profile_image_url)
                embed_color = Color.gold()

        if player_data.get("bencao_dracula_active"):
            dracula_info = ITEMS_DATA.get("bencao_dracula", {})
            active_effects.append(
                f"{dracula_info.get('emoji', '🦇')} **{dracula_info.get('name')}**"
            )

        # --- Criação do Embed ---
        embed = Embed(title=f"Perfil de {self.user.display_name}", color=embed_color)
        embed.set_thumbnail(
            url=self.user.display_avatar.url
        )  # Always get URL for avatar
        if profile_image_url:
            embed.set_image(url=profile_image_url)

        # --- Barras de Progresso (AGORA CHAMANDO VIA CLASSE) ---
        hp_bar = ProfileView.create_progress_bar(
            player_data["hp"], player_stats["max_hp"], length=15
        )
        energy_bar = ProfileView.create_progress_bar(
            player_data["energy"], MAX_ENERGY, length=15
        )
        xp_needed = int(XP_PER_LEVEL_BASE * (player_data["level"] ** 1.2))
        xp_bar = ProfileView.create_xp_bar(player_data["xp"], xp_needed, length=15)

        # --- Descrição Principal (Sumário do Personagem) ---
        # Fixed the 'location' retrieval to always have a valid default.
        location_info = WORLD_MAP.get(
            player_data.get("location", STARTING_LOCATION), {}
        )
        status_map = {"online": "🟢 Online", "dead": "💀 Morto", "afk": "🌙 AFK"}

        embed.description = (
            f"**{player_data['class']}** | Nível **{player_data['level']}**\n"
            f"{xp_bar} `({player_data['xp']}/{xp_needed} XP)`\n"
            f"📍 **Localização:** `{location_info.get('name', 'Desconhecida')}`\n"
            f"Status: *{status_map.get(player_data['status'], 'Indefinido')}*\n"
        )

        # --- Detailed Stats (all in one inline=False field for maximum responsiveness and readability) ---
        stats_value = (
            f"**__⚔️ Combate__**\n"
            f"❤️ **Vida:** `{player_data['hp']}/{player_stats['max_hp']}` {hp_bar}\n"
            f"🗡️ **Ataque:** `{player_stats['attack']}`\n"
            f"✨ **Atq. Especial:** `{player_stats['special_attack']}`\n"
            f"\n"
            f"**__⚙️ Recursos__**\n"
            f"⚡ **Energia:** `{player_data['energy']}/{MAX_ENERGY}` {energy_bar}\n"
            f"💰 **Dinheiro:** `${player_data['money']}`\n"
            f"🌟 **Pontos de Atributo:** `{player_data.get('attribute_points', 0)}`\n"
            f"\n"
            f"**__🏆 Registro & Boosts__**\n"
            f"⚔️ **Abates:** `{player_data['kills']}`\n"
            f"☠️ **Mortes:** `{player_data['deaths']}`\n"
            f"🏴‍☠️ **Recompensa:** `${player_data.get('bounty', 0)}`\n"
            f"🚀 **XP Triplo:** `{'✅ Ativo' if player_data.get('xptriple') else '❌ Inativo'}`\n"
            f"💸 **Dinheiro Duplo:** `{'✅ Ativo' if player_data.get('money_double') else '❌ Inativo'}`"
        )
        embed.add_field(name="Detalhes do Fora-da-Lei", value=stats_value, inline=False)

        # --- Campo de Efeitos Ativos (se houver) ---
        if active_effects:
            embed.add_field(
                name="✨ Efeitos Ativos", value="\n".join(active_effects), inline=False
            )

        embed.set_footer(
            text=f"Outlaws RPG • {self.user.name}",
            icon_url=self.bot_user.display_avatar.url,
        )
        embed.timestamp = datetime.now()
        return embed

    def create_inventory_embed(self) -> discord.Embed:
        """
        Cria o embed do inventário do jogador.
        """
        player_data = get_player_data(self.user.id)
        if not player_data:
            return Embed(
                title="❌ Erro",
                description="Dados do jogador não encontrados.",
                color=Color.red(),
            )

        # Usar a cor do perfil para consistência visual
        embed = Embed(
            title=f"Inventário de {self.user.display_name}", color=self.user.color
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)

        inventory_items = player_data.get("inventory", {})
        if not inventory_items:
            embed.description = "🎒 *O inventário está vazio.*"
        else:
            item_list = []
            for item_id, amount in inventory_items.items():
                item_data = ITEMS_DATA.get(item_id, {})
                emoji = item_data.get("emoji", "❔")
                name = item_data.get("name", item_id.replace("_", " ").title())
                item_list.append(f"{emoji} **{name}** `x{amount}`")
            embed.description = "\n".join(item_list)

        embed.set_footer(
            text=f"Outlaws RPG • {self.user.name}",
            icon_url=self.bot_user.display_avatar.url,
        )
        embed.timestamp = datetime.now()
        return embed

    @ui.button(label="Perfil", style=ButtonStyle.primary, emoji="👤", disabled=True)
    async def profile_button(self, interaction: Interaction, button: ui.Button):
        self.profile_button.disabled = True
        self.inventory_button.disabled = False
        await self.original_interaction.edit_original_response(
            embed=self.create_profile_embed(), view=self
        )
        await interaction.response.defer()

    @ui.button(label="Inventário", style=ButtonStyle.secondary, emoji="🎒")
    async def inventory_button(self, interaction: Interaction, button: ui.Button):
        self.inventory_button.disabled = True
        self.profile_button.disabled = False
        await self.original_interaction.edit_original_response(
            embed=self.create_inventory_embed(), view=self
        )
        await interaction.response.defer()


class TravelView(ui.View):
    def __init__(self, current_location: str, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        # Ensure WORLD_MAP.get(current_location, {}) returns a dict, then check 'conecta'
        connected_locations = WORLD_MAP.get(current_location, {}).get("conecta", [])
        for dest in connected_locations:
            self.add_item(
                TravelButton(
                    label=WORLD_MAP.get(dest, {}).get(
                        "name", dest
                    ),  # Use location name for label
                    emoji=WORLD_MAP.get(dest, {}).get("emoji", "❓"),
                    destination_id=dest,  # Pass the actual ID to the button
                )
            )


class TravelButton(ui.Button):
    def __init__(self, label: str, emoji: str, destination_id: str):
        super().__init__(label=label, style=ButtonStyle.secondary, emoji=emoji)
        self.destination_id = destination_id  # Store the internal ID

    async def callback(self, i: Interaction):
        player_data = get_player_data(self.view.user_id)
        if not player_data:
            await i.response.send_message(
                "Erro ao encontrar sua ficha.", ephemeral=True
            )
            return

        # Check if the destination exists in WORLD_MAP to prevent invalid travel
        if self.destination_id not in WORLD_MAP:
            await i.response.send_message(
                f"Destino '{self.label}' inválido ou não existe no mapa.",
                ephemeral=True,
            )
            return

        player_data["location"] = self.destination_id  # Use the internal ID
        save_data()
        await i.response.edit_message(
            embed=Embed(
                title=f"✈️ Viagem Concluída",
                description=f"Você viajou e chegou em **{self.label}**.",
                color=Color.blue(),
            ),
            view=None,
        )
        self.view.stop()


class HelpView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @ui.select(
        placeholder="Escolha uma categoria da Wiki...",
        options=[
            discord.SelectOption(label="Introdução", emoji="📜", value="Introdução"),
            discord.SelectOption(
                label="Comandos Gerais", emoji="👤", value="Comandos Gerais"
            ),
            discord.SelectOption(
                label="Comandos de Ação", emoji="⚔️", value="Comandos de Ação"
            ),
            discord.SelectOption(
                label="Sistema de Classes", emoji="🛡️", value="Sistema de Classes"
            ),
            discord.SelectOption(
                label="Sistema de Combate", emoji="💥", value="Sistema de Combate"
            ),
            discord.SelectOption(
                label="Itens Especiais", emoji="💎", value="Itens Especiais"
            ),
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
                value="Ativa uma transformação de classe/estilo (ex: Lâmina Fantasma, Lorde Sanguinário, Bênção de Drácula, Lâmina Abençoada).",
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
            embed.description = (
                "**Espadachim**: Equilibrado. Pode se transformar em **Lâmina Fantasma** (Aumenta ataque e ataque especial, penaliza vida) ou **Lâmina Abençoada** (forma abençoada e mais poderosa).\n"
                "**Lutador**: Mais vida/ataque. Pode se transformar em **Punho de Aço** (Aumenta ataque e vida) ou **Punho de Adamantium** (forma abençoada e mais poderosa).\n"
                "**Atirador**: Mestre do dano especial. Pode se transformar em **Olho de Águia** (Aumenta ataque especial, reduz cooldown) ou **Visão Cósmica** (forma abençoada e mais poderosa).\n"
                "**Curandeiro**: Pode curar com `/curar`. Pode se transformar em **Bênção Vital** (Aumenta cura e vida) ou **Toque Divino** (forma abençoada e mais poderosa).\n"
                "**Vampiro**: Rouba vida e se transforma em uma besta sanguinária. Pode ativar a **Bênção de Drácula** para desviar e sugar HP! Sua transformação se chama **Lorde Sanguinário** (Aumenta muito ataque e ataque especial) ou **Rei da Noite** (forma abençoada e mais poderosa)."
            )
        elif topic == "Sistema de Combate":
            embed.description = "Batalhas são por turnos. Acertos Críticos (10% de chance) causam 50% a mais de dano!"
        elif topic == "Itens Especiais":
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
                },
            )

            embed.add_field(
                name=f"{potion_info['emoji']} {potion_info['name']} & {super_potion_info['emoji']} {super_potion_info['name']}",
                value=f"Restaura HP. Poção: {potion_info.get('heal', 0)}HP, Super Poção: {super_potion_info.get('heal', 0)}HP.",
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
                    f"Ex: **{healer_staff_info['emoji']} {healer_staff_info['name']}** (Curandeiro) aumenta cura em {int(healer_staff_info.get('effect_multiplier', 1.0) * 100 - 100)}%, "
                    f"**{fighter_gauntlet_info['emoji']} {fighter_gauntlet_info['name']}** (Lutador) aumenta ataque base em {int(fighter_gauntlet_info.get('attack_bonus_percent', 0.0) * 100)}% e vida máxima em {fighter_gauntlet_info.get('hp_bonus_flat', 0)}, "
                    f"**{shooter_sight_info['emoji']} {shooter_sight_info['name']}** (Atirador) reduz cooldown de ataque especial em {int(shooter_sight_info.get('cooldown_reduction_percent', 0.0) * 100)}%, "
                    f"**{ghost_sword_info['emoji']} {ghost_sword_info['name']}** (Espadachim) concede +{int(ghost_sword_info.get('attack_bonus_percent', 0.0) * 100)}% de ataque, mas penaliza -{int(ghost_sword_info.get('hp_penalty_percent', 0.0) * 100)}% do HP total."
                ),
                inline=False,
            )
            embed.add_field(
                name=f"{dracula_blessing_info['emoji']} {dracula_blessing_info['name']}",
                value=(
                    f"[Vampiro] Ativa uma bênção que concede {int(dracula_blessing_info.get('evasion_chance', 0.0) * 100)}% de chance de desviar de ataques inimigos e roubar {int(dracula_blessing_info.get('hp_steal_percent_on_evade', 0.0) * 100)}% do HP que seria o dano. "
                    f"Custa {dracula_blessing_info.get('cost_energy', 0)} energia e dura {dracula_blessing_info.get('duration_seconds', 0) // 60} minutos."
                ),
                inline=False,
            )
            embed.add_field(
                name=f"{king_henry_blessing_info['emoji']} {king_henry_blessing_info['name']}",
                value=(
                    f"[Aura] Ativa uma bênção poderosa com +{int(king_henry_blessing_info.get('attack_multiplier', 1.0) * 100 - 100)}% ATQ/ATQ Especial/HP e -{int(king_henry_blessing_info.get('cooldown_reduction_percent', 0.0) * 100)}% nos cooldowns. "
                    f"Custa {king_henry_blessing_info.get('cost_energy', 0)} energia e dura {king_henry_blessing_info.get('duration_seconds', 0) // 60} minutos."
                ),
                inline=False,
            )
        await i.response.edit_message(embed=embed)


class ShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        # Add buttons only for items explicitly defined in ITEMS_DATA with a price
        for item_id, item_data in ITEMS_DATA.items():
            if item_data.get("price") is not None:  # Check if price exists
                label = item_data.get("name", item_id.replace("_", " ").title())
                emoji = item_data.get("emoji", "💰")

                # Special handling for "unlockable" items in the shop
                if item_id in ["bencao_dracula", "bencao_rei_henrique"]:
                    label = f"Desbloquear {item_data.get('name', item_id.replace('_', ' ').title())}"

                self.add_item(
                    self.BuyButton(
                        item_id=item_id,
                        price=item_data["price"],
                        label=label,
                        emoji=emoji,
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
            elif self.item_id == "bencao_rei_henrique":
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
            elif item_info.get(
                "class_restriction"
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
            unique_items = [
                "cajado_curandeiro",
                "manopla_lutador",
                "mira_semi_automatica",
                "espada_fantasma",
                "amuleto_de_pedra",
                "bencao_dracula",
                "bencao_rei_henrique",
                "invocador",  # Invocador is also unique, but consumable (bought to use, not to keep)
            ]
            if (
                self.item_id in unique_items
                and item_info.get("consumable", False) == False
            ):  # Only apply for non-consumable uniques
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
            if self.item_id == "manopla_lutador" and player_data["class"] == "Lutador":
                hp_gain_from_item = ITEMS_DATA["manopla_lutador"].get(
                    "hp_bonus_flat", 0
                )
                player_data["max_hp"] += hp_gain_from_item
                player_data["hp"] = min(
                    player_data["hp"] + hp_gain_from_item, player_data["max_hp"]
                )
            elif (
                self.item_id == "espada_fantasma"
                and player_data["class"] == "Espadachim"
            ):
                hp_penalty_percent = ITEMS_DATA["espada_fantasma"].get(
                    "hp_penalty_percent", 0.0
                )
                hp_penalty_from_item = int(player_data["max_hp"] * hp_penalty_percent)
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
    if get_player_data(i.user.id):  # This check now uses the improved get_player_data
        await i.response.send_message("Você já possui uma ficha!", ephemeral=True)
        return
    await i.response.send_message(
        embed=Embed(
            title="Criação de Personagem",
            description="Escolha os fundamentos do seu personagem.",
            color=Color.blurple(),
        ),
        view=ClassChooserView(),
        ephemeral=True,  # Make character creation ephemeral until confirmed
    )


class AddFieldModal(ui.Modal, title="Adicionar Campo ao Embed"):
    def __init__(self):
        super().__init__(timeout=300)
        self.field_name = ui.TextInput(
            label="Nome do Campo",
            placeholder="Ex: Requisitos, Horário",
            max_length=256,
            required=True,
        )
        self.field_value = ui.TextInput(
            label="Valor do Campo",
            placeholder="Ex: Nível 10+, Sábado 19h",
            style=discord.TextStyle.paragraph,
            required=True,
        )
        self.field_inline = ui.TextInput(
            label="Campo na mesma linha? (sim/não)",
            placeholder="Padrão é 'não'.",
            max_length=3,
            required=False,
        )
        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.field_inline)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.stop()


@bot.tree.command(
    name="criar_embed",
    description="[ADMIN] Crie um embed personalizado interativamente.",
)
@commands.has_permissions(administrator=True)
async def criar_embed(i: Interaction):
    initial_embed = Embed(
        title="Novo Embed",
        description="Clique nos botões para editar.",
        color=Color.blue(),
    )
    initial_embed.set_footer(
        text="Criador de Embed", icon_url=bot.user.display_avatar.url
    )
    initial_embed.timestamp = datetime.now()

    view = EmbedCreatorView(
        initial_embed, i.user.id
    )  # Removed bot_ref, no longer needed directly

    await i.response.send_message(embed=initial_embed, view=view, ephemeral=True)
    view.message = await i.original_response()


class EmbedCreatorView(ui.View):
    def __init__(self, initial_embed: Embed, author_id: int):  # Removed bot_ref
        super().__init__(timeout=600)
        self.embed = initial_embed
        self.author_id = author_id
        self.fields_added = 0

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                content="Tempo limite para edição do embed atingido.", view=self
            )
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Apenas o criador do embed pode interagir com este menu.",
                ephemeral=True,
            )
            return False
        return True

    @ui.button(label="Editar Título/Descrição", style=ButtonStyle.primary, emoji="✍️")
    async def edit_basic_info(self, interaction: Interaction, button: ui.Button):
        class BasicInfoModal(ui.Modal, title="Editar Título e Descrição"):
            def __init__(self, current_title, current_description):
                super().__init__(timeout=300)
                self.title_input = ui.TextInput(
                    label="Novo Título",
                    default=current_title,
                    max_length=256,
                    required=True,
                )
                self.description_input = ui.TextInput(
                    label="Nova Descrição",
                    default=current_description,
                    style=discord.TextStyle.paragraph,
                    required=False,
                )
                self.add_item(self.title_input)
                self.add_item(self.description_input)

            async def on_submit(self, modal_interaction: Interaction):
                self.view.embed.title = self.title_input.value
                self.view.embed.description = self.description_input.value or None
                await modal_interaction.response.edit_message(
                    embed=self.view.embed, view=self.view
                )
                # Removed self.stop(), let the modal manage its own lifecycle, but the view remains active

        modal = BasicInfoModal(
            self.embed.title or "",
            self.embed.description or "",
        )
        modal.view = self  # Attach the parent view
        await interaction.response.send_modal(modal)

    @ui.button(label="Adicionar Campo", style=ButtonStyle.secondary, emoji="➕")
    async def add_field(self, interaction: Interaction, button: ui.Button):
        if self.fields_added >= 10:
            await interaction.response.send_message(
                "Você atingiu o limite de 10 campos por embed.", ephemeral=True
            )
            return

        modal = AddFieldModal()
        await interaction.response.send_modal(modal)
        await modal.wait()  # Wait for the modal to be submitted or timed out

        if modal.field_name.value and modal.field_value.value:
            name = modal.field_name.value
            value = modal.field_value.value
            inline = (
                modal.field_inline.value.lower() == "sim"
                if modal.field_inline.value
                else False
            )
            self.embed.add_field(name=name, value=value, inline=inline)
            self.fields_added += 1
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            # If the modal was dismissed or inputs were empty
            await interaction.followup.send(
                "Nenhum campo foi adicionado.", ephemeral=True
            )

    @ui.button(label="Editar Imagens/Cores", style=ButtonStyle.secondary, emoji="🖼️")
    async def edit_media(self, interaction: Interaction, button: ui.Button):
        class MediaModal(ui.Modal, title="Editar Mídia e Cores"):
            def __init__(
                self,
                current_thumb,
                current_image,
                current_color_hex,
                current_author_name,
                current_author_icon,
            ):
                super().__init__(timeout=300)
                self.thumbnail_input = ui.TextInput(
                    label="URL da Miniatura (Thumbnail)",
                    placeholder="Cole a URL da imagem aqui",
                    default=current_thumb or "",
                    required=False,
                )
                self.image_input = ui.TextInput(
                    label="URL da Imagem Principal",
                    placeholder="Cole a URL da imagem aqui",
                    default=current_image or "",
                    required=False,
                )
                self.color_input = ui.TextInput(
                    label="Cor Hexadecimal (Ex: #FF00FF)",
                    placeholder="Ex: #FF00FF",
                    default=current_color_hex or "",
                    max_length=7,
                    required=False,
                )
                self.author_name_input = ui.TextInput(
                    label="Nome do Autor (opcional)",
                    placeholder="Ex: Equipe Outlaws",
                    default=current_author_name or "",
                    required=False,
                )
                self.author_icon_input = ui.TextInput(
                    label="URL do Ícone do Autor (opcional)",
                    placeholder="URL do avatar do autor",
                    default=current_author_icon or "",
                    required=False,
                )
                self.add_item(self.thumbnail_input)
                self.add_item(self.image_input)
                self.add_item(self.color_input)
                self.add_item(self.author_name_input)
                self.add_item(self.author_icon_input)

            async def on_submit(self, modal_interaction: Interaction):
                thumb_url = self.thumbnail_input.value.strip() or None
                self.view.embed.set_thumbnail(url=thumb_url)

                image_url = self.image_input.value.strip() or None
                self.view.embed.set_image(url=image_url)

                if self.color_input.value:
                    try:
                        self.view.embed.color = Color.from_str(self.color_input.value)
                    except ValueError:
                        await modal_interaction.followup.send(
                            "Cor hexadecimal inválida. Use o formato #RRGGBB.",
                            ephemeral=True,
                        )
                        return
                else:
                    self.view.embed.color = (
                        Color.blue()
                    )  # Default color if input is empty

                author_name = self.author_name_input.value.strip()
                author_icon = self.author_icon_input.value.strip() or None
                if author_name:
                    self.view.embed.set_author(name=author_name, icon_url=author_icon)
                else:
                    self.view.embed.remove_author()  # Correctly removes author if name is empty

                await modal_interaction.response.edit_message(
                    embed=self.view.embed, view=self.view
                )

        current_thumb = self.embed.thumbnail.url if self.embed.thumbnail else None
        current_image = self.embed.image.url if self.embed.image else None
        current_color_hex = str(self.embed.color) if self.embed.color else ""
        current_author_name = self.embed.author.name if self.embed.author else None
        current_author_icon = self.embed.author.icon_url if self.embed.author else None

        modal = MediaModal(
            current_thumb,
            current_image,
            current_color_hex,
            current_author_name,
            current_author_icon,
        )
        modal.view = self  # Pass the parent view to the modal
        await interaction.response.send_modal(modal)

    @ui.button(label="Limpar Campos", style=ButtonStyle.danger, emoji="🧹")
    async def clear_fields(self, interaction: Interaction, button: ui.Button):
        self.embed.clear_fields()
        self.fields_added = 0
        await interaction.response.edit_message(embed=self.embed, view=self)

    @ui.button(label="Enviar Embed", style=ButtonStyle.success, emoji="✅", row=2)
    async def send_embed(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Embed enviado!", ephemeral=True)
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)  # Edit the original ephemeral message
        except discord.HTTPException:
            pass

        try:
            await interaction.channel.send(embed=self.embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "Não tenho permissão para enviar o embed neste canal.", ephemeral=True
            )
        self.stop()


@bot.tree.command(
    name="perfil",
    description="Mostra seu perfil de fora-da-lei com um layout profissional.",
)
@app_commands.check(check_player_exists)
async def perfil(i: Interaction, membro: discord.Member = None):
    target_user = membro or i.user
    player_data = get_player_data(target_user.id)  # Use the improved get_player_data
    if not player_data:
        await i.response.send_message(
            "Essa pessoa ainda não é um fora-da-lei.", ephemeral=True
        )
        return

    await i.response.defer()

    view = ProfileView(target_user, bot.user, i)
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
@app_commands.check(check_player_exists)  # Added check
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
        player_data["hp"] += (
            quantidade * 5
        )  # Also restore current HP when max HP increases
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

    # Defer the response as fetching members can take time
    await i.response.defer()

    guild_members = {}
    if i.guild:  # Ensure it's not a DM
        try:
            # Fetch all members to get up-to-date display names and avatars
            async for member in i.guild.fetch_members(limit=None):
                guild_members[member.id] = member
        except discord.Forbidden:
            print(
                f"Bot lacks 'Members Intent' or 'Read Members' permission in guild {i.guild.name}. Cannot fetch all members for ranking."
            )
            # Fallback to names in player_database if members can't be fetched
        except Exception as e:
            print(f"Error fetching guild members for ranking: {e}")

    # Sort based on 'kills', then 'level' if kills are tied, then 'money'
    sorted_players = sorted(
        player_database.values(),
        key=lambda p: (p.get("kills", 0), p.get("level", 1), p.get("money", 0)),
        reverse=True,
    )

    embed = Embed(
        title="🏆 Ranking de MVPs - OUTLAWS 🏆",
        description="Os fora-da-lei mais temidos do servidor.",
        color=Color.gold(),
    )

    rank_entries = []
    # Using enumerate with a slice for the top 10 players
    for idx, player_data in enumerate(sorted_players[:10]):
        # Find the original user_id (string key) for the player_data dict
        player_id_str = None
        for uid_str, data_val in player_database.items():
            if (
                data_val == player_data
            ):  # Compare by value, assumes player_data is unique
                player_id_str = uid_str
                break

        if not player_id_str:  # Should not happen if data integrity is maintained
            continue

        player_id = int(player_id_str)
        member = guild_members.get(player_id)

        player_display_name = (
            member.display_name if member else player_data.get("name", "Desconhecido")
        )
        avatar_url = (
            member.display_avatar.url  # Use display_avatar for dynamic and default avatars
            if member and member.display_avatar
            else "https://discord.com/assets/f9bb9c17af1b5c2a048a1d13f9c646f8.png"  # Default Discord avatar
        )

        # Hyperlink the name to their avatar URL
        rank_entries.append(
            f"**{idx+1}.** [{player_display_name}]({avatar_url})\n"
            f"  **Abates:** {player_data.get('kills', 0)} | "
            f"**Mortes:** {player_data.get('deaths', 0)} | "
            f"**Recompensa:** ${player_data.get('bounty', 0)}"
        )

    if rank_entries:
        embed.description = "\n\n".join(rank_entries)
    else:
        embed.description = "Nenhum jogador no ranking ainda."

    embed.set_footer(text="A glória aguarda os mais audazes!")
    await i.edit_original_response(embed=embed)


## Comandos de Ação no Mundo
@bot.tree.command(
    name="viajar", description="Viaja para uma nova localização no mundo de OUTLAWS."
)
@app_commands.check(check_player_exists)
async def viajar(i: Interaction):
    player_data = get_player_data(i.user.id)
    # Ensure current_location has a default if not set for some reason
    current_location_id = player_data.get("location", STARTING_LOCATION)

    # Get the display name for the current location
    current_location_name = WORLD_MAP.get(current_location_id, {}).get(
        "name", current_location_id.replace("_", " ").title()
    )

    view = TravelView(current_location_id, i.user.id)
    if not view.children:
        await i.response.send_message(
            "Não há para onde viajar a partir daqui.", ephemeral=True
        )
        return
    embed = Embed(
        title=f"✈️ Para Onde Vamos?",
        description=f"Você está em **{current_location_name}**. Escolha seu próximo destino.",
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
            f"Você já trabalhou recentemente. Tente novamente em **{30 - (now - last_work):.1f} segundos**.",
            ephemeral=True,
        )
        return

    # Ensure enemies list is not empty for current location if applicable
    current_location_type = WORLD_MAP.get(
        player_data.get("location", STARTING_LOCATION), {}
    ).get("type")

    # Removed direct dependency on ENEMIES for jobs, as jobs are generic now.
    # If you later want location-specific jobs, adjust this.
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
        xp_message = f"e **{xp_gain}** XP"

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
    # Call level-up check using bot instance
    await bot.check_and_process_levelup(i.user, player_data, i)
    await i.response.send_message(embed=embed)


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

    # Loop through ITEMS_DATA and add to embed if they have a price
    for item_id, item_info in ITEMS_DATA.items():
        if item_info.get("price") is not None:
            name = item_info.get("name", item_id.replace("_", " ").title())
            emoji = item_info.get("emoji", "❔")
            price = item_info.get("price", 0)
            description = item_info.get("description", "Sem descrição.")

            # Append specific details based on item type
            if "heal" in item_info:
                description = f"Restaura {item_info['heal']} HP."
            elif item_id == "invocador":
                description = "Invoca o terrível boss."
            elif "class_restriction" in item_info:
                class_bonus_details = []
                if "attack_bonus_percent" in item_info:
                    class_bonus_details.append(
                        f"Ataque +{int(item_info['attack_bonus_percent'] * 100)}%"
                    )
                if "hp_bonus_flat" in item_info:
                    class_bonus_details.append(f"HP +{item_info['hp_bonus_flat']}")
                if "effect_multiplier" in item_info:
                    class_bonus_details.append(
                        f"Cura +{int(item_info['effect_multiplier'] * 100 - 100)}%"
                    )
                if "cooldown_reduction_percent" in item_info:
                    class_bonus_details.append(
                        f"Cooldown Especial -{int(item_info['cooldown_reduction_percent'] * 100)}%"
                    )
                if "hp_penalty_percent" in item_info:
                    class_bonus_details.append(
                        f"HP -{int(item_info['hp_penalty_percent'] * 100)}% (penalidade)"
                    )

                description = f"[{item_info['class_restriction']}] Bônus: {', '.join(class_bonus_details) or 'Nenhum'}"
            elif item_id in ["bencao_dracula", "bencao_rei_henrique"]:
                description = f"Desbloqueia uma bênção poderosa. Duração: {item_info.get('duration_seconds', 0) // 60} minutos, Custo de Energia: {item_info.get('cost_energy', 0)}."
                if item_id == "bencao_dracula":
                    description = f"[Vampiro] Desbloqueia a transformação temporária que desvia ataques e suga HP."

            embed.add_field(
                name=f"{emoji} {name} (ID: `{item_id}`)",
                value=f"{description} Custa **${price}**.",
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
    # Dynamic initial base for cost calculation (more robust)
    initial_base_value = (
        INITIAL_ATTACK if atributo.value == "attack" else INITIAL_SPECIAL_ATTACK
    )

    # Calculate cost based on current base stat relative to initial stat
    cost = 100 + (base_stat_current - initial_base_value) * cost_per_point

    if player_data["money"] < cost:
        await i.response.send_message(
            f"Você precisa de ${cost} para aprimorar.", ephemeral=True
        )
        return

    player_data["money"] -= cost
    player_data[attr_key] += 2  # Increases the base stat by 2 per upgrade
    save_data()

    # Calculate next cost for the message (current cost + 2 points * cost_per_point)
    next_cost = 100 + ((player_data[attr_key] - initial_base_value) * cost_per_point)

    await i.response.send_message(
        f"✨ Aprimoramento concluído! Seu {atributo.name} base aumentou para `{player_data[attr_key]}`. Próximo aprimoramento custará **${next_cost}**."
    )


## Comandos de Combate e Habilidades
@bot.tree.command(
    name="cacar",
    description="Caça uma criatura na sua localização atual (combate por turnos).",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_wilderness)
@app_commands.checks.cooldown(
    1, 15, key=lambda i: i.user.id
)  # Add a cooldown for hunting
async def cacar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["status"] == "dead":
        await i.response.send_message("Mortos não caçam.", ephemeral=True)
        return

    # Ensure location is valid and has enemies
    location_enemies = ENEMIES.get(player_data.get("location"))
    if not location_enemies:
        await i.response.send_message(
            f"Não há criaturas para caçar em {WORLD_MAP.get(player_data['location'], {}).get('name', 'sua localização atual')}.",
            ephemeral=True,
        )
        return

    await i.response.defer()

    enemy_template = random.choice(location_enemies)
    enemy = enemy_template.copy()
    await run_turn_based_combat(bot, i, player_data, enemy)  # Pass bot instance


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

    # Pre-check energy for special attack
    if primeiro_ataque.value == "especial":
        cost_energy_special = TRANSFORM_COST

        # Apply all relevant cooldown reductions
        if player_data.get("aura_blessing_active"):
            blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
            cost_energy_special = max(
                1,
                int(
                    cost_energy_special
                    * (1 - blessing_info.get("cooldown_reduction_percent", 0.0))
                ),
            )

        if player_data.get("current_transformation"):
            transform_name = player_data["current_transformation"]
            class_name = player_data["class"]
            transform_info = CLASS_TRANSFORMATIONS.get(class_name, {}).get(
                transform_name
            )
            if transform_info and "cooldown_reduction_percent" in transform_info:
                cost_energy_special = max(
                    1,
                    int(
                        cost_energy_special
                        * (1 - transform_info["cooldown_reduction_percent"])
                    ),
                )

        # Mira Semi-Automática check
        mira_semi_automatica_info = ITEMS_DATA.get("mira_semi_automatica", {})
        if (
            player_data["inventory"].get("mira_semi_automatica", 0) > 0
            and player_data["class"] == "Atirador"
        ):
            cost_energy_special = max(
                1,
                int(
                    cost_energy_special
                    * (
                        1
                        - mira_semi_automatica_info.get(
                            "cooldown_reduction_percent", 0.0
                        )
                    )
                ),
            )

        if player_data.get("energy", 0) < cost_energy_special:
            await i.response.send_message(
                f"Você não tem energia suficiente ({cost_energy_special}) para um Ataque Especial inicial! Use Ataque Básico ou recupere energia.",
                ephemeral=True,
            )
            return

    await i.response.defer()

    enemy = {
        "name": "Ex-Cavaleiro Renegado",
        "hp": 320,
        "attack": 95,
        "xp": 390,
        "money": 400,
        "thumb": "https://c.tenor.com/ebFt6wJWEu8AAAAC/tenor.gif",
    }
    await run_turn_based_combat(bot, i, player_data, enemy)  # Pass bot instance


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

    # Added check for AFK status before PVP
    if raw_target_data.get("status") == "afk":
        await i.response.send_message(
            f"{alvo.display_name} está em modo AFK e não pode ser atacado.",
            ephemeral=True,
        )
        return

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

    # Apply cooldown reductions
    if raw_attacker_data.get("aura_blessing_active"):
        blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
        cooldown_duration = int(
            cooldown_duration
            * (1 - blessing_info.get("cooldown_reduction_percent", 0.0))
        )

    if raw_attacker_data.get("current_transformation"):
        transform_name = raw_attacker_data["current_transformation"]
        class_name = raw_attacker_data["class"]
        transform_info = CLASS_TRANSFORMATIONS.get(class_name, {}).get(transform_name)
        if transform_info and "cooldown_reduction_percent" in transform_info:
            cooldown_duration = int(
                cooldown_duration * (1 - transform_info["cooldown_reduction_percent"])
            )

    # Mira Semi-Automática reduction
    mira_semi_automatica_info = ITEMS_DATA.get("mira_semi_automatica", {})
    if (
        raw_attacker_data["inventory"].get("mira_semi_automatica", 0) > 0
        and raw_attacker_data["class"] == "Atirador"
    ):
        cooldown_duration = int(
            cooldown_duration
            * (1 - mira_semi_automatica_info.get("cooldown_reduction_percent", 0.0))
        )

    if now - raw_attacker_data["cooldowns"].get(cooldown_key, 0) < cooldown_duration:
        await i.response.send_message(
            f"Seu {estilo.name} está em cooldown! Tente novamente em **{cooldown_duration - (now - raw_attacker_data['cooldowns'].get(cooldown_key, 0)):.1f}s**.",
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

    initial_target_hp = raw_target_data["hp"]
    raw_target_data["hp"] -= damage

    embed = Embed(color=Color.red())

    # Calculate Dracula evasion chance for target
    dracula_evasion_chance = ITEMS_DATA.get("bencao_dracula", {}).get(
        "evasion_chance", 0.0
    )
    if raw_target_data.get("current_transformation") == "Rei da Noite":
        vampire_blessed_transform_info = CLASS_TRANSFORMATIONS.get("Vampiro", {}).get(
            "Rei da Noite", {}
        )
        dracula_evasion_chance += vampire_blessed_transform_info.get(
            "evasion_chance_bonus", 0.0
        )

    # Check for target evasion or amulet
    if raw_target_data["hp"] <= 0:
        if (
            raw_target_data["class"] == "Vampiro"
            and raw_target_data.get("bencao_dracula_active", False)
            and random.random() < dracula_evasion_chance
        ):
            hp_steal_percent_on_evade = ITEMS_DATA.get("bencao_dracula", {}).get(
                "hp_steal_percent_on_evade", 0.0
            )
            hp_stolen_on_evade = int(damage * hp_steal_percent_on_evade)
            raw_target_data["hp"] = min(
                target_stats["max_hp"], initial_target_hp + hp_stolen_on_evade
            )

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
            bounty_claimed = raw_target_data.get("bounty", 0)
            raw_target_data["bounty"] = 0  # Reset bounty on death

            money_stolen = int(raw_target_data["money"] * BOUNTY_PERCENTAGE)
            raw_attacker_data["money"] += money_stolen + bounty_claimed
            raw_attacker_data["kills"] += 1
            raw_attacker_data["bounty"] += 100  # Add bounty for successful kill

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
    else:
        embed.title = f"⚔️ Duelo de Fora-da-Lei ⚔️"
        embed.description = f"{crit_msg}{i.user.display_name} usou **{estilo.name}** em {alvo.display_name} e causou **{damage}** de dano!{heal_info_msg}\n{alvo.display_name} agora tem **{raw_target_data['hp']}/{target_stats['max_hp']}** HP."

    raw_attacker_data["cooldowns"][cooldown_key] = now
    save_data()
    await i.response.send_message(embed=embed)


@bot.tree.command(
    name="atacar_boss", description="Ataca o boss global quando ele estiver ativo."
)
@app_commands.check(check_player_exists)
@app_commands.checks.cooldown(
    1, 5, key=lambda i: i.user.id
)  # Shorter cooldown for boss attacks
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

    # Apply cooldown reductions for boss attack
    if raw_player_data.get("aura_blessing_active"):
        blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
        cooldown_duration = int(
            cooldown_duration
            * (1 - blessing_info.get("cooldown_reduction_percent", 0.0))
        )

    if raw_player_data.get("current_transformation"):
        transform_name = raw_player_data["current_transformation"]
        class_name = raw_player_data["class"]
        transform_info = CLASS_TRANSFORMATIONS.get(class_name, {}).get(transform_name)
        if transform_info and "cooldown_reduction_percent" in transform_info:
            cooldown_duration = int(
                cooldown_duration * (1 - transform_info["cooldown_reduction_percent"])
            )

    # Mira Semi-Automática reduction for boss attacks
    mira_semi_automatica_info = ITEMS_DATA.get("mira_semi_automatica", {})
    if (
        raw_player_data["inventory"].get("mira_semi_automatica", 0) > 0
        and raw_player_data["class"] == "Atirador"
    ):
        cooldown_duration = int(
            cooldown_duration
            * (1 - mira_semi_automatica_info.get("cooldown_reduction_percent", 0.0))
        )

    last_attack = raw_player_data["cooldowns"].get(cooldown_key, 0)

    if now - last_attack < cooldown_duration:
        await i.response.send_message(
            f"Seu {estilo.name} contra o boss está em cooldown! Tente novamente em **{cooldown_duration - (now - last_attack):.1f}s**.",
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
        if BOSS_DATA["channel_id"]:
            boss_channel = bot.get_channel(BOSS_DATA["channel_id"])
            if boss_channel:
                await boss_channel.send(embed=embed)
        else:  # Fallback if channel_id is not set
            await i.channel.send(embed=embed)

        for p_id_str in BOSS_DATA["participants"]:  # Iterate over string IDs
            if p_data := get_player_data(
                p_id_str
            ):  # Use get_player_data (handles int/str)
                boss_money_raw = 5000
                if p_data.get("money_double") is True:
                    boss_money = boss_money_raw * 2
                else:
                    boss_money = boss_money_raw
                p_data["money"] += boss_money

                boss_xp_raw = 1000
                xp_multiplier_passive = ITEMS_DATA.get("habilidade_inata", {}).get(
                    "xp_multiplier_passive", 0.0
                )

                if p_data.get("style") == "Habilidade Inata":
                    boss_xp_raw = int(boss_xp_raw * (1 + xp_multiplier_passive))

                if p_data.get("xptriple") is True:
                    boss_xp = boss_xp_raw * 3
                else:
                    boss_xp = boss_xp_raw

                p_data["xp"] += boss_xp

                for item_drop_id, quantity_drop in BOSS_DATA.get("drops", {}).items():
                    item_drop_info = ITEMS_DATA.get(item_drop_id)
                    if not item_drop_info:
                        print(
                            f"Warning: Dropped item '{item_drop_id}' is not defined in ITEMS_DATA."
                        )
                        continue

                    if item_drop_id == "amuleto_de_pedra":
                        if p_data["inventory"].get("amuleto_de_pedra", 0) == 0:
                            p_data["inventory"]["amuleto_de_pedra"] = 1
                    else:
                        p_data["inventory"][item_drop_id] = (
                            p_data["inventory"].get(item_drop_id, 0) + quantity_drop
                        )

                # Ensure user object is fetched correctly for level up message
                member_for_levelup = bot.get_user(int(p_id_str))
                if member_for_levelup:  # Only proceed if user is found
                    await bot.check_and_process_levelup(
                        member_for_levelup,
                        p_data,
                        i.channel,  # Send to the channel where boss was defeated
                    )

        # Reset BOSS_DATA only after all participants have been processed
        BOSS_DATA.update(
            {
                "is_active": False,
                "hp": 0,
                "participants": [],
                "channel_id": None,
                "current_boss_name": "Colosso de Pedra",
            }  # Reset current_boss_name
        )
        save_data()


@bot.tree.command(name="usar", description="Usa um item do seu inventário.")
@app_commands.check(check_player_exists)
async def usar(i: Interaction, item_id: str):
    item_id = item_id.lower()
    raw_player_data = get_player_data(i.user.id)

    if (
        item_id not in raw_player_data["inventory"]
        or raw_player_data["inventory"].get(item_id, 0) < 1
    ):  # Use .get with default 0 for safety
        await i.response.send_message("Você não possui este item!", ephemeral=True)
        return

    item_info = ITEMS_DATA.get(item_id)
    if not item_info:
        await i.response.send_message("Este item não é reconhecido.", ephemeral=True)
        return

    # Check if item is an equipable item that gives passive bonuses (and shouldn't be "used")
    # Also include blessings that are "unlocked" permanently and activated via /transformar or /ativar_bencao_aura
    if (
        item_info.get("type") == "equipable"
        or item_info.get("type") == "blessing_unlock"
    ):
        await i.response.send_message(
            f"Você tem o(a) **{item_info['name']}** no seu inventário! Seus efeitos são aplicados automaticamente, ou ative-o com `/transformar` ou `/ativar_bencao_aura`.",
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
                "current_boss_name": "Colosso de Pedra",  # Ensure this is consistently set
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

    # Only decrement inventory count for consumable items (not permanent ones)
    if item_info.get("consumable", False):
        if (
            raw_player_data["inventory"].get(item_id) == 0
        ):  # Clean up if quantity drops to 0
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

    # Base cooldown for healing
    cooldown_healing = 45

    # Apply Aura Blessing reduction
    if raw_player_data.get("aura_blessing_active"):
        blessing_info = ITEMS_DATA.get("bencao_rei_henrique", {})
        cooldown_healing = int(
            cooldown_healing
            * (1 - blessing_info.get("cooldown_reduction_percent", 0.0))
        )

    # Apply Transformation reduction
    if raw_player_data.get("current_transformation"):
        transform_name = raw_player_data["current_transformation"]
        class_name = raw_player_data["class"]
        transform_info = CLASS_TRANSFORMATIONS.get(class_name, {}).get(transform_name)
        if transform_info and "cooldown_reduction_percent" in transform_info:
            cooldown_healing = int(
                cooldown_healing * (1 - transform_info["cooldown_reduction_percent"])
            )

    if now - last_heal < cooldown_healing:
        await i.response.send_message(
            f"Sua cura está em cooldown! Tente novamente em **{cooldown_healing - (now - last_heal):.1f}s**.",
            ephemeral=True,
        )
        return

    heal_amount = random.randint(
        int(player_stats["special_attack"] * 1.5),
        int(player_stats["special_attack"] * 2.5),
    )

    # Apply healing multiplier from items/transformations (calculated in effective stats)
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
        app_commands.Choice(
            name="Lâmina Fantasma (Espadachim)", value="Lâmina Fantasma"
        ),
        app_commands.Choice(name="Punho de Aço (Lutador)", value="Punho de Aço"),
        app_commands.Choice(name="Olho de Águia (Atirador)", value="Olho de Águia"),
        app_commands.Choice(name="Bênção Vital (Curandeiro)", value="Bênção Vital"),
        app_commands.Choice(
            name="Lorde Sanguinário (Vampiro)", value="Lorde Sanguinário"
        ),
        app_commands.Choice(
            name="Lâmina Abençoada (Espadachim - Aura)", value="Lâmina Abençoada"
        ),
        app_commands.Choice(
            name="Punho de Adamantium (Lutador - Aura)", value="Punho de Adamantium"
        ),
        app_commands.Choice(
            name="Visão Cósmica (Atirador - Aura)", value="Visão Cósmica"
        ),
        app_commands.Choice(
            name="Toque Divino (Curandeiro - Aura)", value="Toque Divino"
        ),
        app_commands.Choice(name="Rei da Noite (Vampiro - Aura)", value="Rei da Noite"),
        app_commands.Choice(
            name="Bênção de Drácula (Vampiro)", value="Bênção de Drácula"
        ),
    ]
)
@app_commands.check(check_player_exists)
async def transformar(i: Interaction, forma: app_commands.Choice[str]):
    raw_player_data = get_player_data(i.user.id)
    player_class = raw_player_data["class"]
    player_style = raw_player_data["style"]

    # Handle class-specific transformations
    if forma.value in CLASS_TRANSFORMATIONS.get(player_class, {}):
        if raw_player_data.get("current_transformation"):
            await i.response.send_message(
                f"Você já está na forma {raw_player_data.get('current_transformation', 'transformada')}! Use `/destransformar` para retornar ao normal.",
                ephemeral=True,
            )
            return

        transform_info = CLASS_TRANSFORMATIONS[player_class].get(forma.value)
        if (
            not transform_info
        ):  # Should not happen with app_commands.choices but good for safety
            await i.response.send_message(
                "Dados de transformação não encontrados.",
                ephemeral=True,
            )
            return

        # Check for Aura blessing requirement for blessed forms
        if transform_info.get("required_blessing") == "bencao_rei_henrique":
            if not raw_player_data.get("aura_blessing_active"):
                await i.response.send_message(
                    f"Você precisa ter a **Benção do Rei Henrique** ativa para usar a transformação **{forma.value}**.",
                    ephemeral=True,
                )
                return

        if raw_player_data["energy"] < transform_info["cost_energy"]:
            await i.response.send_message(
                f"Energia insuficiente para se transformar em {forma.value} ({transform_info['cost_energy']} energia)!",
                ephemeral=True,
            )
            return

        raw_player_data["current_transformation"] = forma.value
        raw_player_data["transform_end_time"] = (
            datetime.now().timestamp() + transform_info["duration_seconds"]
        )
        raw_player_data["energy"] -= transform_info["cost_energy"]

        embed = Embed(
            title=f"{transform_info['emoji']} TRANSFORMAÇÃO: {forma.value} {transform_info['emoji']}",
            description=f"{i.user.display_name} liberou seu poder oculto e se tornou um(a) {forma.value} por {transform_info['duration_seconds'] // 60} minutos!",
            color=Color.dark_red() if player_class == "Vampiro" else Color.gold(),
        )
        await i.response.send_message(embed=embed)
        save_data()
        return

    # Handle special blessings that are activated via /transformar
    elif forma.value == "Bênção de Drácula":
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
        if not dracula_info:
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
        app_commands.Choice(
            name="Lâmina Fantasma (Espadachim)", value="Lâmina Fantasma"
        ),
        app_commands.Choice(name="Punho de Aço (Lutador)", value="Punho de Aço"),
        app_commands.Choice(name="Olho de Águia (Atirador)", value="Olho de Águia"),
        app_commands.Choice(name="Bênção Vital (Curandeiro)", value="Bênção Vital"),
        app_commands.Choice(
            name="Lorde Sanguinário (Vampiro)", value="Lorde Sanguinário"
        ),
        app_commands.Choice(
            name="Lâmina Abençoada (Espadachim - Aura)", value="Lâmina Abençoada"
        ),
        app_commands.Choice(
            name="Punho de Adamantium (Lutador - Aura)", value="Punho de Adamantium"
        ),
        app_commands.Choice(
            name="Visão Cósmica (Atirador - Aura)", value="Visão Cósmica"
        ),
        app_commands.Choice(
            name="Toque Divino (Curandeiro - Aura)", value="Toque Divino"
        ),
        app_commands.Choice(name="Rei da Noite (Vampiro - Aura)", value="Rei da Noite"),
        app_commands.Choice(
            name="Benção do Rei Henrique (Aura)", value="bencao_rei_henrique"
        ),
        app_commands.Choice(name="Bênção de Drácula (Vampiro)", value="bencao_dracula"),
        app_commands.Choice(name="Todas as Transformações", value="all"),
    ]
)
@app_commands.check(check_player_exists)
async def destransformar(i: Interaction, forma: app_commands.Choice[str]):
    raw_player_data = get_player_data(i.user.id)
    deactivated_any = False
    messages = []

    if forma.value == "all":
        if raw_player_data.get("current_transformation"):
            transform_name = raw_player_data["current_transformation"]
            raw_player_data["current_transformation"] = None
            raw_player_data["transform_end_time"] = 0
            deactivated_any = True
            messages.append(
                f"Você retornou da forma **{transform_name}** para sua forma normal de {raw_player_data['class']}."
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
            raw_player_data["energy"] = min(
                MAX_ENERGY, raw_player_data["energy"] + 1
            )  # Regain some energy
            save_data()
            messages.append("Você recuperou 1 de energia.")
            await i.response.send_message("\n".join(messages))
        else:
            await i.response.send_message(
                "Você não tem nenhuma transformação ativa para desativar.",
                ephemeral=True,
            )
        return

    # Check for specific class transformations
    class_transforms_for_player = CLASS_TRANSFORMATIONS.get(
        raw_player_data["class"], {}
    )
    if (
        forma.value in class_transforms_for_player
        and raw_player_data.get("current_transformation") == forma.value
    ):
        raw_player_data["current_transformation"] = None
        raw_player_data["transform_end_time"] = 0
        deactivated_any = True
        messages.append(
            f"Você retornou à sua forma normal ({raw_player_data['class']}) de **{forma.value}**."
        )
    # Check for Aura blessing
    elif forma.value == "bencao_rei_henrique":
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
    # Check for Dracula blessing
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
    else:
        await i.response.send_message(
            "A transformação solicitada não está ativa ou não é sua.", ephemeral=True
        )
        return

    if deactivated_any:
        raw_player_data["energy"] = min(
            MAX_ENERGY, raw_player_data["energy"] + 1
        )  # Regain energy
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
    if not blessing_info:
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
    now = datetime.now().timestamp()
    afk_cooldown_duration = 10800  # 3 hours

    last_return_from_afk = player_data["cooldowns"].get("afk_cooldown", 0)
    if now - last_return_from_afk < afk_cooldown_duration:
        remaining_time_seconds = afk_cooldown_duration - (now - last_return_from_afk)
        remaining_time = str(timedelta(seconds=int(remaining_time_seconds)))
        await i.response.send_message(
            f"Você só pode entrar em modo AFK a cada {afk_cooldown_duration // 3600} horas. Tente novamente em **{remaining_time}**.",
            ephemeral=True,
        )
        return

    if player_data["status"] == "afk":
        await i.response.send_message("Você já está em modo AFK.", ephemeral=True)
        return

    player_data["status"] = "afk"
    save_data()
    await i.response.send_message(
        "🌙 Você entrou em modo AFK. Use `/voltar` para ficar online."
    )


@bot.tree.command(name="voltar", description="Sai do modo AFK e volta a ficar online.")
async def voltar(i: Interaction):
    player_data = get_player_data(i.user.id)

    if not player_data:
        await i.response.send_message(
            "Você não tem uma ficha! Use `/criar_ficha`.", ephemeral=True
        )
        return

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
    embed.set_thumbnail(url="https://i.imgur.com/Sce6RIJ.png")
    await i.response.send_message(embed=embed)


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
