# /utils/ui_elements.py
import discord
import time
from .game_logic import (
    get_player_data,
    get_hp_max,
    get_stat,
    criar_barra,
    xp_para_level_up,
)
from config import (
    LOJA_ITENS,
    COR_EMBED_PADRAO,
    MOEDA_EMOJI,
    COR_EMBED_ERRO,
    COR_EMBED_SUCESSO,
)


class FichaView(discord.ui.View):
    def __init__(self, bot, author: discord.User, target_user: discord.Member):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.target_user = target_user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Apenas quem usou o comando pode interagir.", ephemeral=True
            )
            return False
        return True

    def _create_base_embed(self, title_suffix="") -> discord.Embed:
        player_data = get_player_data(self.bot, self.target_user.id)
        embed = discord.Embed(
            title=f"Ficha de {player_data['nome']}{title_suffix}",
        ).set_thumbnail(url=self.target_user.display_avatar.url)
        return embed

    def create_attributes_embed(self) -> discord.Embed:
        embed = self._create_base_embed()
        player_data = get_player_data(self.bot, str(self.target_user.id))

        hp_max = get_hp_max(player_data)
        xp_necessario = xp_para_level_up(player_data["level"])

        # Define o status e a cor do embed baseada no status
        status_str = "☀️ Ativo"
        status_color = COR_EMBED_SUCESSO
        if player_data["hp"] <= 0:
            status_str = "💀 Derrotado"
            status_color = COR_EMBED_ERRO
        elif player_data.get("afk_until", 0) > time.time():
            status_str = "🌙 AFK"
            status_color = COR_EMBED_PADRAO

        bounty_info = player_data.get("bounty", 0)
        if bounty_info > 0:
            status_str = f"**🔥 FORAGIDO** ({MOEDA_EMOJI} {bounty_info})"
            status_color = 0xFF4500  # Laranja/Vermelho para foragido

        embed.color = status_color

        embed.description = (
            f"*{player_data['estilo_luta']}* | Nível **{player_data['level']}**\n"
            f"Status: **{status_str}**"
        )
        embed.add_field(
            name="❤️ Pontos de Vida (HP)",
            value=f"{criar_barra(player_data['hp'], hp_max, cor_cheia='❤️', cor_vazia='🖤')} {player_data['hp']}/{hp_max}",
            inline=False,
        )
        embed.add_field(
            name="✨ Experiência (XP)",
            value=f"{criar_barra(player_data['xp'], xp_necessario, cor_cheia='✨', cor_vazia='➖')} {player_data['xp']}/{xp_necessario}",
            inline=False,
        )

        stats_text = (
            f"⚔️ **Ataque**: `{get_stat(player_data, 'atk')}`\n"
            f"🛡️ **Defesa**: `{get_stat(player_data, 'defesa')}`\n"
            f"{MOEDA_EMOJI} **Dinheiro**: `{player_data['dinheiro']}`"
        )
        embed.add_field(name="📊 Atributos Principais", value=stats_text, inline=True)

        # Adiciona uma imagem baseada no estilo de luta (substitua as URLs!)
        estilo_imagem = {
            "Lutador (Mãos)": "https://i.imgur.com/Kz3yL3g.gif",
            "Espadachim (Espadas)": "https://i.imgur.com/Taf2So5.gif",
            "Atirador (Armas de Fogo)": "https://i.imgur.com/AqHAi1K.gif",
        }
        imagem_url = estilo_imagem.get(player_data.get("estilo_luta"))
        if imagem_url:
            embed.set_image(url=imagem_url)

        embed.set_footer(text="Outlaw RPG | Use os botões para navegar na ficha.")
        return embed

    def create_inventory_embed(self) -> discord.Embed:
        embed = self._create_base_embed(" - Inventário")
        player_data = get_player_data(self.bot, str(self.target_user.id))
        inventario = player_data.get("inventario", {})
        if not inventario:
            embed.description = "O inventário está vazio."
        else:
            desc = []
            for item_id, quantidade in inventario.items():
                item_info = next(
                    (
                        item
                        for cat in LOJA_ITENS.values()
                        for id, item in cat.items()
                        if id == item_id
                    ),
                    None,
                )
                if item_info:
                    desc.append(
                        f"> {item_info['emoji']} **{item_info['nome']}** `x{quantidade}`"
                    )
            embed.description = "\n".join(desc)
        return embed

    @discord.ui.button(label="Atributos", style=discord.ButtonStyle.primary, emoji="📊")
    async def show_attributes(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(embed=self.create_attributes_embed())

    @discord.ui.button(
        label="Inventário", style=discord.ButtonStyle.secondary, emoji="🎒"
    )
    async def show_inventory(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(embed=self.create_inventory_embed())
