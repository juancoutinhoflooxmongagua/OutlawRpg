import discord
import random
import asyncio
from discord import app_commands
from discord.ext import commands

from utils.game_logic import (
    get_player_data,
    check_cooldown,
    set_cooldown,
    get_hp_max,
    verificar_level_up,
)
from config import (
    COR_EMBED_PADRAO,
    COR_EMBED_ERRO,
    COR_EMBED_SUCESSO,
    INIMIGOS,
    COOLDOWN_CACAR,
    COOLDOWN_BATALHAR,
    MOEDA_EMOJI,
    BOUNTY_BASE,
    BOUNTY_PERCENTUAL_VITIMA,
)


class Combat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _run_pve_battle(
        self, interaction: discord.Interaction, player_data: dict, enemy_type: str
    ):
        user_id = str(interaction.user.id)
        inimigo = random.choice(INIMIGOS[enemy_type]).copy()

        hp_max_jogador = get_hp_max(player_data)
        hp_jogador_atual = player_data["hp"]
        hp_inimigo_atual = inimigo["hp"]
        hp_max_inimigo = inimigo["hp"]

        log_batalha = [
            f"⚔️ {interaction.user.mention} encontrou um(a) **{inimigo['nome']}**!"
        ]

        embed = discord.Embed(
            title="⚔️ Batalha em Andamento!",
            description="\n".join(log_batalha),
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Seu HP", value=f"{hp_jogador_atual}/{hp_max_jogador}", inline=True
        )
        embed.add_field(
            name=f"HP do {inimigo['nome']}",
            value=f"{hp_inimigo_atual}/{hp_max_inimigo}",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        while hp_jogador_atual > 0 and hp_inimigo_atual > 0:
            await asyncio.sleep(2)

            # Turno do jogador
            dano_causado = max(1, player_data["atk"] - inimigo["defesa"])
            hp_inimigo_atual -= dano_causado
            log_batalha.append(f"➡️ Você atacou e causou **{dano_causado}** de dano!")

            if hp_inimigo_atual <= 0:
                break

            # Turno do inimigo
            dano_sofrido = max(1, inimigo["atk"] - player_data["defesa"])
            hp_jogador_atual -= dano_sofrido
            log_batalha.append(
                f"⬅️ O **{inimigo['nome']}** atacou e causou **{dano_sofrido}** de dano!"
            )

            embed.description = "\n".join(log_batalha[-4:])
            embed.set_field_at(
                0,
                name="Seu HP",
                value=f"{max(0, hp_jogador_atual)}/{hp_max_jogador}",
                inline=True,
            )
            embed.set_field_at(
                1,
                name=f"HP do {inimigo['nome']}",
                value=f"{max(0, hp_inimigo_atual)}/{hp_max_inimigo}",
                inline=True,
            )
            await message.edit(embed=embed)

        player_data["hp"] = max(0, hp_jogador_atual)

        await asyncio.sleep(2)

        if hp_jogador_atual <= 0:
            embed.color = COR_EMBED_ERRO
            embed.title = "💀 VOCÊ FOI DERROTADO 💀"
            log_batalha.append("\nUse `/reviver` para voltar à ação.")
        else:
            recompensa_xp = inimigo["xp"]
            recompensa_dinheiro = inimigo["dinheiro"]
            player_data["xp"] += recompensa_xp
            player_data["dinheiro"] += recompensa_dinheiro

            embed.color = COR_EMBED_SUCESSO
            embed.title = "🏆 VITÓRIA! 🏆"
            log_batalha.append(
                f"\nVocê ganhou **{recompensa_xp} XP** e **{MOEDA_EMOJI} {recompensa_dinheiro}**!"
            )

        embed.description = "\n".join(log_batalha[-5:])
        await message.edit(embed=embed)

        self.bot.save_fichas()

        novo_level = verificar_level_up(self.bot, user_id)
        if novo_level:
            await interaction.followup.send(
                f"🎉 Parabéns {interaction.user.mention}, você subiu para o **nível {novo_level}**!",
                ephemeral=False,
            )

    @app_commands.command(
        name="cacar",
        description="Enfrente animais selvagens para ganhar XP e dinheiro.",
    )
    async def cacar(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        if not player_data:
            return await interaction.response.send_message(
                "❌ Você precisa ter uma ficha para usar este comando.", ephemeral=True
            )
        if player_data["hp"] <= 0:
            return await interaction.response.send_message(
                "❌ Você está derrotado e não pode caçar. Use `/reviver`.",
                ephemeral=True,
            )

        cooldown = check_cooldown(player_data, "cacar")
        if cooldown > 0:
            return await interaction.response.send_message(
                f"⏳ Você precisa esperar mais `{int(cooldown)}s` para caçar novamente.",
                ephemeral=True,
            )

        set_cooldown(player_data, "cacar", COOLDOWN_CACAR)
        self.bot.save_fichas()
        await self._run_pve_battle(interaction, player_data, "cacar")

    @app_commands.command(
        name="batalhar", description="Enfrente cavaleiros para ganhar XP e dinheiro."
    )
    async def batalhar(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        if not player_data:
            return await interaction.response.send_message(
                "❌ Você precisa ter uma ficha para usar este comando.", ephemeral=True
            )
        if player_data["hp"] <= 0:
            return await interaction.response.send_message(
                "❌ Você está derrotado e não pode batalhar. Use `/reviver`.",
                ephemeral=True,
            )

        cooldown = check_cooldown(player_data, "batalhar")
        if cooldown > 0:
            return await interaction.response.send_message(
                f"⏳ Você precisa esperar mais `{int(cooldown)}s` para batalhar novamente.",
                ephemeral=True,
            )

        set_cooldown(player_data, "batalhar", COOLDOWN_BATALHAR)
        self.bot.save_fichas()
        await self._run_pve_battle(interaction, player_data, "batalhar")

    @app_commands.command(name="atacar", description="Ataca outro jogador.")
    async def atacar(self, interaction: discord.Interaction, alvo: discord.Member):
        atacante_id = str(interaction.user.id)
        alvo_id = str(alvo.id)

        # Validações
        if atacante_id == alvo_id:
            return await interaction.response.send_message(
                "❌ Você não pode atacar a si mesmo.", ephemeral=True
            )
        if alvo.bot:
            return await interaction.response.send_message(
                "❌ Você não pode atacar bots.", ephemeral=True
            )

        atacante_data = get_player_data(self.bot, atacante_id)
        alvo_data = get_player_data(self.bot, alvo_id)

        if not atacante_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha para atacar.", ephemeral=True
            )
        if not alvo_data:
            return await interaction.response.send_message(
                f"❌ {alvo.display_name} não possui uma ficha.", ephemeral=True
            )

        if atacante_data["hp"] <= 0:
            return await interaction.response.send_message(
                "❌ Você está derrotado e não pode atacar.", ephemeral=True
            )
        if alvo_data["hp"] <= 0:
            return await interaction.response.send_message(
                f"❌ {alvo.display_name} já está derrotado.", ephemeral=True
            )

        # Cálculo do dano
        dano = max(1, atacante_data["atk"] - alvo_data["defesa"])
        alvo_data["hp"] -= dano

        resultado_str = f"{interaction.user.mention} atacou {alvo.mention} e causou **{dano}** de dano!"

        # Lógica de derrota e bounty
        if alvo_data["hp"] <= 0:
            alvo_data["hp"] = 0
            resultado_str += f"\n\n**{alvo.mention} foi derrotado!** 💀"

            bounty_alvo = alvo_data.get("bounty", 0)
            if bounty_alvo > 0:
                atacante_data["dinheiro"] += bounty_alvo
                alvo_data["bounty"] = 0
                resultado_str += f"\n{interaction.user.mention} coletou a recompensa de **{MOEDA_EMOJI} {bounty_alvo}**!"
            else:
                nova_bounty = BOUNTY_BASE + int(
                    atacante_data.get("dinheiro", 0) * BOUNTY_PERCENTUAL_VITIMA
                )
                atacante_data["bounty"] = atacante_data.get("bounty", 0) + nova_bounty
                resultado_str += f"\nCom este ato, {interaction.user.mention} agora tem uma recompensa de **{MOEDA_EMOJI} {atacante_data['bounty']}** por sua cabeça!"

        embed = discord.Embed(
            title="⚔️ Combate PvP ⚔️", description=resultado_str, color=COR_EMBED_PADRAO
        )
        gif_url = random.choice(
            self.bot.gifs_db.get(
                atacante_data.get("estilo_luta", "Lutador (Mãos)"), {}
            ).get("basico", [None])
        )
        if gif_url:
            embed.set_image(url=gif_url)

        await interaction.response.send_message(embed=embed)
        self.bot.save_fichas()


async def setup(bot):
    await bot.add_cog(Combat(bot))
