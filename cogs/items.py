# cogs/items.py

import discord
from discord import app_commands
from discord.ext import commands

# Supondo que a função get_player_data exista em utils/game_logic.py
from utils.game_logic import get_player_data

# --- IMPORTAÇÃO CORRIGIDA ---
# O nome da variável foi corrigido de 'LOJA_ITENS' para 'ITENS_LOJA',
# que é o nome correto definido no arquivo config.py.
from config import (
    COR_EMBED_PADRAO,
    COR_EMBED_ERRO,
    ITENS_LOJA,  # <- AQUI ESTÁ A CORREÇÃO!
)


# Classe do Cog de Itens
class Items(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="inventario", description="Mostra os itens que você possui."
    )
    async def inventario(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        inventario_usuario = player_data.get("inventario", {})
        if not inventario_usuario:
            return await interaction.response.send_message(
                "🎒 Seu inventário está vazio.", ephemeral=True
            )

        embed = discord.Embed(
            title=f"🎒 Inventário de {interaction.user.display_name}",
            color=COR_EMBED_PADRAO,
        )

        descricao = []
        for item_id, quantidade in inventario_usuario.items():
            item_info = None
            for categoria in ITENS_LOJA.values():
                if item_id in categoria:
                    item_info = categoria[item_id]
                    break

            if item_info:
                descricao.append(
                    f"{item_info['emoji']} **{item_info['nome']}** - Quantidade: `{quantidade}`"
                )
            else:
                descricao.append(
                    f"❓ **Item Desconhecido ({item_id})** - Quantidade: `{quantidade}`"
                )

        embed.description = "\n".join(descricao)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Items(bot))
