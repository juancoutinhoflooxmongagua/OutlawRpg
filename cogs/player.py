# cogs/player.py
import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import get_player_data, get_hp_max, set_cooldown, check_cooldown
from utils.ui_elements import FichaView
from config import *


class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="criar_ficha", description="Cria sua ficha de personagem no RPG."
    )
    @app_commands.choices(
        estilo_luta=[
            app_commands.Choice(name=f"{info['emoji']} {estilo}", value=estilo)
            for estilo, info in HABILIDADES.items()
        ]
    )
    async def criar_ficha(
        self, interaction: discord.Interaction, estilo_luta: app_commands.Choice[str]
    ):
        user_id = str(interaction.user.id)
        if get_player_data(self.bot, user_id):
            return await interaction.response.send_message(
                "❌ Você já possui uma ficha!", ephemeral=True
            )

        stats = HABILIDADES[estilo_luta.value]["stats_base"]
        self.bot.fichas[user_id] = {
            "nome": interaction.user.display_name,
            "level": 1,
            "xp": 0,
            "dinheiro": 100,
            "estilo_luta": estilo_luta.value,
            "hp": stats["hp"],
            "inventario": {},
            "cooldowns": {},
            "bounty": 0,
        }
        self.bot.save_fichas()

        embed = discord.Embed(
            title=f"📝 Ficha Criada!",
            description=f"Bem-vindo ao mundo de Outlaw, **{interaction.user.mention}**!\nVocê escolheu o caminho do **{estilo_luta.name}**.",
            color=COR_EMBED_SUCESSO,
        ).set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="ficha", description="Mostra sua ficha de personagem ou de outro jogador."
    )
    async def ficha(
        self, interaction: discord.Interaction, membro: discord.Member = None
    ):
        target_user = membro or interaction.user
        if not get_player_data(self.bot, target_user.id):
            msg = (
                "Você não tem uma ficha. Use `/criar_ficha`."
                if not membro
                else f"{target_user.display_name} não tem uma ficha."
            )
            return await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

        view = FichaView(self.bot, interaction.user, target_user)
        await interaction.response.send_message(
            embed=view.create_attributes_embed(), view=view
        )

    @app_commands.command(
        name="reviver", description="Pague para voltar à vida após ser derrotado."
    )
    async def reviver(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )
        if player_data["hp"] > 0:
            return await interaction.response.send_message(
                "❌ Você já está vivo!", ephemeral=True
            )

        cooldown = check_cooldown(player_data, "reviver")
        if cooldown > 0:
            return await interaction.response.send_message(
                f"⏳ Aguarde mais `{int(cooldown)}s`.", ephemeral=True
            )

        if player_data["dinheiro"] < CUSTO_REVIVER:
            return await interaction.response.send_message(
                f"❌ Você precisa de {MOEDA_EMOJI} `{CUSTO_REVIVER}` para reviver.",
                ephemeral=True,
            )

        player_data["dinheiro"] -= CUSTO_REVIVER
        player_data["hp"] = get_hp_max(player_data) // 4
        set_cooldown(player_data, "reviver", COOLDOWN_REVIVER)
        self.bot.save_fichas()

        embed = discord.Embed(
            title="✨ De Volta à Vida!",
            description=f"Você pagou {MOEDA_EMOJI} `{CUSTO_REVIVER}` e retornou ao mundo dos vivos.",
            color=COR_EMBED_SUCESSO,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Player(bot))
