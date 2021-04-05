import ast
import asyncio
import os
import discord
import psycopg2
import pytz
import urllib.parse as urlparse

from datetime import datetime as dt
from discord.ext import commands, tasks
from chl_scraper import scrape

LOCAL_TZ = 'America/Vancouver'
ENV = 'prod'

if ENV == 'dev':
    con = psycopg2.connect(dbname='chl-fantasy',
                           user='Brad',
                           password=os.getenv("CHL_DB_TOKEN"))
    testing = True
else:
    url = urlparse.urlparse(os.environ['DATABASE_URL'])
    dbname = url.path[1:]
    user = url.username
    password = url.password
    host = url.hostname
    port = url.port

    con = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
                )
    testing = False


bot = commands.Bot(
    command_prefix="!",
    description="Fantasy league management bot",
    help_command=commands.DefaultHelpCommand(no_category='Commands'))
token = os.getenv("DISCORD_BOT_TOKEN")


def update(testing=False):
    cur = con.cursor()
    data, data_g = scrape(testing=testing)
    # print(data.items())
    cur.execute("insert into players (TIME, PLAYER_DATA) values (%s, %s)",
                (int(pytz.timezone(LOCAL_TZ).localize(
                    dt.now()).timestamp()), repr(data)))
    cur.execute("insert into goalies (TIME, PLAYER_DATA) values (%s, %s)",
                (int(pytz.timezone(LOCAL_TZ).localize(
                    dt.now()).timestamp()), repr(data_g)))

    if testing:
        time = pytz.timezone(LOCAL_TZ).localize(dt.now()).hour + 1
        day = pytz.timezone(LOCAL_TZ).localize(dt.now()).weekday()
    else:
        time = 1
        day = 6
    
    cur.execute("SELECT count(*) FROM (SELECT 1 FROM weekly LIMIT 1) AS t;")
    weekly_empty = not cur.fetchall()[0][0]
    cur.execute("SELECT * from weekly")

    if (pytz.timezone(LOCAL_TZ).localize(
            dt.now()).weekday() == day and pytz.timezone(LOCAL_TZ).localize(
                dt.now()).hour < time) or weekly_empty:
        cur.execute(
            "insert into weekly (TIME, PLAYER_DATA) values (%s, %s)",
            (int(pytz.timezone(LOCAL_TZ).localize(
                dt.now()).timestamp()), repr(data)))

    cur.execute("SELECT count(*) FROM (SELECT 1 FROM weekly_goalie LIMIT 1) AS t;")
    weekly_empty_g = not cur.fetchall()[0][0]
    cur.execute("SELECT * from weekly_goalie")

    if (pytz.timezone(LOCAL_TZ).localize(
            dt.now()).weekday() == day and pytz.timezone(LOCAL_TZ).localize(
                dt.now()).hour < time) or weekly_empty_g:
        cur.execute(
            "insert into weekly_goalie (TIME, PLAYER_DATA) values (%s, %s)",
            (int(pytz.timezone(LOCAL_TZ).localize(
                dt.now()).timestamp()), repr(data_g)))

    cur.execute("select time, player_data from players")
    rows = cur.fetchall()
    cur.execute("select time, player_data from weekly")
    weekrows = cur.fetchall()

    try:
        newest_player_stats = ast.literal_eval(rows[-1][1])
        newest_player_week = ast.literal_eval(weekrows[-1][1])
        # print(newest_stats, newest_week, sep="\n")
    except Exception:
        print("No data stored yet")


    cur.execute("select time, player_data from goalies")
    rows = cur.fetchall()
    cur.execute("select time, player_data from weekly_goalie")
    weekrows = cur.fetchall()

    try:
        newest_player_stats_g = ast.literal_eval(rows[-1][1])
        newest_player_week_g = ast.literal_eval(weekrows[-1][1])
        # print(newest_stats, newest_week, sep="\n")
    except Exception:
        print("No data stored yet")

    con.commit()
    cur.close()

    # return newest_stats, newest_stats_g
    return newest_player_stats, newest_player_stats_g


@tasks.loop(minutes=60)
# @tasks.loop(seconds=30)
async def update_scoring():
    stats, stats_g = update(testing=False)
    channel = bot.get_channel(824876222717886487)

    # msg = ""
    
    # for key, value in list(stats.items())[:5]:
    #     msg += f"{value['name']} -- {value['fpts']}fpts\n"

    # await channel.send(msg)


@bot.event
async def on_ready():
    # await bot.change_presence(status = discord.Status.idle, activity=discord.Game("Listening to !help"))
    print("I am online")
    update_scoring.start()


@bot.command(pass_context=True,
             name="rules",
             brief="(league rules)",
             help="Displays software-related limitations and scoring rules")
async def rules(ctx):
    await ctx.send(f"Weekly head-2-head matchup system. Matchups are not yet implemented, so you will want to log them yourself (whoever the commisioner is).\n\nThe way the backend works, trades and free agent pickups should only process once a week on Sunday night or Monday morning (between games).\n\nScoring is as follows:\ngoals -- 5pts | assists -- 3pts | saves -- 0.5pts | goals -- -3pts | shutout -- 5pts | win -- 3pts")


