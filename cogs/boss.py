import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import get_player_data, save_boss_data, get_boss_data
from config import (
    LOJA_ITENS,
    COR_EMBED_SUCESSO,
    COR_EMBED_ERRO,
    COR_EMBED_CHEFE,
    BOSS_INFO,
)


class Boss(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="invocar-boss",
        description="Usa um item para invocar um chefe mundial.",
    )
    async def invocar_boss(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        item_id_invocacao = "invocador_colosso"  # ID do item de invocação

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        inventario = player_data.get("inventario", {})
        if item_id_invocacao not in inventario or inventario[item_id_invocacao] <= 0:
            return await interaction.response.send_message(
                "❌ Você não possui o item para invocar o chefe.", ephemeral=True
            )

        boss_data = get_boss_data()
        if boss_data.get("ativo", False):
            return await interaction.response.send_message(
                "👹 Um chefe mundial já está ativo!", ephemeral=True
            )

        # Consome o item
        inventario[item_id_invocacao] -= 1
        if inventario[item_id_invocacao] <= 0:
            del inventario[item_id_invocacao]
        self.bot.save_fichas()

        # Ativa o boss
        novo_boss_data = {
            "ativo": True,
            "id": BOSS_INFO["id"],
            "hp_atual": BOSS_INFO["hp_total"],
            "atacantes": {},
            "channel_id": interaction.channel.id,
            "guild_id": interaction.guild.id,
        }
        save_boss_data(novo_boss_data)

        embed = discord.Embed(
            title=f"👹 {BOSS_INFO['nome']} APARECEU! 👹",
            description=f"{interaction.user.mention} usou um item de invocação e despertou a fúria do Colosso!\n\nUse `/atacar-boss` para lutar!",
            color=COR_EMBED_CHEFE,
        )
        embed.set_thumbnail(
            url="https://i.imgur.com/your_boss_image.gif"
        )  # Coloque uma imagem para seu boss
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="atacar-boss", description="Ataca o chefe mundial ativo."
    )
    async def atacar_boss(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        boss_data = get_boss_data()

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        if not boss_data.get("ativo"):
            return await interaction.response.send_message(
                "❌ Nenhum chefe mundial está ativo.", ephemeral=True
            )

        if player_data["hp"] <= 0:
            return await interaction.response.send_message(
                "💀 Você está derrotado e não pode atacar.", ephemeral=True
            )

        # Lógica de dano
        dano_causado = max(1, player_data["atk"] - BOSS_INFO["defesa"])
        boss_data["hp_atual"] -= dano_causado

        # Registra o dano do atacante
        atacantes = boss_data.setdefault("atacantes", {})
        atacantes[user_id] = atacantes.get(user_id, 0) + dano_causado

        save_boss_data(boss_data)

        embed = discord.Embed(
            title=f"⚔️ Ataque ao {BOSS_INFO['nome']}!",
            description=f"{interaction.user.mention} causou **{dano_causado}** de dano!",
            color=COR_EMBED_PADRAO,
        )
        await interaction.response.send_message(embed=embed)

        # Verifica se o boss foi derrotado
        if boss_data["hp_atual"] <= 0:
            await self.finalizar_boss(interaction.channel)

    async def finalizar_boss(self, channel):
        boss_data = get_boss_data()

        embed = discord.Embed(
            title=f"🏆 {BOSS_INFO['nome']} FOI DERROTADO! 🏆",
            description="O grande chefe caiu! Calculando as recompensas...",
            color=COR_EMBED_SUCESSO,
        )
        await channel.send(embed=embed)

        save_boss_data({"ativo": False})


async def setup(bot):
    await bot.add_cog(Boss(bot))
