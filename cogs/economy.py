# cogs/economy.py

import discord
from discord import app_commands
from discord.ext import commands
import math  # Importado para cálculos matemáticos no custo

# Importando funções que buscam dados dos jogadores.
# (Estou assumindo que elas existem no seu projeto, conforme o código original)
from utils.game_logic import get_player_data, get_stat

# --- IMPORTAÇÕES CORRIGIDAS ---
# Agora importamos as variáveis corretas do config.py.
# A variável 'PRECO_APRIMORAMENTO' foi removida pois não existe e não é necessária.
from config import (
    COR_EMBED_PADRAO,
    COR_EMBED_ERRO,
    MOEDA_EMOJI,
    ITENS_LOJA,  # Importando a variável correta da loja
    APRIMORAMENTO_CUSTO_BASE_ATK,
    APRIMORAMENTO_CUSTO_MULTIPLICADOR_ATK,
    APRIMORAMENTO_CUSTO_BASE_DEF,
    APRIMORAMENTO_CUSTO_MULTIPLICADOR_DEF,
    APRIMORAMENTO_MAX_LEVEL,
)


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="loja", description="Mostra os itens disponíveis para compra."
    )
    async def loja(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 Loja do Outlaw",
            description=f"Use `/comprar [ID do item] [quantidade]` para adquirir um item.",
            color=COR_EMBED_PADRAO,
        )

        # Itera sobre as categorias e itens para montar a embed da loja
        for categoria, itens_na_categoria in ITENS_LOJA.items():
            for item_id, item_info in itens_na_categoria.items():
                embed.add_field(
                    name=f"{item_info['emoji']} {item_info['nome']} - {MOEDA_EMOJI} {item_info['preco']}",
                    value=f"ID: `{item_id}` | {item_info['descricao']}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="comprar", description="Compra um item da loja.")
    @app_commands.describe(
        item_id="O ID do item (ex: 'pocao_vida').",
        quantidade="A quantidade a comprar.",
    )
    async def comprar(
        self, interaction: discord.Interaction, item_id: str, quantidade: int = 1
    ):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )
        if quantidade <= 0:
            return await interaction.response.send_message(
                "❌ A quantidade deve ser positiva.", ephemeral=True
            )

        # Lógica para encontrar o item em qualquer categoria
        item_info = None
        for categoria in ITENS_LOJA.values():
            if item_id in categoria:
                item_info = categoria[item_id]
                break

        if not item_info:
            return await interaction.response.send_message(
                "❌ Item não encontrado na loja.", ephemeral=True
            )

        custo_total = item_info["preco"] * quantidade

        if player_data["dinheiro"] < custo_total:
            return await interaction.response.send_message(
                f"❌ Você não tem {MOEDA_EMOJI} {custo_total} para comprar {quantidade}x {item_info['nome']}.",
                ephemeral=True,
            )

        player_data["dinheiro"] -= custo_total
        inventario = player_data.setdefault("inventario", {})
        inventario[item_id] = inventario.get(item_id, 0) + quantidade
        self.bot.save_fichas()  # (Assumindo que o bot tem este método para salvar)

        await interaction.response.send_message(
            f"✅ Você comprou **{quantidade}x {item_info['nome']}** por {MOEDA_EMOJI} {custo_total}!"
        )

    @app_commands.command(
        name="aprimorar", description="Melhora seus atributos (ATK ou DEF)."
    )
    @app_commands.choices(
        stat=[
            app_commands.Choice(name="Ataque (ATK)", value="atk"),
            app_commands.Choice(name="Defesa (DEF)", value="defesa"),
        ]
    )
    async def aprimorar(
        self, interaction: discord.Interaction, stat: app_commands.Choice[str]
    ):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        stat_key = stat.value  # 'atk' ou 'defesa'

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        # Garante que a estrutura de aprimoramentos exista na ficha do jogador
        aprimoramentos = player_data.setdefault(
            "aprimoramentos", {"atk": 0, "defesa": 0}
        )
        nivel_atual = aprimoramentos.get(stat_key, 0)

        if nivel_atual >= APRIMORAMENTO_MAX_LEVEL:
            return await interaction.response.send_message(
                f"✨ Você já atingiu o nível máximo de aprimoramento para {stat.name}!",
                ephemeral=True,
            )

        # --- LÓGICA DE CUSTO DINÂMICO ---
        # Calcula o custo com base no atributo escolhido (ATK ou DEF)
        if stat_key == "atk":
            custo_base = APRIMORAMENTO_CUSTO_BASE_ATK
            multiplicador = APRIMORAMENTO_CUSTO_MULTIPLICADOR_ATK
        else:  # defesa
            custo_base = APRIMORAMENTO_CUSTO_BASE_DEF
            multiplicador = APRIMORAMENTO_CUSTO_MULTIPLICADOR_DEF

        # Fórmula de custo: base * (multiplicador ^ nivel_atual)
        # Usamos math.floor para arredondar para baixo e ter um número inteiro
        custo = math.floor(custo_base * (multiplicador**nivel_atual))

        if player_data["dinheiro"] < custo:
            return await interaction.response.send_message(
                f"❌ Você precisa de {MOEDA_EMOJI} {custo} para o próximo aprimoramento de {stat.name}.",
                ephemeral=True,
            )

        # --- LÓGICA DE APRIMORAMENTO CORRIGIDA ---
        player_data["dinheiro"] -= custo
        aprimoramentos[stat_key] += 1  # Aumenta apenas o NÍVEL do aprimoramento
        self.bot.save_fichas()

        # Pega o valor total do atributo (base + bônus) para exibir na mensagem
        # A função get_stat deve ser responsável por somar o stat base com os bônus
        stat_total_atualizado = get_stat(player_data, stat_key)

        await interaction.response.send_message(
            f"💪 Seu **{stat.name}** foi aprimorado para o nível **{aprimoramentos[stat_key]}**! "
            f"Valor total agora: **{stat_total_atualizado}**. Você gastou {MOEDA_EMOJI} {custo}."
        )


async def setup(bot):
    await bot.add_cog(Economy(bot))