@bot.command(pass_context=True,
             name="addteam",
             brief="[new team]",
             help="Will create a new (empty) team in the league")
async def addteam(ctx, arg):
    if type(arg) == str:
        arg = arg.title()

        if ctx.message.author.guild_permissions.administrator:
            cur = con.cursor()
            cur.execute("select team_name from fantasy where team_name = %s",
                        (arg, ))
            num = len(cur.fetchall())

            if not num:
                cur.execute(
                    "insert into FANTASY (TEAM_NAME, PLAYERS) values (%s, %s)",
                    (arg, []))
                con.commit()
                await ctx.send(f"Team {arg} added!")
            else:
                await ctx.send(f"Team {arg} already exists!")
            cur.close()

        else:
            await ctx.send(f"Only admins have access to this command")


@bot.command(pass_context=True,
             brief="[team to remove]",
             name="removeteam",
             help="Will remove a team from the league")
# @commands.is_owner()
async def removeteam(ctx, arg):
    if type(arg) == str:
        arg = arg.title()

        if ctx.message.author.guild_permissions.administrator:
            cur = con.cursor()
            cur.execute("select team_name from fantasy where team_name = %s",
                        (arg, ))

            num = len(cur.fetchall())

            if num > 0:
                await ctx.send(
                    f"Are you sure you want to remove {arg}? Reply 'y' to confirm or 'n' to cancel."
                )
                msg = await bot.wait_for("message",
                                         check=lambda m: m.author == ctx.author
                                         and m.channel.id == ctx.channel.id)

                if msg.content.lower() == 'y':
                    cur.execute("delete from fantasy where team_name = %s",
                                (arg, ))
                    con.commit()
                    await ctx.send(f"Team {arg} removed!")
                else:
                    await ctx.send(f"Cancelled")
            else:
                await ctx.send(f"Team {arg} doesn't exist!")
            cur.close()
        else:
            await ctx.send(f"Only admins have access to this command")


@bot.command(pass_context=True,
             brief="[team] [player]",
             name="addplayer",
             help="Adds player (<arg1>) to team (<arg2>)")
# @commands.is_owner()
async def addplayer(ctx, arg1, arg2):
    try:
        arg1 = arg1.title()
        arg2 = arg2.title()

        if ctx.message.author.guild_permissions.administrator:
            cur = con.cursor()
            cur.execute("select team_name, players from fantasy")
            fetched = cur.fetchall()
            all_players = sum(
                [list(ast.literal_eval(ii[-1])) for ii in fetched], [])
            team_indices = [
                fetched.index(ii) for ii in fetched if arg1 in ii[0]
            ]
            curr_players = list(ast.literal_eval(fetched[team_indices[0]][-1]))

            if team_indices:
                cur.execute(
                    "select player_data from players order by time desc limit 1"
                )
                most_recent = ast.literal_eval(cur.fetchall()[0][0])
                try:
                    arg2 = int(arg2)
                except ValueError:
                    pass

                if type(arg2) == int:
                    try:
                        if arg2 not in all_players:
                            await ctx.send(
                                    f"Would you like to add {most_recent[arg2]['name']} ID:{arg2} ({most_recent[arg2]['goals']}g-{most_recent[arg2]['assists']}a-{most_recent[arg2]['fpts']}fpts) to {arg1}? Reply 'y' to confirm or 'n' to cancel."
                            )
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if msg.content.lower() == 'y':
                                curr_players.append(arg2)
                                cur.execute(
                                    "update fantasy set players = %s where team_name = %s",
                                    (curr_players, arg1))
                                con.commit()
                                await ctx.send(
                                    f"{most_recent[arg2]['name']} added to team {arg1}"
                                )
                            else:
                                await ctx.send(f"Cancelled")
                        else:
                            team_on = [
                                ii[0].strip() for ii in fetched

                                if arg2 in list(ast.literal_eval(ii[-1]))
                            ][0]
                            await ctx.send(
                                f"{most_recent[arg2]['name']} is already on team {team_on}"
                            )
                    except KeyError:
                        await ctx.send(
                            f"Incorrect player ID, that player does not exist")
                else:
                    id_list = list(most_recent.keys())
                    val_list = list(most_recent.values())
                    indices = [
                        val_list.index(ii) for ii in val_list

                        if arg2 in ii['name']
                    ]

                    if indices:
                        if len(indices) == 1:
                            pid = id_list[indices[0]]

                            if pid not in all_players:
                                await ctx.send(
                                        f"Would you like to add {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['goals']}g-{most_recent[pid]['assists']}a-{most_recent[pid]['fpts']}fpts) to {arg1}? Reply 'y' to confirm or 'n' to cancel."
                                )
                                msg = await bot.wait_for(
                                    "message",
                                    check=lambda m: m.author == ctx.author and
                                    m.channel.id == ctx.channel.id)

                                if msg.content.lower() == 'y':
                                    curr_players.append(pid)
                                    cur.execute(
                                        "update fantasy set players = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[pid]['name']} added to team {arg1}"
                                    )
                                else:
                                    await ctx.send(f"Cancelled")
                            else:
                                team_on = [
                                    ii[0].strip() for ii in fetched

                                    if pid in list(ast.literal_eval(ii[-1]))
                                ][0]
                                await ctx.send(
                                    f"{most_recent[pid]['name']} is already on team {team_on}"
                                )
                        else:
                            msg = f"Would you like to add one of these players to team {arg1}? If yes, reply with the number corresponding the player you'd like. If no, reply with 'n'.\n"

                            for select, idx in enumerate(indices):
                                pid = id_list[idx]
                                msg += f"{select+1}: {most_recent[pid]['name']} ID{pid} ({most_recent[pid]['goals']}g-{most_recent[pid]['assists']}a-{most_recent[pid]['fpts']}fpts)\n"
                            await ctx.send(msg)
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if int(msg.content) in list(
                                    range(1,
                                          len(indices) + 1)):

                                if not id_list[indices[int(msg.content) -
                                                       1]] in all_players:
                                    curr_players.append(
                                        id_list[indices[int(msg.content) - 1]])
                                    cur.execute(
                                        "update fantasy set players = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} added to team {arg1}"
                                    )
                                else:
                                    team_on = [
                                        ii[0].strip() for ii in fetched

                                        if id_list[indices[int(msg.content) -
                                                           1]] in
                                        list(ast.literal_eval(ii[-1]))
                                    ][0]
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} is already on team {team_on}"
                                    )
                            else:
                                await ctx.send(f"Cancelled")
                    else:
                        await ctx.send(
                                f"Error. Possible player {arg2} doesn't exist"
                                )
            else:
                await ctx.send(
                    f"Error. Possible team {arg1} doesn't exist"
                )
            cur.close()
        else:
            await ctx.send(f"Only admins have access to this command")
    except IndexError:
        await ctx.send(
            f"Error. Possible team {arg1} or player {arg2} doesn't exist")


