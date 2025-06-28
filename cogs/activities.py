# cogs/actions.py
import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import get_player_data, check_cooldown, set_cooldown
from config import COOLDOWN_AFK, COR_EMBED_PADRAO, COR_EMBED_ERRO


class Actions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="afk",
        description="Define seu status como ausente por 3 horas, protegendo você de ataques.",
    )
    async def afk(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        if not player_data:
            return await interaction.response.send_message(
                "❌ Você precisa ter uma ficha para usar este comando.", ephemeral=True
            )

        cooldown = check_cooldown(player_data, "afk")
        if cooldown > 0:
            return await interaction.response.send_message(
                f"⏳ Você já está em cooldown de AFK. Tente novamente em `{int(cooldown/60)}` minutos.",
                ephemeral=True,
            )

        afk_end_time = int(time.time()) + COOLDOWN_AFK
        player_data["afk_until"] = afk_end_time
        set_cooldown(player_data, "afk", COOLDOWN_AFK)
        self.bot.save_fichas()

        embed = discord.Embed(
            title="🌙 Modo AFK Ativado",
            description=f"{interaction.user.mention} agora está ausente e protegido de ataques PvP.\nSeu status voltará ao normal em **3 horas**.",
            color=COR_EMBED_PADRAO,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Actions(bot))
