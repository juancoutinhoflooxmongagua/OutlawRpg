# embed_commands.py
import discord
from discord.ext import commands
from discord import app_commands, Embed, Color, Interaction, ui, ButtonStyle
from datetime import datetime

# Importe 'get_player_data' e 'ITEMS_DATA' de onde eles estiverem (provavelmente config ou main)
# Se get_player_data estiver no main.py, você precisará importá-lo aqui.
# Por enquanto, vou assumir que você vai passar as informações necessárias
# ou que get_player_data se torne global no main antes de importar este arquivo.

# Para simplificar o exemplo, vamos assumir que player_database e ITEMS_DATA podem ser acessados
# ou passados. O ideal seria passar apenas o que é necessário.
# Exemplo de como importar do main.py (se a arquitetura permitir)
# from main import get_player_data, player_database # CUIDADO: Importação circular pode ocorrer!

# Para este exemplo, faremos um import mais seguro se get_player_data depende do player_database global.
# OU você passa o player_database para a função setup_embed_commands.

# IMPORTANTE: Você precisa garantir que `get_player_data` seja acessível.
# Uma forma comum é passá-lo como argumento para a função setup.
# Para manter a compatibilidade com seu código existente, vamos simular isso.

# --- CLASSES/MODAIS PARA CRIAÇÃO DE EMBED PERSONALIZADO ---


class AddFieldModal(ui.Modal, title="Adicionar Campo ao Embed"):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutos para preencher
        self.field_name = ui.TextInput(
            label="Nome do Campo",
            placeholder="Ex: Requisitos, Horário",
            max_length=256,
            required=True,
        )
        self.field_value = ui.TextInput(
            label="Valor do Campo",
            placeholder="Ex: Nível 10+, Sábado 19h",
            style=discord.TextStyle.paragraph,  # Permite múltiplas linhas
            required=True,
        )
        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.field_inline = ui.TextInput(
            label="Campo na mesma linha? (sim/não)",
            placeholder="Padrão é 'não'.",
            max_length=3,
            required=False,
        )
        self.add_item(self.field_inline)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.stop()  # Sinaliza que o modal foi concluído