@bot.command(pass_context=True,
             brief="[team] [goalie]",
             name="addgoalie",
             help="Adds goalie (<arg1>) to team (<arg2>)")
# @commands.is_owner()
async def addgoalie(ctx, arg1, arg2):
    try:
        arg1 = arg1.title()
        arg2 = arg2.title()

        if ctx.message.author.guild_permissions.administrator:
            cur = con.cursor()
            cur.execute("select team_name, goalies from fantasy")
            fetched = cur.fetchall()
            all_players = sum(
                [list(ast.literal_eval(ii[-1])) for ii in fetched], [])
            team_indices = [
                fetched.index(ii) for ii in fetched if arg1 in ii[0]
            ]
            curr_players = list(ast.literal_eval(fetched[team_indices[0]][-1]))

            if team_indices:
                cur.execute(
                    "select player_data from goalies order by time desc limit 1"
                )
                most_recent = ast.literal_eval(cur.fetchall()[0][0])
                try:
                    arg2 = int(arg2)
                except ValueError:
                    pass

                if type(arg2) == int:
                    try:
                        if arg2 not in all_players:
                            await ctx.send(
                                    f"Would you like to add {most_recent[arg2]['name']} ID:{arg2} ({most_recent[arg2]['games']}g-{most_recent[arg2]['saves']}s-{most_recent[arg2]['fpts']}fpts) to {arg1}? Reply 'y' to confirm or 'n' to cancel."
                            )
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if msg.content.lower() == 'y':
                                curr_players.append(arg2)
                                cur.execute(
                                    "update fantasy set goalies = %s where team_name = %s",
                                    (curr_players, arg1))
                                con.commit()
                                await ctx.send(
                                    f"{most_recent[arg2]['name']} added to team {arg1}"
                                )
                            else:
                                await ctx.send(f"Cancelled")
                        else:
                            team_on = [
                                ii[0].strip() for ii in fetched

                                if arg2 in list(ast.literal_eval(ii[-1]))
                            ][0]
                            await ctx.send(
                                f"{most_recent[arg2]['name']} is already on team {team_on}"
                            )
                    except KeyError:
                        await ctx.send(
                            f"Incorrect player ID, that goalie does not exist")
                else:
                    id_list = list(most_recent.keys())
                    val_list = list(most_recent.values())
                    indices = [
                        val_list.index(ii) for ii in val_list

                        if arg2 in ii['name']
                    ]

                    if indices:
                        if len(indices) == 1:
                            pid = id_list[indices[0]]

                            if pid not in all_players:
                                await ctx.send(
                                        f"Would you like to add {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['games']}g-{most_recent[pid]['saves']}g-{most_recent[pid]['fpts']}fpts) to {arg1}? Reply 'y' to confirm or 'n' to cancel."
                                )
                                msg = await bot.wait_for(
                                    "message",
                                    check=lambda m: m.author == ctx.author and
                                    m.channel.id == ctx.channel.id)

                                if msg.content.lower() == 'y':
                                    curr_players.append(pid)
                                    cur.execute(
                                        "update fantasy set goalies = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[pid]['name']} added to team {arg1}"
                                    )
                                else:
                                    await ctx.send(f"Cancelled")
                            else:
                                team_on = [
                                    ii[0].strip() for ii in fetched

                                    if pid in list(ast.literal_eval(ii[-1]))
                                ][0]
                                await ctx.send(
                                    f"{most_recent[pid]['name']} is already on team {team_on}"
                                )
                        else:
                            msg = f"Would you like to add one of these goalies to team {arg1}? If yes, reply with the number corresponding the player you'd like. If no, reply with 'n'.\n"

                            for select, idx in enumerate(indices):
                                pid = id_list[idx]
                                msg += f"{select+1}: {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['games']}g-{most_recent[pid]['saves']}s-{most_recent[pid]['fpts']}fpts)\n"
                            await ctx.send(msg)
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if int(msg.content) in list(
                                    range(1,
                                          len(indices) + 1)):

                                if not id_list[indices[int(msg.content) -
                                                       1]] in all_players:
                                    curr_players.append(
                                        id_list[indices[int(msg.content) - 1]])
                                    cur.execute(
                                        "update fantasy set goalies = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} added to team {arg1}"
                                    )
                                else:
                                    team_on = [
                                        ii[0].strip() for ii in fetched

                                        if id_list[indices[int(msg.content) -
                                                           1]] in
                                        list(ast.literal_eval(ii[-1]))
                                    ][0]
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} is already on team {team_on}"
                                    )
                            else:
                                await ctx.send(f"Cancelled")
                    else:
                        await ctx.send(
                                f"Error. Possible goalie {arg2} doesn't exist"
                                )
            else:
                await ctx.send(
                    f"Error. Possible team {arg1} doesn't exist"
                )
            cur.close()
        else:
            await ctx.send(f"Only admins have access to this command")
    except IndexError:
        await ctx.send(
            f"Error. Possible team {arg1} or player {arg2} doesn't exist")

