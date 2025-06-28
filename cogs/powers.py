# cogs/powers.py
import discord
from discord import app_commands
from discord.ext import commands

# Corrigido: Importando as funções necessárias de 'utils.game_logic'
from utils.game_logic import get_player_data
from config import COR_EMBED_PADRAO


class Powers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # Corrigido: O bot é armazenado para acesso posterior
        self.bot = bot

    @app_commands.command(
        name="poderes", description="Mostra os poderes e habilidades do seu personagem."
    )
    async def poderes(self, interaction: discord.Interaction):
        # Corrigido: Usa a função get_player_data com self.bot para obter os dados
        player_data = get_player_data(self.bot, str(interaction.user.id))

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você precisa ter uma ficha para ver seus poderes. Use `/criar_ficha`.",
                ephemeral=True,
            )

        # A lógica para exibir os poderes continua a mesma
        estilo = player_data.get("estilo_luta", "Nenhum")
        level = player_data.get("level", 1)

        embed = discord.Embed(
            title=f"Poderes de {player_data['nome']}",
            description=f"**Estilo de Luta:** {estilo}\n**Nível:** {level}",
            color=COR_EMBED_PADRAO,
        )

        # Aqui você pode adicionar lógica para mostrar habilidades que mudam com o nível
        embed.add_field(
            name="Ataque Básico", value="Um ataque simples e direto.", inline=False
        )

        if level >= 5:
            embed.add_field(
                name="Ataque Especial (Desbloqueado)",
                value="Um ataque mais poderoso específico do seu estilo.",
                inline=False,
            )
        else:
            embed.add_field(
                name="Ataque Especial (Bloqueado)",
                value="Desbloqueia no nível 5.",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Powers(bot))
