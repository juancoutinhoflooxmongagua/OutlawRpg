# /cogs/combat.py
import discord
import random
import asyncio
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta

from utils.game_logic import (
    fichas_db,
    salvar_fichas,
    get_dynamic_stat,
    get_hp_max,
    gifs_db,
    verificar_level_up,
)
from config import (
    COR_EMBED,
    MSG_SEM_FICHA,
    ATAQUES_ESPECIAIS,
    ANIMAIS,
    CAVALEIROS,
    COOLDOWN_CACAR,
    COOLDOWN_BATALHAR,
)


class Combat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _checar_cooldown(self, jogador, comando, segundos):
        cooldowns = jogador.setdefault("cooldowns", {})
        if comando in cooldowns:
            tempo_limite = datetime.fromisoformat(cooldowns[comando]) + timedelta(
                seconds=segundos
            )
            if datetime.now() < tempo_limite:
                tempo_restante = tempo_limite - datetime.now()
                return f"⏳ Você precisa esperar mais **{int(tempo_restante.total_seconds())}s**."
        return None

    async def _run_pve_battle(self, interaction: discord.Interaction, jogador, inimigo):
        hp_max_jogador = get_hp_max(str(interaction.user.id))
        log_batalha = [
            f"⚔️ {interaction.user.mention} encontrou um(a) **{inimigo['nome']}**!"
        ]

        embed = discord.Embed(
            title="⚔️ Batalha Iniciada!",
            description="\n".join(log_batalha),
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Seu HP", value=f"{jogador['hp']}/{hp_max_jogador}", inline=True
        )
        embed.add_field(
            name=f"HP do {inimigo['nome']}",
            value=f"{inimigo['hp']}/{inimigo['hp']}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)

        while jogador["hp"] > 0 and inimigo["hp"] > 0:
            await asyncio.sleep(2)

            # Turno do jogador
            dano_causado = max(
                1, get_dynamic_stat(str(interaction.user.id), "atk") - inimigo["defesa"]
            )
            inimigo["hp"] -= dano_causado
            log_batalha.append(f"➡️ Você atacou e causou **{dano_causado}** de dano!")

            if inimigo["hp"] <= 0:
                break

            # Turno do inimigo
            dano_sofrido = max(
                1, inimigo["atk"] - get_dynamic_stat(str(interaction.user.id), "defesa")
            )
            jogador["hp"] -= dano_sofrido
            log_batalha.append(
                f"⬅️ O **{inimigo['nome']}** atacou e causou **{dano_sofrido}** de dano!"
            )

            embed.description = "\n".join(log_batalha[-4:])
            embed.set_field_at(
                0,
                name="Seu HP",
                value=f"{max(0, jogador['hp'])}/{hp_max_jogador}",
                inline=True,
            )
            embed.set_field_at(
                1,
                name=f"HP do {inimigo['nome']}",
                value=f"{max(0, inimigo['hp'])}/{inimigo['hp']}",
                inline=True,
            )
            await interaction.edit_original_response(embed=embed)

        await asyncio.sleep(2)

        if jogador["hp"] <= 0:
            jogador["hp"] = 0
            embed.color = discord.Color.dark_red()
            embed.title = "💀 VOCÊ FOI DERROTADO 💀"
            log_batalha.append("\nUse `/reviver` para voltar.")
        else:
            recompensa_xp = inimigo["xp_recompensa"]
            recompensa_dinheiro = inimigo["dinheiro_recompensa"]
            jogador["xp"] += recompensa_xp
            jogador["dinheiro"] += recompensa_dinheiro
            embed.color = discord.Color.gold()
            embed.title = "🏆 VITÓRIA! 🏆"
            log_batalha.append(
                f"\nVocê ganhou **{recompensa_xp} XP** e **${recompensa_dinheiro}**!"
            )

        embed.description = "\n".join(log_batalha[-5:])
        await interaction.edit_original_response(embed=embed)

        novo_level = verificar_level_up(str(interaction.user.id))
        if novo_level:
            await interaction.followup.send(
                f"🎉 Parabéns {interaction.user.mention}, você subiu para o **nível {novo_level}**!"
            )

        salvar_fichas()

    @app_commands.command(
        name="cacar",
        description="Enfrente animais selvagens para ganhar XP e dinheiro.",
    )
    async def cacar(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id not in fichas_db:
            return await interaction.response.send_message(
                MSG_SEM_FICHA, ephemeral=True
            )

        jogador = fichas_db[user_id]
        if jogador["hp"] <= 0:
            return await interaction.response.send_message(
                "❌ Você está derrotado!", ephemeral=True
            )

        erro_cooldown = self._checar_cooldown(jogador, "cacar", COOLDOWN_CACAR)
        if erro_cooldown:
            return await interaction.response.send_message(
                erro_cooldown, ephemeral=True
            )

        jogador["cooldowns"]["cacar"] = datetime.now().isoformat()
        inimigo = random.choice(ANIMAIS).copy()
        await self._run_pve_battle(interaction, jogador, inimigo)

    @app_commands.command(
        name="batalhar", description="Enfrente cavaleiros para ganhar XP e dinheiro."
    )
    async def batalhar(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id not in fichas_db:
            return await interaction.response.send_message(
                MSG_SEM_FICHA, ephemeral=True
            )

        jogador = fichas_db[user_id]
        if jogador["hp"] <= 0:
            return await interaction.response.send_message(
                "❌ Você está derrotado!", ephemeral=True
            )

        erro_cooldown = self._checar_cooldown(jogador, "batalhar", COOLDOWN_BATALHAR)
        if erro_cooldown:
            return await interaction.response.send_message(
                erro_cooldown, ephemeral=True
            )

        jogador["cooldowns"]["batalhar"] = datetime.now().isoformat()
        inimigo = random.choice(CAVALEIROS).copy()
        await self._run_pve_battle(interaction, jogador, inimigo)

    @app_commands.command(
        name="atacar", description="Ataca outro jogador em um combate PvP."
    )
    @app_commands.choices(
        tipo_ataque=[
            app_commands.Choice(name="Ataque Básico", value="basico"),
            app_commands.Choice(name="Ataque Especial", value="especial"),
        ]
    )
    async def atacar(
        self,
        interaction: discord.Interaction,
        alvo: discord.Member,
        tipo_ataque: app_commands.Choice[str],
    ):
        atacante_id, alvo_id = str(interaction.user.id), str(alvo.id)

        # Validações
        if atacante_id not in fichas_db:
            return await interaction.response.send_message(
                MSG_SEM_FICHA, ephemeral=True
            )
        if alvo_id not in fichas_db:
            return await interaction.response.send_message(
                f"❌ {alvo.display_name} não possui uma ficha.", ephemeral=True
            )
        if alvo.bot or alvo.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ Alvo inválido.", ephemeral=True
            )

        atacante, defensor = fichas_db[atacante_id], fichas_db[alvo_id]
        if atacante["hp"] <= 0:
            return await interaction.response.send_message(
                "❌ Você está incapacitado.", ephemeral=True
            )
        if defensor["hp"] <= 0:
            return await interaction.response.send_message(
                f"❌ {alvo.display_name} já está incapacitado.", ephemeral=True
            )

        # Lógica do Ataque
        atk_atacante = get_dynamic_stat(atacante_id, "atk")
        def_defensor = get_dynamic_stat(alvo_id, "defesa")

        if tipo_ataque.value == "basico":
            nome_ataque = "Ataque Básico"
            dano_bruto = random.randint(atk_atacante // 2, int(atk_atacante * 1.2))
            dano_final = max(1, dano_bruto - def_defensor)
        else:  # especial
            estilo = atacante.get("estilo_luta")
            especial_info = ATAQUES_ESPECIAIS.get(estilo)
            if not especial_info:
                return await interaction.response.send_message(
                    "❌ Seu estilo não tem ataque especial.", ephemeral=True
                )

            nome_ataque = especial_info["nome"]
            dano_bruto = int(atk_atacante * especial_info["multiplicador"])
            dano_final = max(
                1, dano_bruto - int(def_defensor * 0.8)
            )  # Ignora parte da defesa

        defensor["hp"] -= dano_final

        resultado = f"{interaction.user.mention} usou **{nome_ataque}** em {alvo.mention}, causando **{dano_final}** de dano!"
        if defensor["hp"] <= 0:
            defensor["hp"] = 0
            resultado += f"\n\n**{alvo.mention} foi derrotado!** 💀"

        embed = discord.Embed(
            title="⚔️ Combate PvP ⚔️", description=resultado, color=COR_EMBED
        )
        gif_url = random.choice(
            gifs_db.get(atacante["estilo_luta"], {}).get(tipo_ataque.value, [None])
        )
        if gif_url:
            embed.set_image(url=gif_url)

        await interaction.response.send_message(embed=embed)
        salvar_fichas()


async def setup(bot):
    await bot.add_cog(Combat(bot))