@bot.command(pass_context=True,
             brief="[team] [player]",
             name="removegoalie",
             help="Removes goalie (<arg1>) from team (<arg2>)")
# @commands.is_owner()
async def removegoalie(ctx, arg1, arg2):
    try:
        arg1 = arg1.title()
        arg2 = arg2.title()

        if ctx.message.author.guild_permissions.administrator:
            cur = con.cursor()
            cur.execute("select team_name, goalies from fantasy")
            fetched = cur.fetchall()
            all_players = sum(
                [list(ast.literal_eval(ii[-1])) for ii in fetched], [])
            team_indices = [
                fetched.index(ii) for ii in fetched if arg1 in ii[0]
            ]
            curr_players = list(ast.literal_eval(fetched[team_indices[0]][-1]))

            if team_indices:
                cur.execute(
                    "select player_data from goalies order by time desc limit 1"
                )
                most_recent = ast.literal_eval(cur.fetchall()[0][0])
                try:
                    arg2 = int(arg2)
                except ValueError:
                    pass

                if type(arg2) == int:
                    try:
                        if arg2 in curr_players:
                            await ctx.send(
                                    f"Would you like to remove {most_recent[arg2]['name']} ID:{arg2} ({most_recent[arg2]['games']}g-{most_recent[arg2]['saves']}s-{most_recent[arg2]['fpts']}fpts) from {arg1}? Reply 'y' to confirm or 'n' to cancel."
                            )
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if msg.content.lower() == 'y':
                                curr_players.remove(arg2)
                                cur.execute(
                                    "update fantasy set goalies = %s where team_name = %s",
                                    (curr_players, arg1))
                                con.commit()
                                await ctx.send(
                                    f"{most_recent[arg2]['name']} removed from team {arg1}"
                                )
                            else:
                                await ctx.send(f"Cancelled")
                        else:
                            # team_on = [
                            #     ii[0].strip() for ii in fetched
                            #     if arg2 in list(ast.literal_eval(ii[-1]))
                            # ][0]
                            await ctx.send(
                                f"{most_recent[arg2]['name']} is not on team {arg1}"
                            )
                    except KeyError:
                        await ctx.send(
                            f"Incorrect player ID, that goalie does not exist")
                else:
                    id_list = list(most_recent.keys())
                    val_list = list(most_recent.values())
                    indices = [
                        val_list.index(ii) for ii in val_list

                        if arg2 in ii['name']
                    ]

                    if indices:
                        if len(indices) == 1:
                            pid = id_list[indices[0]]

                            if pid in curr_players:
                                await ctx.send(
                                        f"Would you like to remove {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['games']}g-{most_recent[pid]['saves']}s-{most_recent[pid]['fpts']}fpts) from {arg1}? Reply 'y' to confirm or 'n' to cancel."
                                )
                                msg = await bot.wait_for(
                                    "message",
                                    check=lambda m: m.author == ctx.author and
                                    m.channel.id == ctx.channel.id)

                                if msg.content.lower() == 'y':
                                    curr_players.remove(pid)
                                    cur.execute(
                                        "update fantasy set goalies = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[pid]['name']} removed from team {arg1}"
                                    )
                                else:
                                    await ctx.send(f"Cancelled")
                            else:
                                # team_on = [
                                #     ii[0].strip() for ii in fetched
                                #     if pid in list(ast.literal_eval(ii[-1]))
                                # ][0]
                                await ctx.send(
                                    f"{most_recent[pid]['name']} is not on team {arg1}"
                                )
                        else:
                            msg = f"Would you like to remove one of these goalies to team {arg1}? If yes, reply with the number corresponding the player you'd like. If no, reply with 'n'.\n"

                            for select, idx in enumerate(indices):
                                pid = id_list[idx]
                                msg += f"{select+1}: {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['games']}g-{most_recent[pid]['saves']}s-{most_recent[pid]['fpts']}fpts)\n"
                            await ctx.send(msg)
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if int(msg.content) in list(
                                    range(1,
                                          len(indices) + 1)):

                                if id_list[indices[int(msg.content) -
                                                       1]] in curr_players:
                                    curr_players.remove(
                                        id_list[indices[int(msg.content) - 1]])
                                    cur.execute(
                                        "update fantasy set goalies = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} removed from team {arg1}"
                                    )
                                else:
                                    # team_on = [
                                    #     ii[0].strip() for ii in fetched
                                    #     if id_list[indices[int(msg.content) -
                                    #                        1]] in
                                    #     list(ast.literal_eval(ii[-1]))
                                    # ][0]
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} is not on team {arg1}"
                                    )
                            else:
                                await ctx.send(f"Cancelled")
                    else:
                        await ctx.send(
                                f"Error. Possible goalie {arg2} doesn't exist"
                                )
            else:
                await ctx.send(
                    f"Error. Possible team {arg1} doesn't exist"
                )
            cur.close()
        else:
            await ctx.send(f"Only admins have access to this command")
    except IndexError:
        await ctx.send(
            f"Error. Possible team {arg1} or player {arg2} doesn't exist")

