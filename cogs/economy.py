# cogs/economy.py
import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import get_player_data, set_cooldown, check_cooldown
from config import (
    LOJA_ITENS,
    MOEDA_EMOJI,
    COR_EMBED_PADRAO,
    COR_EMBED_SUCESSO,
    COR_EMBED_ERRO,
    COOLDOWN_DAILY,
    RECOMPENSA_DAILY_DINHEIRO,
    RECOMPENSA_DAILY_XP,
)


class LojaView(discord.ui.View):
    def __init__(self, bot, author):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.add_item(LojaDropdown(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Apenas quem usou o comando pode interagir com a loja.", ephemeral=True
            )
            return False
        return True


class LojaDropdown(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        for categoria, itens in LOJA_ITENS.items():
            for item_id, item_info in itens.items():
                options.append(
                    discord.SelectOption(
                        label=f"{item_info['nome']} - {MOEDA_EMOJI} {item_info['preco']}",
                        value=item_id,
                        emoji=item_info["emoji"],
                        description=item_info["descricao"][:100],
                    )
                )
        super().__init__(
            placeholder="Selecione um item para comprar...", options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        item_id = self.values[0]
        player_data = get_player_data(self.bot, user_id)

        item_info = None
        for categoria in LOJA_ITENS.values():
            if item_id in categoria:
                item_info = categoria[item_id]
                break

        if not item_info:
            return await interaction.followup.send(
                "❌ Item não encontrado!", ephemeral=True
            )

        if player_data["dinheiro"] < item_info["preco"]:
            return await interaction.followup.send(
                f"❌ Você não tem dinheiro suficiente para comprar **{item_info['nome']}**.",
                ephemeral=True,
            )

        player_data["dinheiro"] -= item_info["preco"]
        inventario = player_data.setdefault("inventario", {})
        inventario[item_id] = inventario.get(item_id, 0) + 1
        self.bot.save_fichas()

        embed = discord.Embed(
            title="✅ Compra Realizada!",
            description=f"Você comprou **1x {item_info['nome']}** por {MOEDA_EMOJI} {item_info['preco']}.",
            color=COR_EMBED_SUCESSO,
        )
        await interaction.followup.send(embed=embed)


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Receba sua recompensa diária.")
    async def daily(self, interaction: discord.Interaction):
        try:
            # Defer para evitar timeout. O ideal é ser efêmero para não poluir o chat.
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            print(
                f"Falha ao responder à interação para {interaction.user}. A interação pode ter expirado."
            )
            return

        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)

        if not player_data:
            return await interaction.followup.send(
                "❌ Você precisa ter uma ficha para usar este comando.", ephemeral=True
            )

        cooldown = check_cooldown(player_data, "daily")
        if cooldown > 0:
            horas, rem = divmod(cooldown, 3600)
            minutos, segundos = divmod(rem, 60)
            return await interaction.followup.send(
                f"⏳ Você já coletou sua recompensa. Tente novamente em `{int(horas)}h {int(minutos)}m`.",
                ephemeral=True,
            )

        player_data["dinheiro"] += RECOMPENSA_DAILY_DINHEIRO
        player_data["xp"] += RECOMPENSA_DAILY_XP
        set_cooldown(player_data, "daily", COOLDOWN_DAILY)
        self.bot.save_fichas()

        embed = discord.Embed(
            title="🎁 Recompensa Diária Coletada!",
            description=f"Você recebeu **{MOEDA_EMOJI} {RECOMPENSA_DAILY_DINHEIRO}** e **{RECOMPENSA_DAILY_XP} XP**!",
            color=COR_EMBED_SUCESSO,
        )
        # Usamos followup.send porque a resposta já foi deferida (adiada).
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="loja", description="Abre a loja de itens do servidor.")
    async def loja(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏪 Loja do Outlaw RPG",
            description="Use o menu abaixo para selecionar um item e comprá-lo.",
            color=COR_EMBED_PADRAO,
        )
        for categoria, itens in LOJA_ITENS.items():
            campo_valor = ""
            for item_id, item_info in itens.items():
                campo_valor += f"> {item_info['emoji']} **{item_info['nome']}** - {MOEDA_EMOJI} {item_info['preco']}\n"
            embed.add_field(
                name=categoria.capitalize(), value=campo_valor, inline=False
            )

        view = LojaView(self.bot, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Economy(bot))
