import discord
from discord import app_commands
from discord.ext import commands
import time

from utils.game_logic import (
    get_player_data,
    get_hp_max,
    get_stat,
    criar_barra,
    xp_para_level_up,
)
from config import (
    COR_EMBED_SUCESSO,
    COR_EMBED_PADRAO,
    COR_EMBED_ERRO,
    CUSTO_REVIVER,
    HABILIDADES,
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

        hp_max = get_hp_max(player_data)
        xp_necessario = xp_para_level_up(player_data["level"])

        ataque_total = get_stat(player_data, "atk")
        defesa_total = get_stat(player_data, "defesa")

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


async def setup(bot):
    await bot.add_cog(Player(bot))