@bot.command(pass_context=True,
             brief="[team] [player]",
             name="removeplayer",
             help="Removes player (<arg1>) from team (<arg2>)")
# @commands.is_owner()
async def removeplayer(ctx, arg1, arg2):
    try:
        arg1 = arg1.title()
        arg2 = arg2.title()

        if ctx.message.author.guild_permissions.administrator:
            cur = con.cursor()
            cur.execute("select team_name, players from fantasy")
            fetched = cur.fetchall()
            all_players = sum(
                [list(ast.literal_eval(ii[-1])) for ii in fetched], [])
            team_indices = [
                fetched.index(ii) for ii in fetched if arg1 in ii[0]
            ]
            curr_players = list(ast.literal_eval(fetched[team_indices[0]][-1]))

            if team_indices:
                cur.execute(
                    "select player_data from players order by time desc limit 1"
                )
                most_recent = ast.literal_eval(cur.fetchall()[0][0])
                try:
                    arg2 = int(arg2)
                except ValueError:
                    pass

                if type(arg2) == int:
                    try:
                        if arg2 in curr_players:
                            await ctx.send(
                                    f"Would you like to remove {most_recent[arg2]['name']} ID:{arg2} ({most_recent[arg2]['goals']}g-{most_recent[arg2]['assists']}a-{most_recent[arg2]['fpts']}fpts) from {arg1}? Reply 'y' to confirm or 'n' to cancel."
                            )
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if msg.content.lower() == 'y':
                                curr_players.remove(arg2)
                                cur.execute(
                                    "update fantasy set players = %s where team_name = %s",
                                    (curr_players, arg1))
                                con.commit()
                                await ctx.send(
                                    f"{most_recent[arg2]['name']} removed from team {arg1}"
                                )
                            else:
                                await ctx.send(f"Cancelled")
                        else:
                            # team_on = [
                            #     ii[0].strip() for ii in fetched
                            #     if arg2 in list(ast.literal_eval(ii[-1]))
                            # ][0]
                            await ctx.send(
                                f"{most_recent[arg2]['name']} is not on team {arg1}"
                            )
                    except KeyError:
                        await ctx.send(
                            f"Incorrect player ID, that player does not exist")
                else:
                    id_list = list(most_recent.keys())
                    val_list = list(most_recent.values())
                    indices = [
                        val_list.index(ii) for ii in val_list

                        if arg2 in ii['name']
                    ]

                    if indices:
                        if len(indices) == 1:
                            pid = id_list[indices[0]]

                            if pid in curr_players:
                                await ctx.send(
                                        f"Would you like to remove {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['goals']}g-{most_recent[pid]['assists']}a-{most_recent[pid]['fpts']}fpts) from {arg1}? Reply 'y' to confirm or 'n' to cancel."
                                )
                                msg = await bot.wait_for(
                                    "message",
                                    check=lambda m: m.author == ctx.author and
                                    m.channel.id == ctx.channel.id)

                                if msg.content.lower() == 'y':
                                    curr_players.remove(pid)
                                    cur.execute(
                                        "update fantasy set players = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[pid]['name']} removed from team {arg1}"
                                    )
                                else:
                                    await ctx.send(f"Cancelled")
                            else:
                                # team_on = [
                                #     ii[0].strip() for ii in fetched
                                #     if pid in list(ast.literal_eval(ii[-1]))
                                # ][0]
                                await ctx.send(
                                    f"{most_recent[pid]['name']} is not on team {arg1}"
                                )
                        else:
                            msg = f"Would you like to remove one of these players to team {arg1}? If yes, reply with the number corresponding the player you'd like. If no, reply with 'n'.\n"

                            for select, idx in enumerate(indices):
                                pid = id_list[idx]
                                msg += f"{select+1}: {most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['goals']}a-{most_recent[pid]['assists']}a-{most_recent[pid]['fpts']}fpts)\n"
                            await ctx.send(msg)
                            msg = await bot.wait_for(
                                "message",
                                check=lambda m: m.author == ctx.author and m.
                                channel.id == ctx.channel.id)

                            if int(msg.content) in list(
                                    range(1,
                                          len(indices) + 1)):

                                if id_list[indices[int(msg.content) -
                                                       1]] in curr_players:
                                    curr_players.remove(
                                        id_list[indices[int(msg.content) - 1]])
                                    cur.execute(
                                        "update fantasy set players = %s where team_name = %s",
                                        (curr_players, arg1))
                                    con.commit()
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} removed from team {arg1}"
                                    )
                                else:
                                    # team_on = [
                                    #     ii[0].strip() for ii in fetched
                                    #     if id_list[indices[int(msg.content) -
                                    #                        1]] in
                                    #     list(ast.literal_eval(ii[-1]))
                                    # ][0]
                                    await ctx.send(
                                        f"{most_recent[id_list[indices[int(msg.content)-1]]]['name']} is not on team {arg1}"
                                    )
                            else:
                                await ctx.send(f"Cancelled")
                    else:
                        await ctx.send(
                                f"Error. Possible player {arg2} doesn't exist"
                                )
            else:
                await ctx.send(
                    f"Error. Possible team {arg1} doesn't exist"
                )
            cur.close()
        else:
            await ctx.send(f"Only admins have access to this command")
    except IndexError:
        await ctx.send(
            f"Error. Possible team {arg1} or player {arg2} doesn't exist")

