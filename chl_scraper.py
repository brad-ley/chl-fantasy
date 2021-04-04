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
    try:
        data = ast.literal_eval(P.read_text(datafile))
    except Exception:
        data = {}

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

        data[f"{datetime.datetime.now()}"] = player_dict

        datafile.write_text(repr(data))

    datadict = ast.literal_eval(P.read_text(datafile))

    update_days = 1
    matchup_days = 1
    # update_days = 1
    # matchup_days = 7
    update_time = update_days * 24 * 60 * 60
    matchup_time = matchup_days * 24 * 60 * 60
    timestamps = sorted([
        float(
            datetime.datetime.strptime(ii, '%Y-%m-%d %H:%M:%S.%f').timestamp())
        for ii in datadict.keys()
    ],
                        reverse=True)
    daily = [
        ii for ii in timestamps
        if 0 < timestamps[0] - ii < update_time or ii == timestamps[0]
    ]
    weekly = [
        ii for ii in timestamps if matchup_time < timestamps[0] -
        ii < matchup_time + update_time or ii == timestamps[0]
    ]


if __name__ == "__main__":
    main(testing=False)
