import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import get_player_data, get_hp_max
from config import LOJA_ITENS, COR_EMBED_SUCESSO, COR_EMBED_ERRO, BOSS_INFO


class Items(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="usar", description="Usa um item do seu inventário.")
    @app_commands.describe(item="O item que você deseja usar.")
    async def usar(self, interaction: discord.Interaction, item: str):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        inventario = player_data.get("inventario", {})
        if not inventario or item not in inventario or inventario[item] <= 0:
            return await interaction.response.send_message(
                "❌ Você não possui este item.", ephemeral=True
            )

        item_info = None
        for categoria in LOJA_ITENS.values():
            if item in categoria:
                item_info = categoria[item]
                break

        if not item_info:
            return await interaction.response.send_message(
                "❌ Item desconhecido.", ephemeral=True
            )

        # Lógica para usar o item
        efeito = item_info.get("efeito")
        if efeito:
            if efeito["tipo"] == "cura":
                hp_max = get_hp_max(player_data)
                vida_curada = min(efeito["valor"], hp_max - player_data["hp"])
                if vida_curada <= 0:
                    return await interaction.response.send_message(
                        "❤️ Sua vida já está cheia!", ephemeral=True
                    )

                player_data["hp"] += vida_curada

                embed = discord.Embed(
                    title=f"🧪 Item Usado: {item_info['nome']}",
                    description=f"Você restaurou **{vida_curada}** pontos de vida.",
                    color=COR_EMBED_SUCESSO,
                )
                await interaction.response.send_message(embed=embed)

            # Adicione outras lógicas de efeito aqui (ex: buffs)
            else:
                await interaction.response.send_message(
                    f"🤷 O item **{item_info['nome']}** ainda não tem um efeito implementado.",
                    ephemeral=True,
                )

        inventario[item] -= 1
        if inventario[item] <= 0:
            del inventario[item]

        self.bot.save_fichas()

    @usar.autocomplete("item")
    async def usar_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        choices = []
        if player_data and player_data.get("inventario"):
            for item_id, quantidade in player_data["inventario"].items():
                if quantidade > 0:
                    # Encontrar o nome do item
                    item_info = None
                    for categoria in LOJA_ITENS.values():
                        if item_id in categoria:
                            item_info = categoria[item_id]
                            break
                    if item_info and current.lower() in item_info["nome"].lower():
                        choices.append(
                            app_commands.Choice(
                                name=f"{item_info['nome']} (x{quantidade})",
                                value=item_id,
                            )
                        )
        return choices[:25]


async def setup(bot):
    await bot.add_cog(Items(bot))