@bot.command(pass_context=True,
             brief="[player]",
             name="player",
             help="Returns fantasy points for chosen player <arg>")
async def player(ctx, arg):
    try:
        arg = arg.title()
        cur = con.cursor()
        cur.execute(
            "select player_data from players order by time desc limit 1"
        )
        fetched = cur.fetchall()
        most_recent = ast.literal_eval(fetched[0][0])
        try:
            arg = int(arg)
        except ValueError:
            pass

        all_players = sum(
            [list(ast.literal_eval(ii[0])) for ii in fetched], [])

        if type(arg) == int:
            if arg in all_players:
                await ctx.send(
                        f"{most_recent[arg]['name']} ID:{arg} ({most_recent[arg]['goals']}g-{most_recent[arg]['assists']}a-{most_recent[arg]['fpts']}fpts)"
                )
            else:
                await ctx.send(
                    f"Incorrect player ID, that player does not exist")
        else:
            id_list = list(most_recent.keys())
            val_list = list(most_recent.values())
            indices = [
                val_list.index(ii) for ii in val_list

                if arg in ii['name']
            ]

            if indices:
                if len(indices) == 1:
                    pid = id_list[indices[0]]

                    if pid in all_players:
                        await ctx.send(
                                f"{most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['goals']}g-{most_recent[pid]['assists']}a-{most_recent[pid]['fpts']}fpts)"
                        )
                    else:
                        await ctx.send(
                            f"Incorrect player ID, that player does not exist")
                else:
                    msg = ""

                    for select, idx in enumerate(indices):
                        pid = id_list[idx]
                        msg += f"{most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['goals']}g-{most_recent[pid]['assists']}a-{most_recent[pid]['fpts']}fpts)\n"
                    await ctx.send(msg)
            else:
                await ctx.send(
                    f"Error. Possible player {arg} doesn't exist"
                )
            cur.close()

    except TypeError:
        await ctx.send(f"Error with input")

@bot.command(pass_context=True,
             brief="[goalie]",
             name="goalie",
             help="Returns fantasy points for chosen goalie <arg>")
