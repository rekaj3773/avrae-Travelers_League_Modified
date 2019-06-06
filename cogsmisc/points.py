import asyncio
import shlex
import textwrap
import traceback
import uuid

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

    @commands.command()
    @commands.cooldown(1, 5, BucketType.user)
    async def setRoleEmoji(self, ctx, role, emoji):
        role_in_guild = await self.isRoleInGuild(ctx, role)
        await self.saveEmojiByKeyValue("role",role,emoji)
        # await ctx.send(role + "'s emoji has been set to " + emoji + ".")

    @commands.command()
    @commands.cooldown(1, 5, BucketType.user)
    async def addPoints(self, ctx, name, points):
        int_points = int(points)
        original_point_total = await self.getPointsByKeyValue("name", name)
        new_point_total = original_point_total + int_points
        await self.savePointsByName(name, new_point_total, original_point_total)

    @commands.command(name='addpointsbyrole')
    @commands.cooldown(1, 5, BucketType.user)
    async def addPointsByRole(self, ctx, role, points):
        if self.isGameMaster(ctx):
            int_points = int(points)
            role_in_guild = await self.isRoleInGuild(ctx, role)
            if role_in_guild:
                original_point_total = await self.getPointsByKeyValue("role", role)
                new_point_total = original_point_total + int_points
                await self.savePointsByKeyValue("role", role, new_point_total, original_point_total)

    @commands.cooldown(1, 5, BucketType.user)
    async def subtractPoints(self, ctx, name, points):
        int_points = int(points)
        original_point_total = await self.getPointsByKeyValue("name", name)
        new_point_total = original_point_total - int_points
        await self.savePointsByKeyValue("name", name, new_point_total, original_point_total)

    @commands.command(name='subtractpointsbyrole')
    @commands.cooldown(1, 5, BucketType.user)
    async def subtractPointsByRole(self, ctx, role, points):
        if self.isGameMaster(ctx):
            int_points = int(points)
            role_in_guild = await self.isRoleInGuild(ctx, role)
            if role_in_guild:
                original_point_total = await self.getPointsByKeyValue("role", role)
                new_point_total = original_point_total - int_points
                await self.savePointsByKeyValue("role", role, new_point_total, original_point_total)

    async def getPointsByKeyValue(self, key, value):
        # Todo:Mongo Shenanigans
        points = await self.bot.mdb.points.find_one({key: value})
        if points is None:
            points = 0
        else:
            points = points["points"]
            int(points)
        return points

    async def savePointsByKeyValue(self, key, value, points, original_points):
        # Todo:Mongo Shenanigans
        if original_points is None:
            await self.bot.mdb.points.insert_one({key: value, "points": points})
        else:
            await self.bot.mdb.points.update_one({key: value}, {"$set": {"points": points}}, upsert=True)

    async def saveEmojiByKeyValue(self,key,value,emoji):
        # Todo:Mongo Shenanigans
        await self.bot.mdb.points.update_one({key: value}, {"$set": {"emoji": emoji}}, upsert=True)

    @commands.command(name="showpoints")
    async def showPoints(self, ctx, role):
        point_total = await self.getPointsByKeyValue("role", role)
        renown_str = await self.getPointTotalString(ctx, point_total)
        await ctx.send(role + " has acquired " + renown_str)

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
            string_input = role.name
            print(string_input)
            string_input = string_input.split("-",1)[1]
            try:
                string_input = document["emoji"] + " " + string_input
            except KeyError:
                string_input = "404 Emoji not set" + string_input
            total_string += "\n " + str(count) + ". " + string_input + " " + renown_str
            count = count + 1
        await ctx.send(total_string)

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

    async def getAllPointDocuments(self):
        cursor = self.bot.mdb.points.find({"points": {"$gt": 0}}).sort('points')
        return await cursor.to_list(100)

    async def getPointTotalString(self, ctx, point_total):
        league_icon = get(ctx.guild.emojis, name='League')
        league_icon = league_icon.__str__()
        renown_str = league_icon + " " + str(point_total) + " Renown " + league_icon
        return renown_str

    async def isGameMaster(self,ctx):
        if "Game Masters" in ctx.message.author.roles or "The Dungeon Master" in ctx.message.author.roles:
            return True
        else:
            await ctx.send("You are not authorized to do this")
            return False


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
