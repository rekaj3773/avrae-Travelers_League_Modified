import asyncio
import shlex
import textwrap
import traceback
import uuid

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, UserInputError
from discord.ext.commands.view import StringView

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
    @commands.cooldown(1, 20, BucketType.user)
    async def addPoints(self, ctx, name, points):
        int_points = int(points)
        get_point_total = self.getPointsByName(name)
        get_point_total += int_points
        await self.savePointsByName(name, get_point_total)

    async def getPointsByName(self, name):
        # Todo:Mongo Shenanigans
        points = await self.bot.mdb.points.find({"name": name})
        if points is None:
            points = 0
        else:
            int(points)
        return points

    async def savePointsByName(self, name, points):
        # Todo:Mongo Shenanigans
        await self.bot.mdb.points.update_one({"name": name},{"$set": {"points": points}})


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
