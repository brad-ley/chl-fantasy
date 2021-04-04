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
                "name": entry["name"],
                "goals": int(entry["goals"]),
                "assists": int(entry["assists"]),
                "fpts": int(entry["goals"]) * 5 + int(entry["assists"]) * 3
            }
    return player_dict


def main(testing=False):
    datafile = P("./data.txt")

    if testing:
        pass
    else:
        url = 'https://lscluster.hockeytech.com/feed/?feed=modulekit&view=statviewtype&type=topscorers&key=41b145a848f4bd67&fmt=json&client_code=whl&lang=en&league_code=&season_id=273&first=0&limit=10&sort=active&stat=all&order_direction='
        response = requests.get(url)
        datalist = response.json()['SiteKit']['Statviewtype']

        player_dict = {}
        
        for entry in datalist:
            player_dict[entry["player_id"]] = {
                "name": entry["name"],
                "goals": entry["goals"],
                "assists": entry["assists"]
            }

        datafile.write_text(repr(datalist))


if __name__ == "__main__":
    main(testing=False)
