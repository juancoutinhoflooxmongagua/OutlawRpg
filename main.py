import discord
from discord.ext import commands, tasks
from discord import app_commands, Embed, Color, Interaction, ui, ButtonStyle
import json
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_DATA_FILE = os.path.join(SCRIPT_DIR, "outlaws_data.json")
GUILD_ID = 0  # COLOQUE O ID DO SEU SERVIDOR AQUI PARA TESTES RÁPIDOS

# --- CONFIGURAÇÕES DE GAME DESIGN ---
XP_PER_LEVEL_BASE = 150
XP_PER_MESSAGE_COOLDOWN_SECONDS = 60
ATTRIBUTE_POINTS_PER_LEVEL = 2
CRITICAL_CHANCE = 0.10
CRITICAL_MULTIPLIER = 1.5
INITIAL_MONEY = 100
INITIAL_HP = 100
INITIAL_ATTACK = 10
INITIAL_SPECIAL_ATTACK = 20
REVIVE_COST = 55
BOUNTY_PERCENTAGE = 0.20
TRANSFORM_COST = 2
MAX_ENERGY = 10
STARTING_LOCATION = "Abrigo dos Foras-da-Lei"

# --- DADOS GLOBAIS DO JOGO ---
BOSS_DATA = {
    "name": "Colosso de Pedra",
    "hp": 0,
    "max_hp": 5000,
    "attack": 150,
    "is_active": False,
    "participants": [],
    "channel_id": None,
}

WORLD_MAP = {
    "Abrigo dos Foras-da-Lei": {
        "type": "cidade",
        "emoji": "⛺",
        "conecta": ["Floresta Sussurrante"],
        "desc": "Um acampamento improvisado que serve de refúgio para os renegados.",
    },
    "Floresta Sussurrante": {
        "type": "selvagem",
        "emoji": "🌳",
        "conecta": ["Abrigo dos Foras-da-Lei", "Ruínas do Templo"],
        "desc": "Uma mata densa e perigosa, onde criaturas espreitam nas sombras.",
    },
    "Ruínas do Templo": {
        "type": "selvagem",
        "emoji": "🏛️",
        "conecta": ["Floresta Sussurrante"],
        "desc": "Os restos de um antigo local de poder, agora habitado por guardiões de pedra.",
    },
}
ENEMIES = {
    "Floresta Sussurrante": [
        {
            "name": "Lobo Faminto",
            "hp": 60,
            "attack": 12,
            "xp": 25,
            "money": 15,
            "thumb": "https://c.tenor.com/v5Ik3wkrjlwAAAAC/tenor.gif",
        },
        # NOVOS INIMIGOS PARA FLORESTA SUSSURRANTE:
        {
            "name": "Aranha Gigante",  # Nome do novo inimigo
            "hp": 50,  # Pontos de vida
            "attack": 15,  # Dano de ataque
            "xp": 30,  # Experiência concedida
            "money": 20,  # Dinheiro concedido
            "thumb": "https://c.tenor.com/cBKUDbUVHSAAAAAC/tenor.gif",  # Link para o GIF/imagem do inimigo (exemplo, troque pelo seu!)
        },
        {
            "name": "Dragão de Komodo",
            "hp": 70,
            "attack": 10,
            "xp": 28,
            "money": 18,
            "thumb": "https://c.tenor.com/gIzmfcS1-rcAAAAC/tenor.gif",  # Link para o GIF/imagem do inimigo (exemplo, troque pelo seu!)
        },
    ],
    "Ruínas do Templo": [
        {
            "name": "Guardião de Pedra",
            "hp": 400,
            "attack": 38,
            "xp": 260,
            "money": 200,
            "thumb": "https://c.tenor.com/NLQ2AoVfEQUAAAAd/tenor.gif",
        },
        # NOVOS INIMIGOS PARA RUÍNAS DO TEMPLO:
        {
            "name": "Espectro Antigo",  # Nome do novo inimigo
            "hp": 90,  # Pontos de vida
            "attack": 102,  # Dano de ataque
            "xp": 80,  # Experiência concedida
            "money": 160,  # Dinheiro concedido
            "thumb": "https://c.tenor.com/tTXMqhKPCFwAAAAd/tenor.gif",  # Link para o GIF/imagem do inimigo (exemplo, troque pelo seu!)
        },
        {
            "name": "Gárgula Vingativa",
            "hp": 220,
            "attack": 50,
            "xp": 65,
            "money": 165,
            "thumb": "https://c.tenor.com/Ub7Nd2q36RYAAAAd/tenor.gif",  # Link para o GIF/imagem do inimigo (exemplo, troque pelo seu!)
        },
    ],
}


