import requests
import json
import time
import pandas as pd
import ast
import datetime
from pathlib import Path as P

filename = "stats.csv" 


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
            player_dict[entry['name']] = {"goals":entry["goals"], "assists":entry["assists"]}

        data[f"{datetime.datetime.now()}"] = player_dict
    
        datafile.write_text(repr(data))

    datadict = ast.literal_eval(P.read_text(datafile))

    timestamps = sorted([float(datetime.datetime.strptime(ii, '%Y-%m-%d %H:%M:%S.%f').timestamp()) for ii in datadict.keys()], reverse=True)
    now_and_prev = [ii for ii in timestamps if 7*24*60*60 < timestamps[0] - ii < 7*24*60*60 + 12*60*60]
    print(now_and_prev)


if __name__ == "__main__":
    main(testing=False)