class EmbedCreatorView(ui.View):
    def __init__(self, initial_embed: Embed, author_id: int, bot_ref: commands.Bot):
        super().__init__(timeout=600)  # 10 minutos para editar o embed
        self.embed = initial_embed
        self.author_id = author_id  # Para verificar quem pode editar
        self.fields_added = 0  # Contador para limitar campos
        self.bot_ref = (
            bot_ref  # Referência ao objeto bot principal para bot.user.display_avatar
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                content="Tempo limite para edição do embed atingido.", view=self
            )
        except:
            pass  # Mensagem já pode ter sido deletada

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Apenas o criador do embed pode interagir com este menu.",
                ephemeral=True,
            )
            return False
        return True

    @ui.button(label="Editar Título/Descrição", style=ButtonStyle.primary, emoji="✍️")
    async def edit_basic_info(self, interaction: Interaction, button: ui.Button):
        class BasicInfoModal(ui.Modal, title="Editar Título e Descrição"):
            def __init__(self, current_title, current_description):
                super().__init__(timeout=300)
                self.title_input = ui.TextInput(
                    label="Novo Título",
                    default=current_title,
                    max_length=256,
                    required=True,
                )
                self.description_input = ui.TextInput(
                    label="Nova Descrição",
                    default=current_description,
                    style=discord.TextStyle.paragraph,
                    required=False,
                )
                self.add_item(self.title_input)
                self.add_item(self.description_input)

            async def on_submit(self, modal_interaction: Interaction):
                self.view.embed.title = self.title_input.value
                self.view.embed.description = (
                    self.description_input.value
                    if self.description_input.value
                    else Embed.Empty
                )
                await modal_interaction.response.edit_message(
                    embed=self.view.embed, view=self.view
                )
                self.stop()

        modal = BasicInfoModal(
            self.embed.title if self.embed.title != Embed.Empty else "",
            self.embed.description if self.embed.description != Embed.Empty else "",
        )
        modal.view = self
        await interaction.response.send_modal(modal)

    @ui.button(label="Adicionar Campo", style=ButtonStyle.secondary, emoji="➕")
    async def add_field(self, interaction: Interaction, button: ui.Button):
        if self.fields_added >= 10:
            await interaction.response.send_message(
                "Você atingiu o limite de 10 campos por embed.", ephemeral=True
            )
            return

        modal = AddFieldModal()
        await interaction.response.send_modal(modal)

        await modal.wait()

        if modal.field_name.value and modal.field_value.value:
            name = modal.field_name.value
            value = modal.field_value.value
            inline = (
                modal.field_inline.value.lower() == "sim"
                if modal.field_inline.value
                else False
            )
            self.embed.add_field(name=name, value=value, inline=inline)
            self.fields_added += 1
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.followup.send(
                "Nenhum campo foi adicionado.", ephemeral=True
            )

    @ui.button(label="Editar Imagens/Cores", style=ButtonStyle.secondary, emoji="🖼️")
    async def edit_media(self, interaction: Interaction, button: ui.Button):
        class MediaModal(ui.Modal, title="Editar Mídia e Cores"):
            def __init__(
                self,
                current_thumb,
                current_image,
                current_color_hex,
                current_author_name,
                current_author_icon,
            ):
                super().__init__(timeout=300)
                self.thumbnail_input = ui.TextInput(
                    label="URL da Miniatura (Thumbnail)",
                    placeholder="Cole a URL da imagem aqui",
                    default=current_thumb if current_thumb != Embed.Empty else "",
                    required=False,
                )
                self.image_input = ui.TextInput(
                    label="URL da Imagem Principal",
                    placeholder="Cole a URL da imagem aqui",
                    default=current_image if current_image != Embed.Empty else "",
                    required=False,
                )
                self.color_input = ui.TextInput(
                    label="Cor Hexadecimal (Ex: #FF00FF)",
                    placeholder="Ex: #FF00FF",
                    default=current_color_hex if current_color_hex != "" else "",
                    max_length=7,
                    required=False,
                )
                self.author_name_input = ui.TextInput(
                    label="Nome do Autor (opcional)",
                    placeholder="Ex: Equipe Outlaws",
                    default=(
                        current_author_name
                        if current_author_name != Embed.Empty
                        else ""
                    ),
                    required=False,
                )
                self.author_icon_input = ui.TextInput(
                    label="URL do Ícone do Autor (opcional)",
                    placeholder="URL do avatar do autor",
                    default=(
                        current_author_icon
                        if current_author_icon != Embed.Empty
                        else ""
                    ),
                    required=False,
                )
                self.add_item(self.thumbnail_input)
                self.add_item(self.image_input)
                self.add_item(self.color_input)
                self.add_item(self.author_name_input)
                self.add_item(self.author_icon_input)

            async def on_submit(self, modal_interaction: Interaction):
                if self.thumbnail_input.value:
                    self.view.embed.set_thumbnail(url=self.thumbnail_input.value)
                else:
                    self.view.embed.set_thumbnail(url=Embed.Empty)

                if self.image_input.value:
                    self.view.embed.set_image(url=self.image_input.value)
                else:
                    self.view.embed.set_image(url=Embed.Empty)

                if self.color_input.value:
                    try:
                        self.view.embed.color = Color.from_str(self.color_input.value)
                    except ValueError:
                        await modal_interaction.followup.send(
                            "Cor hexadecimal inválida. Use o formato #RRGGBB.",
                            ephemeral=True,
                        )
                        return
                else:
                    self.view.embed.color = Color.blue()

                author_name = self.author_name_input.value
                author_icon = (
                    self.author_icon_input.value
                    if self.author_icon_input.value
                    else Embed.Empty
                )
                if author_name:
                    self.view.embed.set_author(name=author_name, icon_url=author_icon)
                else:
                    self.view.embed.set_author(name=Embed.Empty)

                await modal_interaction.response.edit_message(
                    embed=self.view.embed, view=self.view
                )
                self.stop()

        current_thumb = (
            self.embed.thumbnail.url if self.embed.thumbnail else Embed.Empty
        )
        current_image = self.embed.image.url if self.embed.image else Embed.Empty
        current_color_hex = str(self.embed.color) if self.embed.color else ""
        current_author_name = (
            self.embed.author.name
            if self.embed.author and self.embed.author.name != Embed.Empty
            else ""
        )
        current_author_icon = (
            self.embed.author.icon_url
            if self.embed.author and self.embed.author.icon_url != Embed.Empty
            else ""
        )

        modal = MediaModal(
            current_thumb,
            current_image,
            current_color_hex,
            current_author_name,
            current_author_icon,
        )
        modal.view = self
        await interaction.response.send_modal(modal)

    @ui.button(label="Limpar Campos", style=ButtonStyle.danger, emoji="🧹")
    async def clear_fields(self, interaction: Interaction, button: ui.Button):
        self.embed.clear_fields()
        self.fields_added = 0
        await interaction.response.edit_message(embed=self.embed, view=self)

    @ui.button(label="Enviar Embed", style=ButtonStyle.success, emoji="✅", row=2)
    async def send_embed(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Embed enviado!", ephemeral=True)
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(content=None, view=self)
        except:
            pass

        try:
            await interaction.channel.send(embed=self.embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "Não tenho permissão para enviar o embed neste canal.", ephemeral=True
            )

        self.stop()


def setup_embed_commands(bot: commands.Bot):
    """
    Função para configurar e adicionar os comandos de criação de embed ao bot.
    """

    @bot.tree.command(
        name="criar_embed",
        description="[ADMIN] Crie um embed personalizado interativamente.",
    )
    @commands.has_permissions(administrator=True)
    async def criar_embed(interaction: Interaction):
        initial_embed = Embed(
            title="Novo Embed",
            description="Clique nos botões para editar o embed.",
            color=Color.blue(),
        )
        initial_embed.set_footer(
            text="ID do Embed: Criando...",
            icon_url=interaction.client.user.display_avatar,
        )
        initial_embed.timestamp = datetime.now()

        # Passamos 'bot' para a view para que ela possa acessar bot.user.display_avatar
        view = EmbedCreatorView(initial_embed, interaction.user.id, bot)

        await interaction.response.send_message(
            embed=initial_embed, view=view, ephemeral=True
        )
        view.message = await interaction.original_response()