async def goalie(ctx, arg):
    try:
        arg = arg.title()
        cur = con.cursor()
        cur.execute(
            "select player_data from goalies order by time desc limit 1"
        )
        fetched = cur.fetchall()
        most_recent = ast.literal_eval(fetched[0][0])
        try:
            arg = int(arg)
        except ValueError:
            pass

        all_players = sum(
            [list(ast.literal_eval(ii[0])) for ii in fetched], [])

        if type(arg) == int:
            if arg in all_players:
                await ctx.send(
                        f"{most_recent[arg]['name']} ID:{arg} ({most_recent[arg]['games']}g-{most_recent[arg]['saves']}s-{most_recent[arg]['fpts']}fpts)"
                )
            else:
                await ctx.send(
                    f"Incorrect player ID, that player does not exist")
        else:
            id_list = list(most_recent.keys())
            val_list = list(most_recent.values())
            indices = [
                val_list.index(ii) for ii in val_list

                if arg in ii['name']
            ]

            if indices:
                if len(indices) == 1:
                    pid = id_list[indices[0]]

                    if pid in all_players:
                        await ctx.send(
                                f"{most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['games']}g-{most_recent[pid]['saves']}a-{most_recent[pid]['fpts']}fpts)"
                        )
                    else:
                        await ctx.send(
                            f"Incorrect player ID, that player does not exist")
                else:
                    msg = ""

                    for select, idx in enumerate(indices):
                        pid = id_list[idx]
                        msg += f"{most_recent[pid]['name']} ID:{pid} ({most_recent[pid]['games']}g-{most_recent[pid]['saves']}s-{most_recent[pid]['fpts']}fpts)\n"
                    await ctx.send(msg)
            else:
                await ctx.send(
                    f"Error. Possible player {arg} doesn't exist"
                )
            cur.close()

    except TypeError:
        await ctx.send(f"Error with input")

@bot.command(pass_context=True,
             brief="(all players)",
             name="players",
             help="Displays all players (goals-assists-fantasy points)")
async def players(ctx):
    cur = con.cursor()
    cur.execute("select time, player_data from players")
    rows = cur.fetchall()

    try:
        stats = ast.literal_eval(rows[-1][1])
        # stats_g = ast.literal_eval(rows_g[-1][1])
        # print(newest_stats, newest_week, sep="\n")
    except Exception:
        print("No data stored yet")

    con.commit()
    cur.close()
    # channel = bot.get_channel(824876222717886487)
   
    stats_list = list(stats.items())
    stats_list.sort(key=lambda x: x[-1]['fpts'], reverse=True)
    n = 50
    for idx, _ in enumerate(stats_list):
        msg = ""
        if idx % n == 0 and stats_list[idx][1]['fpts'] > 0:
            if idx+n+1 > len(stats_list):
                end = len(stats_list)
            else:
                end = idx+n+1
            msg += f"TOP {idx+1}-{end}\n"
            for key, value in stats_list[idx:idx+n]:

                msg += f"{value['name']} ID:{key} ({value['goals']}g-{value['assists']}a-{value['fpts']}fpts)\n"

            await ctx.send(msg)

@bot.command(pass_context=True,
             brief="(all goalies)",
             name="goalies",
             help="Displays all goalies (games-saves-fantasy points)")
async def goalies(ctx):
    cur = con.cursor()
    cur.execute("select time, player_data from goalies")
    rows = cur.fetchall()

    try:
        stats = ast.literal_eval(rows[-1][1])
        # stats_g = ast.literal_eval(rows_g[-1][1])
        # print(newest_stats, newest_week, sep="\n")
    except Exception:
        print("No data stored yet")

    con.commit()
    cur.close()
    # channel = bot.get_channel(824876222717886487)
   
    stats_list = list(stats.items())
    stats_list.sort(key=lambda x: x[-1]['fpts'], reverse=True)
    n = 50
    for idx, _ in enumerate(stats_list):
        msg = ""
        if idx % n == 0 and stats_list[idx][1]['fpts'] > 0:
            if idx+n+1 > len(stats_list):
                end = len(stats_list)
            else:
                end = idx+n+1
            msg += f"TOP {idx+1}-{end}\n"
            for key, value in stats_list[idx:idx+n]:

                msg += f"{value['name']} ID:{key} ({value['games']}g-{value['saves']}s-{value['fpts']}fpts)\n"

            await ctx.send(msg)

@bot.command(pass_context=True,
             brief="[team]",
             name="team",
             help="Displays team (<arg1>)")
async def team(ctx, arg):
    arg = arg.title()
    cur = con.cursor()
    cur.execute("select team_name, players, goalies from fantasy where team_name = %s",
                (arg, ))
    vals = cur.fetchall() 
    cur.execute(
        "select player_data from players order by time desc limit 1"
    )
    most_recent = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from goalies order by time desc limit 1"
    )
    most_recent_g = ast.literal_eval(cur.fetchall()[0][0])
    if vals:
        msg = ""

        for val in vals:
            msg += f"========{val[0].strip()}========\n"
            
            msg += "========skaters========\n"
            if val[1]:
                for player in list(ast.literal_eval(val[1])):
                    msg += f"{most_recent[player]['name']} ({most_recent[player]['goals']}g-{most_recent[player]['assists']}a-{most_recent[player]['fpts']}fpts)\n"
            msg += "========goalies========\n"
            if val[2]:
                for player in list(ast.literal_eval(val[2])):
                    msg += f"{most_recent_g[player]['name']} ({most_recent_g[player]['games']}g-{most_recent_g[player]['saves']}s-{most_recent_g[player]['fpts']}fpts)\n"
        await ctx.send(msg)
    else:
        await ctx.send(f"Error. Possible team {arg} doesn't exist")
    cur.close()

@bot.command(pass_context=True,
             brief="(all teams)",
             name="teams",
             help="Displays teams")
