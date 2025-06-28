import discord
from discord import app_commands
from discord.ext import commands
import time

# Funções e constantes importadas (assumindo que existam nos seus outros arquivos)
from utils.game_logic import (
    get_player_data,
    get_hp_max,
    get_stat,  # Função chave para calcular o total
    criar_barra,
    xp_para_level_up,
)
from config import (
    COR_EMBED_SUCESSO,
    COR_EMBED_PADRAO,
    COR_EMBED_ERRO,
    CUSTO_REVIVER,
    HABILIDADES,
    APRIMORAMENTO_CUSTO_BASE_ATK,
    APRIMORAMENTO_CUSTO_MULTIPLICADOR_ATK,
    APRIMORAMENTO_CUSTO_BASE_DEF,
    APRIMORAMENTO_CUSTO_MULTIPLICADOR_DEF,
    APRIMORAMENTO_MAX_LEVEL,
    MOEDA_EMOJI,
)


class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="criar_ficha", description="Cria sua ficha de personagem no RPG."
    )
    @app_commands.describe(
        nome="O nome do seu personagem.",
        estilo_luta="Escolha seu estilo de combate inicial.",
    )
    @app_commands.choices(
        estilo_luta=[
            app_commands.Choice(name=estilo, value=estilo)
            for estilo in HABILIDADES.keys()
        ]
    )
    async def criar_ficha(
        self,
        interaction: discord.Interaction,
        nome: str,
        estilo_luta: app_commands.Choice[str],
    ):
        user_id = str(interaction.user.id)
        if get_player_data(self.bot, user_id):
            return await interaction.response.send_message(
                "❌ Você já possui uma ficha!", ephemeral=True
            )

        base_stats = HABILIDADES[estilo_luta.value]["stats_base"]

        nova_ficha = {
            "nome": nome,
            "level": 1,
            "xp": 0,
            "hp": base_stats["hp"],
            "atk": base_stats["atk"],
            "defesa": base_stats["defesa"],
            "dinheiro": 100,
            "estilo_luta": estilo_luta.value,
            "inventario": {},
            "cooldowns": {},
            "bounty": 0,
            "afk_until": 0,
            "created_at": time.time(),
            "aprimoramentos": {"atk": 0, "defesa": 0},
        }

        self.bot.fichas_db[user_id] = nova_ficha
        self.bot.save_fichas()

        embed = discord.Embed(
            title=f"✅ Ficha de {nome} Criada!",
            description=f"Bem-vindo ao mundo de Outlaw, {interaction.user.mention}!\nSeu caminho como **{estilo_luta.value}** começa agora.",
            color=COR_EMBED_SUCESSO,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="ficha", description="Mostra sua ficha ou a de outro jogador."
    )
    async def ficha(
        self, interaction: discord.Interaction, jogador: discord.Member = None
    ):
        target_user = jogador or interaction.user
        player_data = get_player_data(self.bot, str(target_user.id))

        if not player_data:
            msg = (
                "❌ Você não tem uma ficha. Use `/criar_ficha`."
                if not jogador
                else f"❌ {target_user.display_name} não possui uma ficha."
            )
            return await interaction.response.send_message(msg, ephemeral=True)

        # --- LÓGICA DE EXIBIÇÃO DA FICHA CORRIGIDA ---
        hp_max = get_hp_max(player_data)
        xp_necessario = xp_para_level_up(player_data["level"])

        # Usa get_stat para calcular os valores totais
        ataque_total = get_stat(player_data, "atk")
        defesa_total = get_stat(player_data, "defesa")

        # Detalhes para o breakdown dos stats
        base_atk = (
            HABILIDADES.get(player_data["estilo_luta"], {})
            .get("stats_base", {})
            .get("atk", 0)
        )
        base_def = (
            HABILIDADES.get(player_data["estilo_luta"], {})
            .get("stats_base", {})
            .get("defesa", 0)
        )
        level_bonus = (player_data.get("level", 1) - 1) // 2
        aprimoramento_atk = player_data.get("aprimoramentos", {}).get("atk", 0)
        aprimoramento_def = player_data.get("aprimoramentos", {}).get("defesa", 0)

        barra_hp = criar_barra(player_data["hp"], hp_max)
        barra_xp = criar_barra(
            player_data["xp"], xp_necessario, cor_cheia="🟦", cor_vazia="⬜"
        )

        embed = discord.Embed(
            title=f"Ficha de {player_data['nome']}", color=COR_EMBED_PADRAO
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.add_field(name="📜 Nível", value=f"`{player_data['level']}`", inline=True)
        embed.add_field(
            name=f"{MOEDA_EMOJI} Dinheiro",
            value=f"`{player_data['dinheiro']}`",
            inline=True,
        )
        embed.add_field(
            name="👑 Estilo", value=f"`{player_data['estilo_luta']}`", inline=True
        )

        embed.add_field(
            name="❤️ HP",
            value=f"{barra_hp} `{player_data['hp']}/{hp_max}`",
            inline=False,
        )
        embed.add_field(
            name="📈 XP",
            value=f"{barra_xp} `{player_data['xp']}/{xp_necessario}`",
            inline=False,
        )

        embed.add_field(name="⚔️ Ataque Total", value=f"`{ataque_total}`", inline=True)
        embed.add_field(name="🛡️ Defesa Total", value=f"`{defesa_total}`", inline=True)

        stats_breakdown = (
            f"**ATK:** `{base_atk}` (Base) + `{level_bonus}` (Nível) + `{aprimoramento_atk}` (Aprim.)\n"
            f"**DEF:** `{base_def}` (Base) + `{level_bonus}` (Nível) + `{aprimoramento_def}` (Aprim.)"
        )
        embed.add_field(
            name="📊 Detalhes dos Atributos", value=stats_breakdown, inline=False
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="reviver", description="Reviva seu personagem pagando uma taxa."
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
                "❌ Você não está derrotado.", ephemeral=True
            )
        if player_data["dinheiro"] < CUSTO_REVIVER:
            return await interaction.response.send_message(
                f"❌ Você não tem dinheiro suficiente. Custo: {MOEDA_EMOJI} {CUSTO_REVIVER}",
                ephemeral=True,
            )

        player_data["dinheiro"] -= CUSTO_REVIVER
        player_data["hp"] = get_hp_max(player_data)
        self.bot.save_fichas()

        embed = discord.Embed(
            title="❤️ Personagem Revivido!",
            description=f"Você pagou {MOEDA_EMOJI} {CUSTO_REVIVER} e voltou à ação com a vida cheia!",
            color=COR_EMBED_SUCESSO,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="aprimorar", description="Aprimora seus atributos gastando dinheiro."
    )
    @app_commands.describe(atributo="O atributo que você deseja aprimorar.")
    @app_commands.choices(
        atributo=[
            app_commands.Choice(name="Ataque", value="atk"),
            app_commands.Choice(name="Defesa", value="defesa"),
        ]
    )
    async def aprimorar(
        self, interaction: discord.Interaction, atributo: app_commands.Choice[str]
    ):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        stat_key = atributo.value

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você precisa ter uma ficha para aprimorar.", ephemeral=True
            )

        aprimoramentos = player_data.setdefault(
            "aprimoramentos", {"atk": 0, "defesa": 0}
        )
        nivel_atual = aprimoramentos.get(stat_key, 0)

        if nivel_atual >= APRIMORAMENTO_MAX_LEVEL:
            return await interaction.response.send_message(
                f"❌ Você já atingiu o nível máximo de aprimoramento para {atributo.name}.",
                ephemeral=True,
            )

        if stat_key == "atk":
            custo = int(
                APRIMORAMENTO_CUSTO_BASE_ATK
                * (APRIMORAMENTO_CUSTO_MULTIPLICADOR_ATK**nivel_atual)
            )
        else:
            custo = int(
                APRIMORAMENTO_CUSTO_BASE_DEF
                * (APRIMORAMENTO_CUSTO_MULTIPLICADOR_DEF**nivel_atual)
            )

        if player_data["dinheiro"] < custo:
            return await interaction.response.send_message(
                f"❌ Você não tem dinheiro suficiente. Custo: {MOEDA_EMOJI} {custo}",
                ephemeral=True,
            )

        # --- LÓGICA DE APRIMORAMENTO CORRIGIDA ---
        player_data["dinheiro"] -= custo
        aprimoramentos[stat_key] += 1  # Registra o nível do aprimoramento
        player_data[stat_key] += 1  # Adiciona +1 diretamente ao atributo base

        self.bot.save_fichas()

        # Pega o valor total atualizado para mostrar na mensagem
        stat_total_atualizado = get_stat(player_data, stat_key)

        embed = discord.Embed(
            title="✨ Atributo Aprimorado!",
            description=f"Você aprimorou **{atributo.name}**! Seu valor total agora é **{stat_total_atualizado}**.\n(Nível de Aprimoramento: {nivel_atual + 1})\nCusto: {MOEDA_EMOJI} {custo}",
            color=COR_EMBED_SUCESSO,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Player(bot))
