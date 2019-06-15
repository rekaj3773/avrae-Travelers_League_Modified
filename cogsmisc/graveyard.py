import asyncio
import shlex
import textwrap
import traceback
import uuid
import re

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, UserInputError
from discord.ext.commands.view import StringView
from discord.utils import get

from cogs5e.funcs import scripting
from cogs5e.funcs.scripting import ScriptingEvaluator
from cogs5e.models.character import Character
from cogs5e.models.errors import AvraeException, EvaluationError, NoCharacter
from utils.functions import auth_and_chan, clean_content, confirm

ALIASER_ROLES = ("server aliaser", "dragonspeaker")


class Points(commands.Cog):
    """Commands to help streamline using the bot."""

    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self):
        if getattr(self.bot, "shard_id", 0) == 0:
            cmds = list(self.bot.all_commands.keys())
            self.bot.rdb.jset('default_commands', cmds)

    async def on_message(self, message):
        if str(message.author.id) in self.bot.get_cog("AdminUtils").muted:
            return
        await self.handle_aliases(message)

    @commands.command(name='setroleemoji')
    @commands.cooldown(1, 5, BucketType.user)
    async def setRoleEmoji(self, ctx, role, emoji):
        role_in_guild = await self.isRoleInGuild(ctx, role)
        await self.saveEmojiByKeyValue("role",role,emoji)
        role = await self.getRoleByMention(ctx, role)
        await ctx.send(role.__str__() + "'s emoji has been set to " + emoji + ".")

    # <editor-fold desc="Point Adjusting">
    @commands.command(name='addpointsbyrole')
    @commands.cooldown(1, 5, BucketType.user)
    async def addPointsByRole(self, ctx, role, points):
        bool = await self.isGameMaster(ctx)
        if bool:
            int_points = int(points)
            role_in_guild = await self.isRoleInGuild(ctx, role)
            if role_in_guild:
                original_point_total = await self.getPointsByKeyValue("role", role)
                new_point_total = original_point_total + int_points
                await self.savePointsByKeyValue("role", role, new_point_total, original_point_total)


    @commands.command(name='subtractpointsbyrole')
    @commands.cooldown(1, 5, BucketType.user)
    async def subtractPointsByRole(self, ctx, role, points):
        bool = await self.isGameMaster(ctx)
        if bool:
            int_points = int(points)
            role_in_guild = await self.isRoleInGuild(ctx, role)
            if role_in_guild:
                original_point_total = await self.getPointsByKeyValue("role", role)
                new_point_total = original_point_total - int_points
                await self.savePointsByKeyValue("role", role, new_point_total, original_point_total)
    # </editor-fold>

    # <editor-fold desc="Leaderboard stuff">
    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx):
        all_documents = await self.getAllPointDocuments()
        total_string = ""
        count = 1
        for document in reversed(all_documents):
            try:
                role = document["role"]
            except KeyError:
                continue
            renown_str = await self.getPointTotalString(ctx, document["points"])
            role = await self.getRoleByMention(ctx, role)
            string_input = role.__str__()
            try:
                string_input = string_input.split("-",1)[1]
            except IndexError:
                string_input = role.__str__();
            try:
                string_input = document["emoji"] + " " + string_input
            except KeyError:
                string_input = "404 Emoji not set, use !setroleemoji to update this for Player-" + string_input
            total_string += "\n " + str(count) + ". " + string_input + " " + renown_str
            count = count + 1
        await ctx.send(total_string)

    async def getPointTotalString(self, ctx, point_total):
        league_icon = get(ctx.guild.emojis, name='League')
        league_icon = league_icon.__str__()
        renown_str = league_icon + " " + str(point_total) + " Renown " + league_icon
        return renown_str
    # </editor-fold>

    # <editor-fold desc="Key Value Methods">
    async def getPointsByKeyValue(self, key, value):
        points = await self.bot.mdb.points.find_one({key: value})
        if points is None:
            points = 0
        else:
            points = points["points"]
            int(points)
        return points

    async def savePointsByKeyValue(self, key, value, points, original_points):
        if original_points is None:
            await self.bot.mdb.points.insert_one({key: value, "points": points})
        else:
            await self.bot.mdb.points.update_one({key: value}, {"$set": {"points": points}}, upsert=True)

    async def saveEmojiByKeyValue(self,key,value,emoji):
        await self.bot.mdb.points.update_one({key: value}, {"$set": {"emoji": emoji}}, upsert=True)
    # </editor-fold>

    # <editor-fold desc="Helper functions">
    async def getAllPointDocuments(self):
        cursor = self.bot.mdb.points.find({"points": {"$gt": 0}}).sort('points')
        return await cursor.to_list(100)

    async def getRoleByMention(self, ctx, mention):
        role = get(ctx.guild.roles, id=int(re.sub('[<>@&]', '', mention)))
        return role
    # </editor-fold>

    # <editor-fold desc="Checking role messages">
    async def isRoleInGuild(self, ctx, role):
        role_in_guild = False
        for ctx_role in ctx.guild.roles:
            # Make the id similar to the role string, could parse the nasty characters out of role but I'm lazy
            if "<@&" + str(ctx_role.id) + ">" == role:
                role_in_guild = True
                if role_in_guild:
                    return role_in_guild
        await ctx.send("Role: " + role + " is not a vaild role in this server. Please input a valid role.")
        return role_in_guild

    async def isGameMaster(self,ctx):
        for role in ctx.message.author.roles:
            if "Game Masters" == role.__str__() or "The Director" in role.__str__():
                return True
        await ctx.send("You are not authorized to do this")
        return False
    # </editor-fold>


def setup(bot):
    bot.add_cog(Points(bot))


class Context:
    """A class to pretend to be ctx."""

    def __init__(self, bot, message):
        self.bot = bot
        self.message = message

    @property
    def author(self):
        return self.message.author

    @property
    def guild(self):
        return self.message.guild

    @property
    def channel(self):
        return self.message.channel
