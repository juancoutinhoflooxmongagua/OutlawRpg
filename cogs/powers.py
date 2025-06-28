# /cogs/powers.py

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta

from utils.game_logic import fichas_db, salvar_fichas
from config import COR_EMBED, MSG_SEM_FICHA

# Poderes podem ser definidos aqui ou no config.py para maior organização
PODERES = {
    "furia": {
        "nome": "Fúria Berserker",
        "descricao": "Aumenta seu ATK em 50%, mas reduz sua DEF em 30% por 1 minuto.",
        "duracao": 60,  # segundos
        "cooldown": 300,  # 5 minutos
        "efeitos": {"atk_mult": 1.5, "def_mult": 0.7},
    }
}


class Powers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poder", description="Ativa um poder especial.")
    @app_commands.choices(
        nome_poder=[
            app_commands.Choice(name=info["nome"], value=poder_id)
            for poder_id, info in PODERES.items()
        ]
    )
    async def poder(
        self, interaction: discord.Interaction, nome_poder: app_commands.Choice[str]
    ):
        user_id = str(interaction.user.id)
        if user_id not in fichas_db:
            return await interaction.response.send_message(
                MSG_SEM_FICHA, ephemeral=True
            )

        jogador = fichas_db[user_id]
        poder_id = nome_poder.value
        poder_info = PODERES[poder_id]
        agora = datetime.now()

        # Verifica se já existe um poder ativo
        if (
            "poder_ativo" in jogador
            and datetime.fromisoformat(jogador["poder_ativo"]["fim"]) > agora
        ):
            poder_ativo_nome = PODERES[jogador["poder_ativo"]["id"]]["nome"]
            return await interaction.response.send_message(
                f"❌ Você já está sob o efeito de **{poder_ativo_nome}**!",
                ephemeral=True,
            )

        # Verifica cooldown do poder
        cooldowns = jogador.setdefault("cooldowns", {})
        cooldown_key = f"poder_{poder_id}"
        if cooldown_key in cooldowns:
            tempo_limite = datetime.fromisoformat(cooldowns[cooldown_key])
            if agora < tempo_limite:
                tempo_restante = tempo_limite - agora
                minutos, segundos = divmod(tempo_restante.seconds, 60)
                return await interaction.response.send_message(
                    f"⏳ O poder **{poder_info['nome']}** está em cooldown por mais **{minutos}m {segundos}s**.",
                    ephemeral=True,
                )

        # Ativa o poder
        tempo_fim = agora + timedelta(seconds=poder_info["duracao"])
        jogador["poder_ativo"] = {"id": poder_id, "fim": tempo_fim.isoformat()}

        # Define o cooldown
        cooldown_fim = agora + timedelta(seconds=poder_info["cooldown"])
        cooldowns[cooldown_key] = cooldown_fim.isoformat()

        salvar_fichas()

        embed = discord.Embed(
            title=f"🔥 Poder Ativado: {poder_info['nome']}!",
            description=poder_info["descricao"],
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed)

        # ATENÇÃO: Para que os efeitos funcionem, a função get_dynamic_stat em utils/game_logic.py
        # precisaria ser atualizada para reconhecer os multiplicadores de "poder_ativo".
        # Esta é uma implementação básica da ativação e cooldown.


async def setup(bot):
    await bot.add_cog(Powers(bot))
