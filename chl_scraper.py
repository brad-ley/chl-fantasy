import ast
import datetime
import json
import time
from pathlib import Path as P

import requests


def scrape(league='whl', testing=False):
    if league == 'whl':
        if testing:
            limit = 10
        else:
            limit = 1000
        url = f'https://lscluster.hockeytech.com/feed/?feed=modulekit&view=statviewtype&type=topscorers&key=41b145a848f4bd67&fmt=json&client_code=whl&lang=en&league_code=&season_id=273&first=0&limit={limit}&sort=active&stat=all&order_direction='
        response = requests.get(url)
        datalist = response.json()['SiteKit']['Statviewtype']

        player_dict = {}

        for entry in datalist:
            player_dict[int(entry["player_id"])] = {
                "name": entry["name"].replace(" (total)",""),
                "goals": int(entry["goals"]),
                "assists": int(entry["assists"]),
                "fpts": int(entry["goals"]) * 5 + int(entry["assists"]) * 3
            }

        url = f'https://lscluster.hockeytech.com/feed/?feed=modulekit&view=statviewtype&type=topgoalies&key=41b145a848f4bd67&fmt=json&qualified=qualified&client_code=whl&lang=en&league_code=&season_id=273&first=0&limit={limit}&sort=active&order_direction='
        response = requests.get(url)
        datalist = response.json()['SiteKit']['Statviewtype']

        goalie_dict = {}

        for entry in datalist:
            goalie_dict[int(entry["player_id"])] = {
                "name": entry["name"].replace(" (total)",""),
                "games": int(entry["games_played"]),
                "saves": int(entry["saves"]),
                "wins": int(entry["wins"]),
                "shutouts": int(entry["shutouts"]),
                "fpts": int(entry["saves"])*0.4 - int(entry["games_played"])*3 + int(entry["shutouts"])*5 + int(entry["wins"])*3
            }
    return player_dict, goalie_dict


def main(testing=False):
    datafile = P("./data.txt")

    if testing:
        pass
    else:
        url = 'https://lscluster.hockeytech.com/feed/?feed=modulekit&view=statviewtype&type=topscorers&key=41b145a848f4bd67&fmt=json&client_code=whl&lang=en&league_code=&season_id=273&first=0&limit=1000&sort=active&stat=all&order_direction='
        response = requests.get(url)
        datalist = response.json()['SiteKit']['Statviewtype']

        datafile.write_text(repr(datalist))
        player_dict = {}
        
        for entry in datalist:
            player_dict[entry["player_id"]] = {
                "name": entry["name"],
                "goals": entry["goals"],
                "assists": entry["assists"]
            }

        url = f'https://lscluster.hockeytech.com/feed/?feed=modulekit&view=statviewtype&type=topgoalies&key=41b145a848f4bd67&fmt=json&qualified=qualified&client_code=whl&lang=en&league_code=&season_id=273&first=0&limit=1000&sort=active&order_direction='
        response = requests.get(url)
        datalist = response.json()['SiteKit']['Statviewtype']



if __name__ == "__main__":
    main(testing=False)
