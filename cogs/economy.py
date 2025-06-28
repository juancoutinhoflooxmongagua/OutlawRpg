# cogs/economy.py
import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import (
    get_player_data,
    check_cooldown,
    set_cooldown,
    get_boss_data,
    save_boss_data,
)
from config import *


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="daily", description="Colete sua recompensa diária de XP e dinheiro."
    )
    async def daily(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        cooldown = check_cooldown(player_data, "daily")
        if cooldown > 0:
            hours, rem = divmod(cooldown, 3600)
            minutes, _ = divmod(rem, 60)
            return await interaction.response.send_message(
                f"⏳ Você já coletou seu daily. Volte em `{int(hours)}h {int(minutes)}m`.",
                ephemeral=True,
            )

        player_data["dinheiro"] += RECOMPENSA_DAILY_DINHEIRO
        player_data["xp"] += RECOMPENSA_DAILY_XP
        set_cooldown(player_data, "daily", COOLDOWN_DAILY)
        self.bot.save_fichas()

        embed = discord.Embed(
            title="🎁 Recompensa Diária Coletada!", color=COR_EMBED_SUCESSO
        )
        embed.add_field(
            name="Dinheiro",
            value=f"+ {MOEDA_EMOJI} {RECOMPENSA_DAILY_DINHEIRO}",
            inline=True,
        )
        embed.add_field(
            name="Experiência", value=f"+ ✨ {RECOMPENSA_DAILY_XP} XP", inline=True
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="usar", description="Usa um item do seu inventário.")
    @app_commands.autocomplete(item_id=...)  # Implementar autocomplete
    async def usar(self, interaction: discord.Interaction, item_id: str):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        if (
            item_id not in player_data.get("inventario", {})
            or player_data["inventario"][item_id] < 1
        ):
            return await interaction.response.send_message(
                "❌ Você não possui este item.", ephemeral=True
            )

        item_info = next(
            (
                item
                for cat in LOJA_ITENS.values()
                for id, item in cat.items()
                if id == item_id
            ),
            None,
        )
        if not item_info:
            return await interaction.response.send_message(
                "❌ Item inválido.", ephemeral=True
            )

        # Lógica para o Invocador do Colosso
        if item_id == "invocador_colosso":
            boss_data = get_boss_data()
            if boss_data.get("ativo", False):
                return await interaction.response.send_message(
                    f"❌ O **{BOSS_INFO['nome']}** já está ativo no mundo!",
                    ephemeral=True,
                )

            boss_data["ativo"] = True
            boss_data["hp_atual"] = BOSS_INFO["hp_total"]
            boss_data["quem_invocou"] = interaction.user.id
            boss_data["atacantes"] = {}
            save_boss_data(boss_data)

            player_data["inventario"][item_id] -= 1
            if player_data["inventario"][item_id] == 0:
                del player_data["inventario"][item_id]
            self.bot.save_fichas()

            embed = discord.Embed(
                title=f"👹 CHEFE MUNDIAL INVOCADO 👹",
                description=f"{interaction.user.mention} usou o **{item_info['nome']}**!\n\nO temível **{BOSS_INFO['nome']}** surgiu! Todos os jogadores podem agora usar `/atacar_boss` para lutar contra ele!",
                color=COR_EMBED_CHEFE,
            )
            embed.set_image(
                url="https://i.imgur.com/lAb983f.gif"
            )  # Exemplo de GIF de boss
            return await interaction.response.send_message(
                content="@everyone", embed=embed
            )

        # Adicionar lógica para outros itens consumíveis aqui
        await interaction.response.send_message(
            f"✅ Você usou **{item_info['nome']}**.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Economy(bot))
