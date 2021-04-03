import requests
import pandas as pd
import json
import time
from random import randint

# The csv file to save the data to
filename = "lineups.csv"

# The GameID for the game we want to scrape
event_id = 24633

# The URL of the game we want to scrape, including the GameID
url = "https://cluster.leaguestat.com/feed/index.php?feed=gc&key=2976319eb44abe94&client_code=ohl&game_id={event_id}&lang_code=en&fmt=json&tab=gamesummary".format(event_id=event_id)

# Sends a request to the URL to grab the data
response = requests.get(url)

# Gives the website a quick breather between attempts. It's earned it.
#time.sleep(randint(4,5))

# Stores the JSON response
fjson = response.json()

# Extracts the home team lineup and the away team lineup
hdata = fjson['GC']['Gamesummary']['home_team_lineup']['players']
adata = fjson['GC']['Gamesummary']['visitor_team_lineup']['players']

# Converts the JSON to a Pandas dataframe
dfh = pd.DataFrame(hdata)
dfa = pd.DataFrame(adata)

# Appends the game number and a home/away flag to the dataframes
gamenodfh = pd.DataFrame(data={'GAME_ID' : [event_id], 'H_A' : ['H']})
finaldfh = dfh.assign(**gamenodfh.iloc[0])
gamenodfa = pd.DataFrame(data={'GAME_ID' : [event_id], 'H_A' : ['A']})
finaldfa = dfa.assign(**gamenodfa.iloc[0])

# Specify columns to keep in our final file and their order
col_list = ['GAME_ID', 'player_id', 'person_id', 'first_name', 'last_name', 'jersey_number', 'position_str', 'shots', 'shots_on', 'goals', 'assists', 'faceoff_wins', 'faceoff_attempts', 'plusminus', 'hits', 'pim', 'H_A']
finaldfh = finaldfh[col_list]
finaldfa = finaldfa[col_list]    

# Writes the lineups to a CSV file
finaldfh.to_csv(filename, mode='a', sep='|', encoding='utf-8')
finaldfa.to_csv(filename, mode='a', sep='|', encoding='utf-8', header=False)