# --- GERENCIAMENTO DE DADOS ---
def load_data():
    if not os.path.exists(PLAYER_DATA_FILE):
        return {}
    try:
        with open(PLAYER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


player_database = load_data()


def save_data():
    try:
        with open(PLAYER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(player_database, f, indent=4)
    except IOError as e:
        print(f"ERRO CRÍTICO AO SALVAR DADOS: {e}")


def get_player_data(user_id):
    return player_database.get(str(user_id))


# --- SETUP DO BOT ---
class OutlawsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        auto_save.start()
        energy_regeneration.start()
        boss_attack_loop.start()
        if GUILD_ID != 0:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        print("Comandos sincronizados!")

    async def on_ready(self):
        print(f"Bot {self.user} está online!")
        print(f"Dados de {len(player_database)} jogadores carregados.")

    async def close(self):
        print("Desligando e salvando dados...")
        save_data()
        await super().close()


bot = OutlawsBot()


def is_in_city(i: Interaction):
    p = get_player_data(i.user.id)
    # Primeiro, uma verificação rápida para garantir que 'p' existe antes de tentar acessá-lo.
    # Embora 'check_player_exists' seja o primeiro decorator, é bom ser defensivo.
    if not p:
        # Se não há dados do jogador, essa falha será capturada pelo CheckFailure geral
        # depois que check_player_exists falhar.
        return False  # Não deveria acontecer se check_player_exists estiver antes
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "cidade":
        return True
    raise NotInCity("Este comando só pode ser usado em uma cidade.")  # LANÇA A EXCEÇÃO


def is_in_wilderness(i: Interaction):
    p = get_player_data(i.user.id)
    if not p:
        return False  # Não deveria acontecer se check_player_exists estiver antes
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "selvagem":
        return True
    raise NotInWilderness(
        "Este comando só pode ser usado em áreas selvagens."
    )  # LANÇA A EXCEÇÃO


# A função check_player_exists deve ser a primeira a ser verificada nos comandos:
def check_player_exists(i: Interaction):
    p = get_player_data(i.user.id)
    return p and p.get("status") != "afk"


def create_xp_bar(current_xp: int, needed_xp: int, length: int = 10) -> str:
    if needed_xp == 0:
        return "`" + "█" * length + "`"
    progress = min(current_xp / needed_xp, 1.0)
    filled_length = int(length * progress)
    bar = "█" * filled_length + "░" * (length - filled_length)
    return f"`{bar}`"


async def check_and_process_levelup(
    player_data: dict, source: Interaction | discord.TextChannel
):
    level = player_data.get("level", 1)
    xp_needed = int(XP_PER_LEVEL_BASE * (level**1.2))
    if player_data["xp"] >= xp_needed:
        player_data["level"] += 1
        player_data["xp"] -= xp_needed
        player_data["attribute_points"] = (
            player_data.get("attribute_points", 0) + ATTRIBUTE_POINTS_PER_LEVEL
        )
        player_data["max_hp"] += 10
        player_data["hp"] = player_data["max_hp"]
        user_mention = ""
        if isinstance(source, Interaction):
            user_mention = source.user.mention
        else:  # Tenta encontrar o usuário para mencionar
            user = bot.get_user(
                int(
                    list(player_database.keys())[
                        list(player_database.values()).index(player_data)
                    ]
                )
            )
            if user:
                user_mention = user.mention
        embed = Embed(
            title="🌟 LEVEL UP! 🌟",
            description=f"Parabéns, {user_mention}! Você alcançou o **Nível {player_data['level']}**!",
            color=Color.gold(),
        )
        embed.set_thumbnail(
            url="https://media.tenor.com/drxH1lO9cfEAAAAi/dark-souls-bonfire.gif"
        )
        embed.add_field(
            name="Recompensas",
            value=f"🔹 **{ATTRIBUTE_POINTS_PER_LEVEL}** Pontos de Atributo\n🔹 Vida totalmente restaurada!",
            inline=False,
        )
        embed.set_footer(text="Use /distribuir_pontos para ficar mais forte!")
        if isinstance(source, Interaction):
            try:
                await source.followup.send(embed=embed)
            except:
                await source.channel.send(embed=embed)
        else:
            await source.send(embed=embed)


async def run_turn_based_combat(
    interaction: Interaction, player_data: dict, enemy: dict
):
    log = []
    player_hp = player_data["hp"]
    enemy_hp = enemy["hp"]
    embed = Embed(title=f"⚔️ Batalha Iniciada! ⚔️", color=Color.orange())
    embed.set_thumbnail(url=enemy.get("thumb"))
    embed.add_field(
        name=interaction.user.display_name,
        value=f"❤️ {player_hp}/{player_data['max_hp']}",
        inline=True,
    )
    embed.add_field(
        name=enemy["name"], value=f"❤️ {enemy_hp}/{enemy['hp']}", inline=True
    )
    await interaction.response.send_message(embed=embed)
    turn = 1
    while player_hp > 0 and enemy_hp > 0:
        await asyncio.sleep(2.5)
        player_dmg = random.randint(player_data["attack"] // 2, player_data["attack"])
        crit_msg = ""
        if random.random() < CRITICAL_CHANCE:
            player_dmg = int(player_dmg * CRITICAL_MULTIPLIER)
            crit_msg = "💥 **CRÍTICO!** "
        log.append(
            f"➡️ **Turno {turn}**: {crit_msg}Você ataca e causa `{player_dmg}` de dano."
        )
        enemy_hp -= player_dmg
        if len(log) > 5:
            log.pop(0)
        embed.description = "\n".join(log)
        embed.set_field_at(
            1,
            name=enemy["name"],
            value=f"❤️ {max(0, enemy_hp)}/{enemy['hp']}",
            inline=True,
        )
        await interaction.edit_original_response(embed=embed)
        if enemy_hp <= 0:
            break
        await asyncio.sleep(2.5)
        enemy_dmg = random.randint(enemy["attack"] // 2, enemy["attack"])
        log.append(
            f"⬅️ **Turno {turn}**: {enemy['name']} ataca e causa `{enemy_dmg}` de dano."
        )
        player_hp -= enemy_dmg
        if len(log) > 5:
            log.pop(0)
        embed.description = "\n".join(log)
        embed.set_field_at(
            0,
            name=interaction.user.display_name,
            value=f"❤️ {max(0, player_hp)}/{player_data['max_hp']}",
            inline=True,
        )
        await interaction.edit_original_response(embed=embed)
        turn += 1
    final_embed = Embed()
    player_database[str(interaction.user.id)]["hp"] = max(0, player_hp)
    if player_hp <= 0:
        final_embed.title = "☠️ Você Foi Derrotado!"
        final_embed.color = Color.dark_red()
        player_database[str(interaction.user.id)]["status"] = "dead"
    else:
        final_embed.title = "🏆 Vitória! 🏆"
        final_embed.color = Color.green()
        final_embed.description = f"Você derrotou o {enemy['name']}!"
        final_embed.add_field(
            name="Recompensas", value=f"💰 +${enemy['money']}\n✨ +{enemy['xp']} XP"
        )
        player_database[str(interaction.user.id)]["money"] += enemy["money"]
        player_database[str(interaction.user.id)]["xp"] += enemy["xp"]
        await check_and_process_levelup(
            player_database[str(interaction.user.id)], interaction
        )
    save_data()
    await interaction.edit_original_response(embed=final_embed, view=None)


# --- VIEWS DA INTERFACE (BOTÕES E MENUS) ---


class ClassChooserView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.chosen_class = None
        self.chosen_style = None

    @ui.select(
        placeholder="Escolha sua Classe...",
        options=[
            discord.SelectOption(label="Espadachim", emoji="⚔️"),
            discord.SelectOption(label="Lutador", emoji="🥊"),
            discord.SelectOption(label="Atirador", emoji="🏹"),
            discord.SelectOption(label="Curandeiro", emoji="🩹"),
        ],
    )
    async def class_select(self, i: Interaction, s: ui.Select):
        self.chosen_class = s.values[0]
        await i.response.send_message(
            f"Classe: **{self.chosen_class}**. Agora, a fonte de poder."
        )

    @ui.select(
        placeholder="Escolha sua Fonte de Poder...",
        options=[
            discord.SelectOption(label="Habilidade Inata", emoji="💪"),
            discord.SelectOption(label="Aura", emoji="✨"),
        ],
    )
    async def style_select(self, i: Interaction, s: ui.Select):
        self.chosen_style = s.values[0]
        await i.response.send_message(f"Fonte de Poder: **{self.chosen_style}**.")

    @ui.button(label="Confirmar Criação", style=ButtonStyle.success, row=2)
    async def confirm_button(self, i: Interaction, b: ui.Button):
        if not self.chosen_class or not self.chosen_style:
            await i.response.send_message("Escolha uma classe e um estilo!")
            return
        user_id = str(i.user.id)
        if user_id in player_database:
            await i.response.send_message("Você já possui uma ficha!")
            return
        base_stats = {"hp": 100, "attack": 10, "special_attack": 20}
        if self.chosen_class == "Lutador":
            base_stats["hp"] += 20
            base_stats["attack"] += 5
        elif self.chosen_class == "Espadachim":
            base_stats["attack"] += 10
            base_stats["special_attack"] -= 5
        elif self.chosen_class == "Atirador":
            base_stats["hp"] -= 10
            base_stats["special_attack"] += 10
        elif self.chosen_class == "Curandeiro":
            base_stats["special_attack"] += 5
        player_database[user_id] = {
            "name": i.user.display_name,
            "class": self.chosen_class,
            "style": self.chosen_style,
            "xp": 0,
            "level": 1,
            "money": INITIAL_MONEY,
            "hp": base_stats["hp"],
            "max_hp": base_stats["hp"],
            "base_attack": base_stats["attack"],
            "base_special_attack": base_stats["special_attack"],
            "attack": base_stats["attack"],
            "special_attack": base_stats["special_attack"],
            "inventory": {},
            "cooldowns": {},
            "status": "online",
            "bounty": 0,
            "kills": 0,
            "deaths": 0,
            "energy": MAX_ENERGY,
            "is_transformed": False,
            "attribute_points": 0,
            "location": STARTING_LOCATION,
            "transform_name": {
                "Espadachim": "Lâmina Fantasma",
                "Lutador": "Punho de Aço",
                "Atirador": "Olho de Águia",
                "Curandeiro": "Bênção Vital",
            }.get(self.chosen_class, "Super Forma"),
        }
        save_data()
        embed = Embed(
            title=f"Ficha de {i.user.display_name} Criada!",
            description=f"Bem-vindo ao mundo de OUTLAWS, **{self.chosen_class}** que usa **{self.chosen_style}**!",
            color=Color.green(),
        )
        embed.set_thumbnail(
            url=i.user.avatar.url if i.user.avatar else discord.Embed.Empty
        )
        embed.set_footer(text="Use /perfil para ver seus status.")
        await i.response.edit_message(content=None, embed=embed, view=None)
        self.stop()


class ProfileView(ui.View):
    def __init__(self, user: discord.Member, bot_user: discord.ClientUser):
        super().__init__(timeout=180)
        self.user = user
        self.bot_user = bot_user

    def create_profile_embed(self) -> discord.Embed:
        player_data = get_player_data(self.user.id)
        embed_color = (
            Color.orange()
            if player_data.get("is_transformed", False)
            else self.user.color
        )
        title_prefix = (
            f"🔥 {player_data.get('transform_name', 'Transformado')} | "
            if player_data.get("is_transformed", False)
            else ""
        )
        embed = Embed(
            title=f"{title_prefix}Perfil de {self.user.display_name}", color=embed_color
        )
        embed.set_thumbnail(
            url=self.user.avatar.url if self.user.avatar else discord.Embed.Empty
        )
        embed.set_image(url="https://c.tenor.com/twwaRu0KGWoAAAAC/tenor.gif")
        location = player_data.get("location", "Desconhecido")
        location_info = WORLD_MAP.get(location, {})
        status_map = {"online": "🟢 Online", "dead": "💀 Morto", "afk": "🌙 AFK"}
        embed.add_field(
            name="📍 Localização & Status",
            value=f"**{location_info.get('emoji', '❓')} {location}**\n*Status: {status_map.get(player_data['status'], '?')}*",
            inline=True,
        )
        xp_needed = int(XP_PER_LEVEL_BASE * (player_data["level"] ** 1.2))
        xp_bar = create_xp_bar(player_data["xp"], xp_needed)
        embed.add_field(
            name="⚔️ Classe & Nível",
            value=f"**{player_data['class']}** | Nível **{player_data['level']}**\n{xp_bar} `{player_data['xp']}/{xp_needed}`",
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(
            name="❤️ Vida",
            value=f"**{player_data['hp']}/{player_data['max_hp']}**",
            inline=True,
        )
        embed.add_field(
            name="🗡️ Ataque", value=f"**{player_data['attack']}**", inline=True
        )
        embed.add_field(
            name="✨ Atq. Especial",
            value=f"**{player_data['special_attack']}**",
            inline=True,
        )
        embed.add_field(
            name="🌟 Pontos de Atributo",
            value=f"**{player_data.get('attribute_points', 0)}**",
            inline=True,
        )
        embed.add_field(
            name="⚡ Energia",
            value=f"**{player_data['energy']}/{MAX_ENERGY}**",
            inline=True,
        )
        embed.add_field(
            name="💰 Dinheiro", value=f"**${player_data['money']}**", inline=True
        )
        embed.set_footer(
            text=f"Outlaws RPG • Perfil gerado em", icon_url=self.bot_user.avatar.url
        )
        embed.timestamp = datetime.now()
        return embed

    def create_inventory_embed(self) -> discord.Embed:
        player_data = get_player_data(self.user.id)
        embed = Embed(
            title=f"Inventário de {self.user.display_name}", color=Color.dark_gold()
        )
        embed.set_author(
            name=self.user.display_name,
            icon_url=self.user.avatar.url if self.user.avatar else discord.Embed.Empty,
        )
        inventory_list = [
            f"{'🧪' if item == 'pocao' else '🔮' if item == 'invocador' else '❔'} **{item.capitalize()}** `x{amount}`"
            for item, amount in player_data["inventory"].items()
        ]
        embed.description = (
            "\n".join(inventory_list)
            if inventory_list
            else "*Seu inventário está vazio.*"
        )
        embed.add_field(
            name="💰 Bounty", value=f"`${player_data['bounty']}`", inline=True
        )
        embed.add_field(name="☠️ Kills", value=f"`{player_data['kills']}`", inline=True)
        embed.set_footer(
            text=f"Outlaws RPG • Inventário", icon_url=self.bot_user.avatar.url
        )
        embed.timestamp = datetime.now()
        return embed

    @ui.button(label="Perfil", style=ButtonStyle.primary, emoji="👤", disabled=True)
    async def profile_button(self, i: Interaction, b: ui.Button):
        self.profile_button.disabled = True
        self.inventory_button.disabled = False
        await i.response.edit_message(embed=self.create_profile_embed(), view=self)

    @ui.button(label="Inventário", style=ButtonStyle.secondary, emoji="🎒")
    async def inventory_button(self, i: Interaction, b: ui.Button):
        self.inventory_button.disabled = True
        self.profile_button.disabled = False
        await i.response.edit_message(embed=self.create_inventory_embed(), view=self)


class TravelView(ui.View):
    def __init__(self, current_location: str, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        for dest in WORLD_MAP.get(current_location, {}).get("conecta", []):
            self.add_item(
                TravelButton(
                    label=dest, emoji=WORLD_MAP.get(dest, {}).get("emoji", "❓")
                )
            )


class TravelButton(ui.Button):
    def __init__(self, label: str, emoji: str):
        super().__init__(label=label, style=ButtonStyle.secondary, emoji=emoji)

    async def callback(self, i: Interaction):
        player_data = get_player_data(self.view.user_id)
        if not player_data:
            await i.response.send_message("Erro ao encontrar sua ficha.")
            return
        player_data["location"] = self.label
        save_data()
        await i.response.edit_message(
            embed=Embed(
                title=f"✈️ Viagem Concluída",
                description=f"Você viajou e chegou em **{self.label}**.",
                color=Color.blue(),
            ),
            view=None,
        )


class HelpView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @ui.select(
        placeholder="Escolha uma categoria da Wiki...",
        options=[
            discord.SelectOption(label="Introdução", emoji="📜"),
            discord.SelectOption(label="Comandos Gerais", emoji="👤"),
            discord.SelectOption(label="Comandos de Ação", emoji="⚔️"),
            discord.SelectOption(label="Sistema de Classes", emoji="🛡️"),
            discord.SelectOption(label="Sistema de Combate", emoji="💥"),
        ],
    )
    async def select_callback(self, i: Interaction, s: ui.Select):
        topic = s.values[0]
        embed = Embed(title=f"📜 Wiki OUTLAWS - {topic}", color=Color.blurple())
        if topic == "Introdução":
            embed.description = "Bem-vindo a OUTLAWS, um mundo impiedoso onde apenas os mais fortes sobrevivem..."
        elif topic == "Comandos Gerais":
            embed.add_field(name="/perfil", value="Mostra seu perfil.", inline=False)
            embed.add_field(
                name="/distribuir_pontos", value="Melhora atributos.", inline=False
            )
            embed.add_field(name="/reviver", value="Volta à vida.", inline=False)
            embed.add_field(
                name="/ranking", value="Mostra os mais mortais.", inline=False
            )
            embed.add_field(
                name="/afk | /voltar", value="Entra/sai do modo Ausente.", inline=False
            )
        elif topic == "Comandos de Ação":
            embed.add_field(
                name="/cacar | /batalhar",
                value="Inicia um combate por turnos.",
                inline=False,
            )
            embed.add_field(name="/atacar", value="Ataca outro jogador.", inline=False)
            embed.add_field(
                name="/trabalhar", value="Ganha dinheiro e XP.", inline=False
            )
            embed.add_field(name="/viajar", value="Move-se pelo mundo.", inline=False)
            embed.add_field(
                name="/loja | /aprimorar", value="Disponíveis em cidades.", inline=False
            )
        elif topic == "Sistema de Classes":
            embed.description = "**Espadachim**: Equilibrado.\n**Lutador**: Mais vida/ataque.\n**Atirador**: Mestre do dano especial.\n**Curandeiro**: Pode curar com `/curar`."
        elif topic == "Sistema de Combate":
            embed.description = "Batalhas são por turnos. Acertos Críticos (10% de chance) causam 50% a mais de dano!"
        embed.set_footer(text="Selecione outra opção para aprender mais.")
        await i.response.edit_message(embed=embed)


class ShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(
            self.BuyButton(item_id="pocao", price=50, label="Comprar Poção", emoji="🧪")
        )
        self.add_item(
            self.BuyButton(
                item_id="invocador", price=1000, label="Comprar Invocador", emoji="🔮"
            )
        )

    class BuyButton(ui.Button):
        def __init__(self, item_id: str, price: int, label: str, emoji: str):
            super().__init__(label=label, style=ButtonStyle.primary, emoji=emoji)
            self.item_id, self.price = item_id, price

        async def callback(self, i: Interaction):
            player_data = get_player_data(i.user.id)
            if not player_data:
                await i.response.send_message("Crie uma ficha primeiro!")
                return
            if player_data["money"] < self.price:
                await i.response.send_message("Dinheiro insuficiente!")
                return
            player_data["money"] -= self.price
            player_data["inventory"][self.item_id] = (
                player_data["inventory"].get(self.item_id, 0) + 1
            )
            save_data()
            await i.response.send_message(
                f"**{i.user.display_name}** comprou 1x {self.item_id.capitalize()}!"
            )


# --- COMANDOS DO BOT ---


# Seção 1: Comandos de Personagem e Status
@bot.tree.command(
    name="criar_ficha", description="Cria sua ficha de personagem no mundo de OUTLAWS."
)
async def criar_ficha(i: Interaction):
    if get_player_data(i.user.id):
        await i.response.send_message("Você já possui uma ficha!")
        return
    await i.response.send_message(
        embed=Embed(
            title="Criação de Personagem",
            description="Escolha os fundamentos do seu personagem.",
            color=Color.blurple(),
        ),
        view=ClassChooserView(),
    )


@bot.tree.command(
    name="perfil",
    description="Mostra seu perfil de fora-da-lei com um layout profissional.",
)
@app_commands.check(check_player_exists)
async def perfil(i: Interaction, membro: discord.Member = None):
    target_user = membro or i.user
    if not get_player_data(target_user.id):
        await i.response.send_message("Essa pessoa ainda não é um fora-da-lei.")
        return
    await i.response.send_message(
        embed=ProfileView(target_user, bot.user).create_profile_embed(),
        view=ProfileView(target_user, bot.user),
    )


@bot.tree.command(name="reviver", description="Pague uma taxa para voltar à vida.")
@app_commands.check(check_player_exists)
async def reviver(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["status"] != "dead":
        await i.response.send_message("Você já está vivo!")
        return
    if player_data["money"] < REVIVE_COST:
        await i.response.send_message(f"Você precisa de ${REVIVE_COST} para reviver.")
        return
    player_data["money"] -= REVIVE_COST
    player_data["hp"] = player_data["max_hp"]
    player_data["status"] = "online"
    save_data()
    await i.response.send_message(
        embed=Embed(
            title="✨ De Volta à Vida",
            description=f"Você pagou ${REVIVE_COST} e trapaceou a morte.",
            color=Color.light_grey(),
        )
    )


@bot.tree.command(
    name="distribuir_pontos",
    description="Use seus pontos de atributo para fortalecer seu personagem.",
)
@app_commands.check(check_player_exists)
@app_commands.describe(
    atributo="Onde você quer investir seus pontos.",
    quantidade="Quantos pontos quer usar.",
)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name="💪 Força (Ataque)", value="attack"),
        app_commands.Choice(
            name="✨ Agilidade (Atq. Especial)", value="special_attack"
        ),
        app_commands.Choice(name="❤️ Vitalidade (HP)", value="hp"),
    ]
)
async def distribuir_pontos(
    i: Interaction, atributo: app_commands.Choice[str], quantidade: int
):
    player_data = get_player_data(i.user.id)
    available_points = player_data.get("attribute_points", 0)
    if quantidade <= 0:
        await i.response.send_message("A quantidade deve ser positiva.")
        return
    if available_points < quantidade:
        await i.response.send_message(f"Você só tem {available_points} pontos.")
        return
    player_data["attribute_points"] -= quantidade
    if atributo.value == "attack":
        player_data["base_attack"] += quantidade * 2
        player_data["attack"] = (
            player_data["base_attack"]
            if not player_data["is_transformed"]
            else int(player_data["base_attack"] * 1.5)
        )
    elif atributo.value == "special_attack":
        player_data["base_special_attack"] += quantidade * 3
        player_data["special_attack"] = (
            player_data["base_special_attack"]
            if not player_data["is_transformed"]
            else int(player_data["base_special_attack"] * 1.5)
        )
    elif atributo.value == "hp":
        player_data["max_hp"] += quantidade * 5
        player_data["hp"] += quantidade * 5
    save_data()
    await i.response.send_message(
        embed=Embed(
            title="📈 Atributos Aprimorados",
            description=f"Você investiu **{quantidade}** pontos em **{atributo.name}**.",
            color=Color.green(),
        )
    )


@bot.tree.command(
    name="ranking", description="Mostra o ranking de MVPs (Mais Abates) do servidor."
)
async def ranking(i: Interaction):
    if not player_database:
        await i.response.send_message("Nenhum jogador no ranking ainda.")
        return
    sorted_players = sorted(
        player_database.values(), key=lambda p: p.get("kills", 0), reverse=True
    )
    embed = Embed(
        title="🏆 Ranking de MVPs - OUTLAWS 🏆",
        description="Os fora-da-lei mais temidos do servidor.",
        color=Color.gold(),
    )
    for idx, player in enumerate(sorted_players[:10]):
        embed.add_field(
            name=f"{idx+1}. {player.get('name', 'Desconhecido')}",
            value=f"**Abates:** {player.get('kills', 0)} | **Mortes:** {player.get('deaths', 0)} | **Bounty:** ${player.get('bounty', 0)}",
            inline=False,
        )
    await i.response.send_message(embed=embed)


# Seção 2: Comandos de Ação no Mundo
@bot.tree.command(
    name="viajar", description="Viaja para uma nova localização no mundo de OUTLAWS."
)
@app_commands.check(check_player_exists)
async def viajar(i: Interaction):
    player_data = get_player_data(i.user.id)
    current_location = player_data.get("location", STARTING_LOCATION)
    view = TravelView(current_location, i.user.id)
    if not view.children:
        await i.response.send_message("Não há para onde viajar a partir daqui.")
        return
    embed = Embed(
        title="✈️ Para Onde Vamos?",
        description=f"Você está em **{current_location}**. Escolha seu próximo destino.",
        color=Color.blue(),
    )
    await i.response.send_message(embed=embed, view=view)


@bot.tree.command(
    name="trabalhar",
    description="Faça um trabalho na cidade para ganhar dinheiro e XP.",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_city)
async def trabalhar(i: Interaction):
    player_data = get_player_data(i.user.id)
    now, cooldown_key, last_work = (
        datetime.now().timestamp(),
        "work_cooldown",
        player_data["cooldowns"].get("work_cooldown", 0),
    )
    if now - last_work < 30:
        await i.response.send_message(f"Você já trabalhou recentemente.")
        return
    job = random.choice(
        [
            {"name": "Contrabando", "money": random.randint(40, 60), "xp": 20},
            {"name": "Punga", "money": random.randint(20, 80), "xp": 30},
            {"name": "Segurança Particular", "money": random.randint(50, 55), "xp": 25},
        ]
    )
    money_gain, xp_gain = job["money"], job["xp"]
    player_data["money"] += money_gain
    player_data["xp"] += xp_gain
    player_data["cooldowns"][cooldown_key] = now
    embed = Embed(
        title="💰 Bico Concluído!",
        description=f"Você realizou um trabalho de **{job['name']}**.",
        color=Color.dark_gold(),
    )
    embed.add_field(
        name="Recompensa", value=f"Você ganhou **${money_gain}** e **{xp_gain}** XP."
    )
    save_data()
    await i.response.send_message(embed=embed)
    await check_and_process_levelup(player_data, i)


@bot.tree.command(
    name="loja", description="Mostra os itens disponíveis para compra na cidade."
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_city)
async def loja(i: Interaction):
    embed = Embed(
        title="🛒 Loja OUTLAWS 🛒",
        description="Itens para te ajudar em sua jornada.",
        color=Color.dark_teal(),
    )
    embed.add_field(
        name="Poção de Vida (ID: `pocao`)",
        value="Restaura 50 HP. Custa **$75**.",
        inline=False,
    )
    embed.add_field(
        name="Invocador do Colosso (ID: `invocador`)",
        value="Invoca o terrível boss. Custa **$1000**.",
        inline=False,
    )
    await i.response.send_message(embed=embed, view=ShopView())


@bot.tree.command(
    name="aprimorar",
    description="Gaste dinheiro para fortalecer seus ataques na cidade.",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_city)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name="Ataque Básico", value="attack"),
        app_commands.Choice(name="Ataque Especial", value="special_attack"),
    ]
)
async def aprimorar(i: Interaction, atributo: app_commands.Choice[str]):
    player_data = get_player_data(i.user.id)
    attr_key = f"base_{atributo.value}"
    base_stat = INITIAL_ATTACK if "attack" in attr_key else INITIAL_SPECIAL_ATTACK
    cost = 100 + (player_data[attr_key] - base_stat) * 20
    if player_data["money"] < cost:
        await i.response.send_message(f"Você precisa de ${cost} para aprimorar.")
        return
    player_data["money"] -= cost
    player_data[attr_key] += 2
    if not player_data["is_transformed"]:
        player_data[atributo.value] = player_data[attr_key]
    save_data()
    await i.response.send_message(
        f"✨ Aprimoramento concluído! Seu {atributo.name} base aumentou para `{player_data[attr_key]}`."
    )


# Seção 3: Comandos de Combate e Habilidades
@bot.tree.command(
    name="cacar",
    description="Caça uma criatura na sua localização atual (combate por turnos).",
)
@app_commands.check(check_player_exists)
@app_commands.check(is_in_wilderness)
async def cacar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["status"] == "dead":
        await i.response.send_message("Mortos não caçam.")
        return
    location = player_data.get("location")
    enemy_template = random.choice(ENEMIES[location])
    enemy = enemy_template.copy()
    await run_turn_based_combat(i, player_data, enemy)


@bot.tree.command(
    name="batalhar",
    description="Enfrenta um Ex-Cavaleiro para testar sua força (combate por turnos).",
)
@app_commands.check(check_player_exists)
@app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
@app_commands.describe(
    primeiro_ataque="Escolha seu ataque inicial: Básico ou Especial."
)
@app_commands.choices(
    primeiro_ataque=[
        app_commands.Choice(name="Ataque Básico", value="basico"),
        app_commands.Choice(name="Ataque Especial", value="especial"),
    ]
)
async def batalhar(i: Interaction, primeiro_ataque: app_commands.Choice[str]):
    player_data = get_player_data(i.user.id)
    if player_data["status"] == "dead":
        await i.response.send_message("Mortos não batalham.")
        return

    # Se o jogador escolher ataque especial, verifica a energia
    if primeiro_ataque.value == "especial":
        # Usando TRANSFORM_COST como custo de energia para ataque especial
        if player_data.get("energy", 0) < TRANSFORM_COST:
            await i.response.send_message(
                f"Você não tem energia suficiente ({TRANSFORM_COST}) para um Ataque Especial inicial! Use Ataque Básico ou recupere energia."
            )
            return

    enemy = {
        "name": "Ex-Cavaleiro Renegado",
        "hp": 320,
        "attack": 95,
        "xp": 390,
        "money": 400,
        "thumb": "https://c.tenor.com/ebFt6wJWEu8AAAAC/tenor.gif",
    }
    # Passa o estilo de ataque escolhido para a função de combate
    await run_turn_based_combat(i, player_data, enemy, primeiro_ataque.value)


async def run_turn_based_combat(
    interaction: Interaction,
    player_data: dict,
    enemy: dict,
    initial_attack_style: str = "basico",
):
    log = []
    player_hp = player_data["hp"]
    enemy_hp = enemy["hp"]

    embed = Embed(title=f"⚔️ Batalha Iniciada! ⚔️", color=Color.orange())
    embed.set_thumbnail(url=enemy.get("thumb"))
    embed.add_field(
        name=interaction.user.display_name,
        value=f"❤️ {player_hp}/{player_data['max_hp']}",
        inline=True,
    )
    embed.add_field(
        name=enemy["name"], value=f"❤️ {enemy_hp}/{enemy['hp']}", inline=True
    )

    # Envia a mensagem inicial da batalha
    battle_message = await interaction.response.send_message(embed=embed)
    battle_message = await interaction.original_response()

    turn = 1
    while player_hp > 0 and enemy_hp > 0:
        await asyncio.sleep(2.5)  # Pausa entre turnos

        # --- Turno do Jogador ---
        player_dmg = 0
        attack_type_name = ""
        crit_msg = ""

        # Lógica para o PRIMEIRO ataque (baseado na escolha do comando)
        if turn == 1:
            if initial_attack_style == "basico":
                player_dmg = random.randint(
                    player_data["attack"] // 2, player_data["attack"]
                )
                attack_type_name = "Ataque Básico"
            elif initial_attack_style == "especial":
                player_dmg = random.randint(
                    int(player_data["special_attack"] * 0.8),
                    int(player_data["special_attack"] * 1.5),
                )
                attack_type_name = "Ataque Especial"
                # Dedução da energia para o ataque especial inicial
                player_data["energy"] = max(0, player_data["energy"] - TRANSFORM_COST)
        else:
            # Para os turnos seguintes, o ataque é sempre básico
            player_dmg = random.randint(
                player_data["attack"] // 2, player_data["attack"]
            )
            attack_type_name = "Ataque Básico"

        if random.random() < CRITICAL_CHANCE:
            player_dmg = int(player_dmg * CRITICAL_MULTIPLIER)
            crit_msg = "💥 **CRÍTICO!** "

        enemy_hp -= player_dmg
        log.append(
            f"➡️ **Turno {turn}**: {crit_msg}Você usou **{attack_type_name}** e causou `{player_dmg}` de dano."
        )
        if len(log) > 5:
            log.pop(0)

        # Atualiza o embed
        embed.description = "\n".join(log)
        embed.set_field_at(
            0,
            name=interaction.user.display_name,
            value=f"❤️ {max(0, player_hp)}/{player_data['max_hp']}",
            inline=True,
        )
        embed.set_field_at(
            1,
            name=enemy["name"],
            value=f"❤️ {max(0, enemy_hp)}/{enemy['hp']}",
            inline=True,
        )
        await battle_message.edit(embed=embed)

        if enemy_hp <= 0:
            break  # Inimigo derrotado

        await asyncio.sleep(2.5)  # Pausa antes do ataque do inimigo

        # --- Turno do Inimigo ---
        enemy_dmg = random.randint(enemy["attack"] // 2, enemy["attack"])
        player_hp -= enemy_dmg

        log.append(f"⬅️ {enemy['name']} ataca e causa `{enemy_dmg}` de dano.")
        if len(log) > 5:
            log.pop(0)

        # Atualiza o embed
        embed.description = "\n".join(log)
        embed.set_field_at(
            0,
            name=interaction.user.display_name,
            value=f"❤️ {max(0, player_hp)}/{player_data['max_hp']}",
            inline=True,
        )
        await battle_message.edit(embed=embed)

        turn += 1

    # --- Fim da Batalha ---
    final_embed = Embed()
    player_database[str(interaction.user.id)]["hp"] = max(0, player_hp)

    if player_hp <= 0:
        final_embed.title = "☠️ Você Foi Derrotado!"
        final_embed.color = Color.dark_red()
        player_database[str(interaction.user.id)]["status"] = "dead"
        player_database[str(interaction.user.id)]["deaths"] += 1
        final_embed.description = f"O {enemy['name']} foi muito forte para você."
    else:
        final_embed.title = "🏆 Vitória! 🏆"
        final_embed.color = Color.green()
        final_embed.description = f"Você derrotou o {enemy['name']}!"
        final_embed.add_field(
            name="Recompensas", value=f"💰 +${enemy['money']}\n✨ +{enemy['xp']} XP"
        )
        player_database[str(interaction.user.id)]["money"] += enemy["money"]
        player_database[str(interaction.user.id)]["xp"] += enemy["xp"]
        await check_and_process_levelup(
            player_database[str(interaction.user.id)], interaction
        )

    save_data()
    await battle_message.edit(embed=final_embed)


@bot.tree.command(name="atacar", description="Ataca outro jogador em um duelo.")
@app_commands.check(check_player_exists)
@app_commands.describe(
    alvo="O jogador que você quer atacar.", estilo="O tipo de ataque a ser usado."
)
@app_commands.choices(
    estilo=[
        app_commands.Choice(name="Ataque Básico", value="basico"),
        app_commands.Choice(name="Ataque Especial", value="especial"),
    ]
)
async def atacar(
    i: Interaction, alvo: discord.Member, estilo: app_commands.Choice[str]
):
    attacker_id, target_id = str(i.user.id), str(alvo.id)
    if attacker_id == target_id:
        await i.response.send_message("Você não pode atacar a si mesmo!")
        return
    attacker_data, target_data = get_player_data(attacker_id), get_player_data(
        target_id
    )
    if not target_data:
        await i.response.send_message("Este jogador não tem uma ficha!")
        return
    if attacker_data["status"] == "dead" or target_data["status"] == "dead":
        await i.response.send_message("Um dos jogadores está morto.")
        return
    now, cooldown_key, cooldown_duration = (
        datetime.now().timestamp(),
        f"{estilo.value}_attack_cooldown",
        10 if estilo.value == "basico" else 30,
    )
    if now - attacker_data["cooldowns"].get(cooldown_key, 0) < cooldown_duration:
        await i.response.send_message(f"Seu {estilo.name} está em cooldown!")
        return
    if estilo.value == "basico":
        damage, attack_name = (
            random.randint(
                attacker_data["attack"] // 2, int(attacker_data["attack"] * 1.2)
            ),
            "Ataque Básico",
        )
    else:
        damage, attack_name = (
            random.randint(
                int(attacker_data["special_attack"] * 0.8),
                int(attacker_data["special_attack"] * 1.5),
            ),
            "Ataque Especial",
        )
    crit_msg = ""
    if random.random() < CRITICAL_CHANCE:
        damage = int(damage * CRITICAL_MULTIPLIER)
        crit_msg = "💥 **ACERTO CRÍTICO!** "
    target_data["hp"] -= damage
    attacker_data["cooldowns"][cooldown_key] = now
    embed = Embed(color=Color.red())
    if target_data["hp"] <= 0:
        (
            target_data["hp"],
            target_data["status"],
            target_data["deaths"],
            target_data["bounty"],
        ) = (0, "dead", target_data["deaths"] + 1, 0)
        attacker_data["kills"] += 1
        money_stolen, bounty_claim = (
            int(target_data["money"] * BOUNTY_PERCENTAGE),
            attacker_data["bounty"],
        )
        attacker_data["money"] += money_stolen + bounty_claim
        attacker_data["bounty"] += 100
        embed.title = f"☠️ ABATE! {i.user.display_name} derrotou {alvo.display_name}!"
        embed.description = f"{crit_msg}{i.user.display_name} usou **{attack_name}** e causou **{damage}** de dano, finalizando o oponente.\n\n recompensa de **${bounty_claim}** foi clamada!\n**${money_stolen}** (20%) foram roubados.\n{i.user.display_name} agora tem uma recompensa de **${attacker_data['bounty']}** por sua cabeça."
    else:
        embed.title = f"⚔️ Duelo de Fora-da-Lei ⚔️"
        embed.description = f"{crit_msg}{i.user.display_name} usou **{attack_name}** em {alvo.display_name} e causou **{damage}** de dano!\n{alvo.display_name} agora tem **{target_data['hp']}/{target_data['max_hp']}** HP."
    save_data()
    await i.response.send_message(embed=embed)


# Seção 3: Comandos de Combate e Habilidades
@bot.tree.command(
    name="atacar_boss", description="Ataca o boss global quando ele estiver ativo."
)
@app_commands.check(check_player_exists)
@app_commands.choices(
    estilo=[
        app_commands.Choice(name="Ataque Básico", value="basico"),
        app_commands.Choice(name="Ataque Especial", value="especial"),
    ]
)
async def atacar_boss(i: Interaction, estilo: app_commands.Choice[str]):
    if not BOSS_DATA["is_active"]:
        await i.response.send_message("Não há nenhum boss ativo.")
        return
    player_id, player_data = str(i.user.id), get_player_data(i.user.id)

    # Adicione esta verificação para jogadores mortos
    if player_data["status"] == "dead":
        await i.response.send_message(
            "Você não pode atacar o boss enquanto estiver morto."
        )
        return

    if player_id not in BOSS_DATA["participants"]:
        BOSS_DATA["participants"].append(player_id)
    now, cooldown_key, last_attack, cooldown_duration = (
        datetime.now().timestamp(),
        f"boss_{estilo.value}_cooldown",
        player_data["cooldowns"].get(f"boss_{estilo.value}_cooldown", 0),
        5 if estilo.value == "basico" else 15,
    )
    if now - last_attack < cooldown_duration:
        await i.response.send_message(
            f"Seu {estilo.name} contra o boss está em cooldown!"
        )
        return
    damage = (
        random.randint(player_data["attack"], int(player_data["attack"] * 1.5))
        if estilo.value == "basico"
        else random.randint(
            player_data["special_attack"], int(player_data["special_attack"] * 1.8)
        )
    )
    crit_msg = ""
    if random.random() < CRITICAL_CHANCE:
        damage = int(damage * CRITICAL_MULTIPLIER)
        crit_msg = "💥 **CRÍTICO!** "
    BOSS_DATA["hp"] -= damage
    player_data["cooldowns"][cooldown_key] = now
    save_data()
    await i.response.send_message(
        f"{crit_msg}Você atacou o {BOSS_DATA['name']} e causou `{damage}` de dano! Vida restante: `{max(0, BOSS_DATA['hp'])}/{BOSS_DATA['max_hp']}`."
    )
    if BOSS_DATA["hp"] <= 0:
        embed = Embed(
            title=f"🎉 O {BOSS_DATA['name']} FOI DERROTADO! 🎉",
            description="Recompensas foram distribuídas!",
            color=Color.green(),
        )
        await i.channel.send(embed=embed)
        for p_id in BOSS_DATA["participants"]:
            if p_data := get_player_data(p_id):
                p_data["money"] += 5000
                p_data["xp"] += 1000
                await check_and_process_levelup(p_data, i)
        BOSS_DATA.update(
            {"is_active": False, "hp": 0, "participants": [], "channel_id": None}
        )
        save_data()


@bot.tree.command(name="usar", description="Usa um item do seu inventário.")
@app_commands.check(check_player_exists)
async def usar(i: Interaction, item_id: str):
    item_id, player_data = item_id.lower(), get_player_data(i.user.id)
    if item_id not in player_data["inventory"] or player_data["inventory"][item_id] < 1:
        await i.response.send_message("Você não possui este item!")
        return
    if item_id == "pocao":
        player_data["hp"] = min(player_data["max_hp"], player_data["hp"] + 50)
        player_data["inventory"]["pocao"] -= 1
        await i.response.send_message(
            f"🧪 Você usou uma poção e recuperou 50 HP! Vida atual: `{player_data['hp']}/{player_data['max_hp']}`."
        )
    elif item_id == "invocador":
        if BOSS_DATA["is_active"]:
            await i.response.send_message("O Colosso já está ativo!")
            return
        player_data["inventory"]["invocador"] -= 1
        BOSS_DATA.update(
            {
                "is_active": True,
                "hp": BOSS_DATA["max_hp"],
                "participants": [str(i.user.id)],
                "channel_id": i.channel.id,
            }
        )
        embed = Embed(
            title=f"👹 O {BOSS_DATA['name']} APARECEU! 👹",
            description=f"Invocado por **{i.user.display_name}**! Usem `/atacar_boss`!",
            color=Color.dark_red(),
        )
        embed.add_field(
            name="Vida do Boss", value=f"`{BOSS_DATA['hp']}/{BOSS_DATA['max_hp']}`"
        ).set_thumbnail(url="https://c.tenor.com/TgVgrdOEIIYAAAAd/tenor.gif")
        await i.response.send_message(embed=embed)
    if player_data["inventory"].get(item_id) == 0:
        del player_data["inventory"][item_id]
    save_data()


@bot.tree.command(
    name="curar",
    description="[Curandeiro] Usa seus poderes para restaurar a vida de um alvo.",
)
@app_commands.check(check_player_exists)
async def curar(i: Interaction, alvo: discord.Member):
    player_data = get_player_data(i.user.id)
    if player_data["class"] != "Curandeiro":
        await i.response.send_message("Apenas Curandeiros podem usar este comando.")
        return
    target_data = get_player_data(alvo.id)
    if not target_data:
        await i.response.send_message(f"{alvo.display_name} não possui uma ficha.")
        return
    now, cooldown_key, last_heal = (
        datetime.now().timestamp(),
        "heal_cooldown",
        player_data["cooldowns"].get("heal_cooldown", 0),
    )
    if now - last_heal < 45:
        await i.response.send_message(f"Sua cura está em cooldown!")
        return
    heal_amount = random.randint(
        int(player_data["special_attack"] * 1.5),
        int(player_data["special_attack"] * 2.5),
    )
    original_hp = target_data["hp"]
    target_data["hp"] = min(target_data["max_hp"], target_data["hp"] + heal_amount)
    healed_for = target_data["hp"] - original_hp
    player_data["cooldowns"][cooldown_key] = now
    embed = Embed(title="✨ Bênção Vital ✨", color=Color.from_rgb(139, 212, 181))
    if i.user.id == alvo.id:
        embed.description = (
            f"Você se concentrou e curou a si mesmo em **{healed_for}** HP."
        )
    else:
        embed.description = (
            f"Você usou seus poderes para curar {alvo.mention} em **{healed_for}** HP."
        )
    embed.set_footer(
        text=f"Vida de {alvo.display_name}: {target_data['hp']}/{target_data['max_hp']}"
    )
    save_data()
    await i.response.send_message(embed=embed)


@bot.tree.command(
    name="transformar",
    description="Usa sua energia para entrar em um estado mais poderoso.",
)
@app_commands.check(check_player_exists)
async def transformar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if player_data["is_transformed"]:
        await i.response.send_message("Você já está transformado!")
        return
    if player_data["energy"] < TRANSFORM_COST:
        await i.response.send_message(f"Energia insuficiente!")
        return
    player_data["is_transformed"] = True
    player_data["energy"] -= TRANSFORM_COST
    player_data["attack"] = int(player_data["base_attack"] * 1.5)
    player_data["special_attack"] = int(player_data["base_special_attack"] * 1.5)
    save_data()
    embed = Embed(
        title=f"🔥 TRANSFORMAÇÃO: {player_data['transform_name']} 🔥",
        description=f"{i.user.display_name} liberou seu poder oculto!",
        color=Color.orange(),
    )
    await i.response.send_message(embed=embed)


@bot.tree.command(
    name="destransformar", description="Retorna à sua forma normal e recupera energia."
)
@app_commands.check(check_player_exists)
async def destransformar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if not player_data["is_transformed"]:
        await i.response.send_message("Você não está transformado.")
        return
    player_data["is_transformed"] = False
    player_data["energy"] = min(MAX_ENERGY, player_data["energy"] + 1)
    player_data["attack"] = player_data["base_attack"]
    player_data["special_attack"] = player_data["base_special_attack"]
    save_data()
    await i.response.send_message(
        "Você retornou à sua forma normal e recuperou `1` de energia."
    )


# Seção 4: Comandos Utilitários
@bot.tree.command(name="help", description="Mostra a wiki interativa do bot OUTLAWS.")
async def help(i: Interaction):
    embed = Embed(
        title="📜 Bem-vindo à Wiki de OUTLAWS",
        description="Use o menu abaixo para navegar pelos tópicos.",
        color=Color.blurple(),
    )
    embed.set_thumbnail(url="https://i.imgur.com/Sce6RIJ.png")
    await i.response.send_message(embed=embed, view=HelpView())


@bot.tree.command(
    name="afk",
    description="Entra no modo AFK. Você não pode ser alvo nem usar comandos.",
)
@app_commands.check(check_player_exists)
async def afk(i: Interaction):
    player_data = get_player_data(i.user.id)
    now, cooldown_key, last_return = (
        datetime.now().timestamp(),
        "afk_cooldown",
        player_data["cooldowns"].get("afk_cooldown", 0),
    )
    if now - last_return < 10800:
        await i.response.send_message("Você não pode ficar AFK ainda.")
        return
    player_data["status"] = "afk"
    save_data()
    await i.response.send_message(
        "🌙 Você entrou em modo AFK. Use `/voltar` para ficar online."
    )


@bot.tree.command(name="voltar", description="Sai do modo AFK e volta a ficar online.")
async def voltar(i: Interaction):
    player_data = get_player_data(i.user.id)
    if not player_data:
        await i.response.send_message("Você não tem uma ficha.")
        return
    if player_data["status"] != "afk":
        await i.response.send_message("Você não está em modo AFK.")
        return
    player_data["status"] = "online"
    player_data["cooldowns"]["afk_cooldown"] = datetime.now().timestamp()
    save_data()
    await i.response.send_message(
        "🟢 Você está online novamente! O cooldown para usar `/afk` outra vez começou."
    )


# --- TAREFAS EM BACKGROUND ---
@tasks.loop(seconds=60)
async def auto_save():
    save_data()


@tasks.loop(hours=1)
async def energy_regeneration():
    for user_id, player_data in player_database.items():
        if player_data.get("energy", 0) < MAX_ENERGY:
            player_data["energy"] += 1


@tasks.loop(seconds=15)
async def boss_attack_loop():
    if not BOSS_DATA["is_active"] or not BOSS_DATA["channel_id"]:
        return
    channel = bot.get_channel(BOSS_DATA["channel_id"])
    if not channel:
        BOSS_DATA["is_active"] = False
        BOSS_DATA["channel_id"] = None
        return
    participants_online = [
        p_id
        for p_id in BOSS_DATA["participants"]
        if (p_data := get_player_data(p_id)) and p_data.get("status") == "online"
    ]
    if not participants_online:
        return
    targets_to_attack_ids = random.sample(
        participants_online, k=min(3, len(participants_online))
    )
    target_names = []
    for target_id in targets_to_attack_ids:
        target_data = get_player_data(target_id)
        damage = random.randint(BOSS_DATA["attack"] // 2, BOSS_DATA["attack"])
        target_data["hp"] -= damage
        target_names.append(f"**{target_data['name']}** (`{damage}` dano)")
        if target_data["hp"] <= 0:
            target_data["hp"] = 0
            target_data["status"] = "dead"
            target_data["deaths"] += 1
    attack_embed = Embed(
        title=f"👹 Fúria do {BOSS_DATA['name']}",
        description=f"O colosso ataca ferozmente! {', '.join(target_names)} foram atingidos!",
        color=Color.dark_orange(),
    )
    await channel.send(embed=attack_embed)
    save_data()


class NotInCity(app_commands.CheckFailure):
    pass


class NotInWilderness(app_commands.CheckFailure):
    pass


def check_player_exists(i: Interaction):
    p = get_player_data(i.user.id)
    return p and p.get("status") != "afk"


def is_in_city(i: Interaction):
    p = get_player_data(i.user.id)
    if not p:  # Ensure player data exists before checking location
        return (
            False  # This will be caught by check_player_exists if it's the only issue
        )
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "cidade":
        return True
    raise NotInCity("Este comando só pode ser usado em uma cidade.")


def is_in_wilderness(i: Interaction):
    p = get_player_data(i.user.id)
    if not p:  # Ensure player data exists before checking location
        return (
            False  # This will be caught by check_player_exists if it's the only issue
        )
    if WORLD_MAP.get(p.get("location"), {}).get("type") == "selvagem":
        return True
    raise NotInWilderness("Este comando só pode ser usado em áreas selvagens.")


@bot.tree.error
async def on_app_command_error(i: Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await i.response.send_message(
            f"Este comando está em cooldown! Tente novamente em **{error.retry_after:.2f}s**."
        )
    elif isinstance(error, NotInCity):  # Prioridade para erros de "não está na cidade"
        await i.response.send_message(
            "Este comando só pode ser usado em uma cidade. Use `/viajar` para ir para um **Abrigo dos Foras-da-Lei**."
        )
    elif isinstance(
        error, NotInWilderness
    ):  # Prioridade para erros de "não está na selva"
        await i.response.send_message(
            "Este comando só pode ser usado em áreas selvagens. Use `/viajar`."
        )
    elif isinstance(
        error, app_commands.CheckFailure
    ):  # Trata outras falhas gerais de verificação
        player_data = get_player_data(i.user.id)
        if player_data and player_data.get("status") == "afk":
            await i.response.send_message(
                "Você não pode usar este comando enquanto estiver AFK."
            )
        else:  # Se a verificação de jogador existir falhou por outro motivo (ex: sem ficha)
            await i.response.send_message(
                "Você ainda não tem uma ficha! Use `/criar_ficha`."
            )
    else:
        print(f"Erro não tratado: {error}")  # Para qualquer outro erro inesperado
        await i.response.send_message("Ocorreu um erro inesperado.")


@bot.event
async def on_message(message: discord.Message):
    # Ignora mensagens do próprio bot para evitar loops infinitos
    if message.author.bot:
        return

    # Ignora mensagens de comandos para evitar XP duplicado ou indesejado
    # (se você tiver comandos baseados em prefixo que não sejam app_commands)
    if message.content.startswith(bot.command_prefix):
        return

    player_id = str(message.author.id)
    player_data = get_player_data(player_id)

    # Verifica se o jogador tem uma ficha e não está AFK
    if not player_data or player_data.get("status") == "afk":
        return

    now = datetime.now().timestamp()
    cooldown_key = "message_xp_cooldown"
    last_message_xp = player_data["cooldowns"].get(cooldown_key, 0)

    # Verifica o cooldown para XP por mensagem
    if now - last_message_xp >= XP_PER_MESSAGE_COOLDOWN_SECONDS:
        xp_gain = 5  # Você pode ajustar a quantidade de XP por mensagem aqui
        player_data["xp"] += xp_gain
        player_data["cooldowns"][cooldown_key] = now
        save_data()

        # Opcional: Enviar uma mensagem discreta ou atualizar o perfil
        # Aumentar XP pode levar a level up, então chamamos a função de level up
        await check_and_process_levelup(
            player_data, message.channel
        )  # Passa o canal para notificar o level up

    # É crucial chamar bot.process_commands(message) para que os comandos do bot continuem funcionando!
    await bot.process_commands(message)


# --- INICIAR O BOT ---
if __name__ == "__main__":
    if TOKEN:
        try:
            bot.run(TOKEN)
        except KeyboardInterrupt:
            print("Desligando...")
            save_data()
    else:
        print("ERRO: O DISCORD_TOKEN não foi encontrado no arquivo .env!")