async def teams(ctx):
    cur = con.cursor()
    cur.execute("select team_name, players, goalies from fantasy")
    vals = cur.fetchall() 
    cur.execute(
        "select player_data from players order by time desc limit 1"
    )
    most_recent = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from goalies order by time desc limit 1"
    )
    most_recent_g = ast.literal_eval(cur.fetchall()[0][0])

    if vals:
        msg = ""

        for val in vals:
            msg += f"========{val[0].strip()}" + "="*(len("skaters=======")-len(val[0].strip())) + "\n"

            msg += "========skaters========\n"
            if val[1]:
                for player in list(ast.literal_eval(val[1])):
                    msg += f"{most_recent[player]['name']} ({most_recent[player]['goals']}g-{most_recent[player]['assists']}a-{most_recent[player]['fpts']}fpts)\n"
            msg += "========goalies========\n"
            if val[2]:
                for player in list(ast.literal_eval(val[2])):
                    msg += f"{most_recent_g[player]['name']} ({most_recent_g[player]['games']}g-{most_recent_g[player]['saves']}s-{most_recent_g[player]['fpts']}fpts)\n"
            msg += "\n"
        await ctx.send(msg.strip())
    else:
        await ctx.send(f"The database is empty")
    cur.close()

@bot.command(pass_context=True,
             brief="[team]",
             name="score",
             help="Displays weekly score for team <arg>")
async def score(ctx, arg):
    arg = arg.title()
    cur = con.cursor()
    cur.execute("select team_name, players, goalies from fantasy where team_name = %s",
                (arg, ))
    vals = cur.fetchall() 
    cur.execute(
        "select player_data from players order by time desc limit 1"
    )
    most_recent = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from weekly order by time desc limit 1"
    )
    recent_week = ast.literal_eval(cur.fetchall()[0][0])

    cur.execute(
        "select player_data from goalies order by time desc limit 1"
    )
    most_recent_g = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from weekly_goalie order by time desc limit 1"
    )
    recent_week_g = ast.literal_eval(cur.fetchall()[0][0])
    if vals:
        msg = ""
        score = 0

        for val in vals:
            if val[1]:
                for player in list(ast.literal_eval(val[1])):
                    msg += f"{most_recent[player]['name']} ({most_recent[player]['goals']-recent_week[player]['goals']}g-{most_recent[player]['assists']-recent_week[player]['assists']}a-{most_recent[player]['fpts']-recent_week[player]['fpts']}fpts)\n"
                    try:
                        score += most_recent[player]['fpts'] - recent_week[player]['fpts']
                    except KeyError:
                        score += most_recent[player]['fpts']
            if val[2]:
                for player in list(ast.literal_eval(val[2])):
                    msg += f"{most_recent_g[player]['name']} ({most_recent_g[player]['games']-recent_week_g[player]['games']}g-{most_recent_g[player]['saves']-recent_week_g[player]['saves']}s-{most_recent_g[player]['fpts']-recent_week_g[player]['fpts']}fpts)\n"
                    try:
                        score += most_recent_g[player]['fpts'] - recent_week_g[player]['fpts']
                    except KeyError:
                        score += most_recent_g[player]['fpts'] - recent_week_g[player]['fpts']
            msg = f"========{val[0].strip()}" + "="*(len("skaters=======")-len(val[0].strip())) + f"{score}fpts\n" + msg
        await ctx.send(msg.strip())
    else:
        await ctx.send(f"The database is empty")
    cur.close()


@bot.command(pass_context=True,
             brief="(all teams)",
             name="scores",
             help="Displays weekly scores for all teams")
async def scores(ctx):
    cur = con.cursor()
    cur.execute("select team_name, players, goalies from fantasy")
    vals = cur.fetchall() 
    cur.execute(
        "select player_data from players order by time desc limit 1"
    )
    most_recent = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from weekly order by time desc limit 1"
    )
    recent_week = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from goalies order by time desc limit 1"
    )
    most_recent_g = ast.literal_eval(cur.fetchall()[0][0])
    cur.execute(
        "select player_data from weekly_goalie order by time desc limit 1"
    )
    recent_week_g = ast.literal_eval(cur.fetchall()[0][0])

    if vals:
        msg = ""
        score = 0
        
        for val in vals:
            if val[1]:
                for player in list(ast.literal_eval(val[1])):
                    try:
                        score += most_recent[player]['fpts'] - recent_week[player]['fpts']
                    except KeyError:
                        score += most_recent[player]['fpts']
            if val[2]:
                for player in list(ast.literal_eval(val[2])):
                    try:
                        score += most_recent_g[player]['fpts'] - recent_week_g[player]['fpts']
                    except KeyError:
                        score += most_recent_g[player]['fpts']
            msg = f"========{val[0].strip()}" + "="*(len("skaters=======")-len(val[0].strip())) + f"{score}fpts\n" + msg
        await ctx.send(msg.strip())
    else:
        await ctx.send(f"The database is empty")
    cur.close()

# @bot.command()
# async def clear(ctx, amount=3):
#     await ctx.channel.purge(limit=amount)

bot.run(token)
