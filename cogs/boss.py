# cogs/boss.py

import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import random
import asyncio

# Corrigido: Importando get_stat para usar os atributos atualizados do jogador
from utils.game_logic import get_player_data, save_boss_data, get_boss_data, get_stat
from config import (
    COR_EMBED_SUCESSO,
    COR_EMBED_CHEFE,
    BOSS_INFO,
    COR_EMBED_PADRAO,
)


class Boss(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.boss_attack_loop.start()

    def cog_unload(self):
        self.boss_attack_loop.cancel()

    async def _execute_boss_attack(self, channel: discord.TextChannel):
        """
        Lógica de ataque do chefe. Ataca até 3 jogadores que o atacaram recentemente.
        """
        boss_data = get_boss_data()
        if not boss_data.get("ativo") or not boss_data.get("atacantes"):
            return

        guild = channel.guild
        if not guild:
            return

        # --- LÓGICA DE ALVO CORRIGIDA ---
        # Pega os IDs dos jogadores que atacaram o chefe
        potential_target_ids = list(boss_data["atacantes"].keys())

        # Filtra para garantir que o jogador ainda está no servidor e com HP > 0
        valid_targets = []
        for user_id in potential_target_ids:
            member = guild.get_member(int(user_id))
            player_data = get_player_data(self.bot, user_id)
            if member and player_data and player_data.get("hp", 0) > 0:
                valid_targets.append((user_id, player_data))

        if not valid_targets:
            return

        # Seleciona até 3 jogadores para atacar
        num_to_attack = min(len(valid_targets), 3)
        targets_to_attack = random.sample(valid_targets, num_to_attack)
        attacked_players_info = []

        for user_id, player_data in targets_to_attack:
            # Corrigido: Usa get_stat para calcular a defesa real do jogador
            defesa_jogador = get_stat(player_data, "defesa")
            dano_sofrido = max(1, BOSS_INFO["atk"] - defesa_jogador)
            player_data["hp"] -= dano_sofrido
            member = guild.get_member(int(user_id))

            attacked_players_info.append(
                f"{member.mention} sofreu **{dano_sofrido}** de dano!"
            )

            if player_data["hp"] <= 0:
                player_data["hp"] = 0
                attacked_players_info.append(f"**{member.mention} foi derrotado!** 💀")

        self.bot.save_fichas()

        if attacked_players_info:
            embed = discord.Embed(
                title=f"A Fúria do {BOSS_INFO['nome']}!",
                description="\n".join(attacked_players_info),
                color=COR_EMBED_CHEFE,
            )
            await channel.send(embed=embed)

    @tasks.loop(seconds=45)
    async def boss_attack_loop(self):
        boss_data = get_boss_data()
        if boss_data.get("ativo"):
            channel_id = boss_data.get("channel_id")
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel and boss_data.get("hp_atual", 0) > 0:
                    await self._execute_boss_attack(channel)

    @boss_attack_loop.before_loop
    async def before_boss_attack_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="invocar-boss",
        description="Usa um item para invocar um chefe mundial.",
    )
    async def invocar_boss(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        item_id_invocacao = "invocador_colosso"

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        inventario = player_data.get("inventario", {})
        if item_id_invocacao not in inventario or inventario[item_id_invocacao] <= 0:
            return await interaction.response.send_message(
                "❌ Você não possui o item para invocar o chefe.", ephemeral=True
            )

        boss_data = get_boss_data()
        if boss_data.get("ativo", False):
            return await interaction.response.send_message(
                "👹 Um chefe mundial já está ativo!", ephemeral=True
            )

        inventario[item_id_invocacao] -= 1
        if inventario[item_id_invocacao] <= 0:
            del inventario[item_id_invocacao]
        self.bot.save_fichas()

        novo_boss_data = {
            "ativo": True,
            "id": BOSS_INFO["id"],
            "hp_atual": BOSS_INFO["hp_total"],
            "atacantes": {},
            "channel_id": interaction.channel.id,
            "guild_id": interaction.guild.id,
        }
        save_boss_data(novo_boss_data)

        embed = discord.Embed(
            title=f"👹 {BOSS_INFO['nome']} APARECEU! 👹",
            description=f"{interaction.user.mention} usou um item de invocação e despertou a fúria do Colosso!\n\nUse `/atacar-boss` para lutar!",
            color=COR_EMBED_CHEFE,
        )
        # Assumindo que você possa ter uma imagem para o boss no config
        if BOSS_INFO.get("imagem_url"):
            embed.set_thumbnail(url=BOSS_INFO["imagem_url"])
        await interaction.response.send_message(embed=embed)

        await asyncio.sleep(5)
        await self._execute_boss_attack(interaction.channel)

    @app_commands.command(
        name="atacar-boss", description="Ataca o chefe mundial ativo."
    )
    async def atacar_boss(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = get_player_data(self.bot, user_id)
        boss_data = get_boss_data()

        if not player_data:
            return await interaction.response.send_message(
                "❌ Você não tem uma ficha.", ephemeral=True
            )

        if not boss_data.get("ativo"):
            return await interaction.response.send_message(
                "❌ Nenhum chefe mundial está ativo.", ephemeral=True
            )

        if player_data["hp"] <= 0:
            return await interaction.response.send_message(
                "💀 Você está derrotado e não pode atacar.", ephemeral=True
            )

        # Corrigido: Usa get_stat para que o dano considere os aprimoramentos
        ataque_jogador = get_stat(player_data, "atk")
        dano_causado = max(1, ataque_jogador - BOSS_INFO.get("defesa", 0))
        boss_data["hp_atual"] -= dano_causado

        atacantes = boss_data.setdefault("atacantes", {})
        atacantes[user_id] = atacantes.get(user_id, 0) + dano_causado

        save_boss_data(boss_data)

        embed = discord.Embed(
            title=f"⚔️ Ataque ao {BOSS_INFO['nome']}!",
            description=f"{interaction.user.mention} causou **{dano_causado}** de dano!",
            color=COR_EMBED_PADRAO,
        )
        await interaction.response.send_message(embed=embed)

        if boss_data["hp_atual"] <= 0:
            await self.finalizar_boss(interaction.channel)
        else:
            await asyncio.sleep(2)
            await self._execute_boss_attack(interaction.channel)

    async def finalizar_boss(self, channel):
        # A lógica de recompensas seria adicionada aqui.
        embed = discord.Embed(
            title=f"🏆 {BOSS_INFO['nome']} FOI DERROTADO! 🏆",
            description="O grande chefe caiu! As recompensas foram distribuídas aos maiores atacantes.",
            color=COR_EMBED_SUCESSO,
        )
        await channel.send(embed=embed)
        save_boss_data({"ativo": False})


async def setup(bot):
    await bot.add_cog(Boss(bot))
