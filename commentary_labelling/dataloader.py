import pickle
from difflib import SequenceMatcher
import ujson as json

from commentary_labelling.Logger import Logger

logger = Logger.getInstance()

team_map = {'P.N.G.': 'PNG',
            'India': 'INDIA',
            'Canada': 'CAN',
            'Kenya': 'KENYA',
            'New Zealand': 'NZ',
            'Oman': 'OMAN',
            'Nepal': 'NEPAL',
            'Ireland': 'IRE',
            'Hong Kong': 'HKG',
            'Scotland': 'SCOT',
            'Pakistan': 'PAK',
            'Namibia': 'NAM',
            'U.S.A.': 'USA',
            'Bangladesh': 'BDESH',
            'Zimbabwe': 'ZIM',
            'Sri Lanka': 'SL',
            'South Africa': 'SA',
            'U.A.E.': 'UAE',
            'West Indies': 'WI',
            'Australia': 'AUS',
            'Afghanistan': 'AFG',
            'Bermuda': 'BMUDA',
            'Netherlands': 'NL',
            'England': 'ENG'}

id_to_team = {v: k for k, v in team_map.items()}

getTeamName = lambda team_id: id_to_team[team_id]
getTeamId = lambda team_name: team_map[team_name]


def getOver(balls, over):
    retBalls = []
    for i, b in enumerate(balls):
        if over == int(b['over']):
            retBalls.append(i)
    return retBalls


def getPlayersBallsFromInnings(profile, innings):
    sums = innings['over_summaries']
    balls = []
    for idx in reversed(range(len(sums))):
        summary = sums[idx]
        if summary['next_bowler'] == profile['known_as']:
            balls += getOver(innings['balls'], int(summary['number']) - 1)

    return sorted(balls)


class DataLoader(object):
    instance = None
    matches = None
    players = None
    loaded = False

    def __init__(self):
        pass

    @staticmethod
    def getInstance():
        if not DataLoader.instance:
            DataLoader.instance = DataLoader()

        return DataLoader.instance

    @staticmethod
    def getPlayerProfile(name):
        returnList = []
        for i, p in DataLoader.players.items():
            match = SequenceMatcher(a=p['known_as'].lower(), b=name.lower()).ratio()
            if match > 0.6:
                returnList.append((p, match))

        return [i[0] for i in sorted(returnList, key=lambda x: x[1], reverse=True)]

    @staticmethod
    def load():
        if not DataLoader.loaded:
            with open('../matches.json', 'r') as f:
                DataLoader.matches = json.load(f)

            with open('../player_table.json', 'r') as f:
                DataLoader.players = json.load(f)

            DataLoader.loaded = True

    @staticmethod
    def getMatchDetails(match_id):
        returnTable = []
        for k, v in DataLoader.matches[match_id].items():
            if k not in ['commentary', 'team_1_players', 'team_2_players']:
                returnTable.append([k, v])
        return returnTable


    @staticmethod
    def getAllPlayerOvers(playerName):
        DataLoader.load()
        overs = []
        try:
            profile = DataLoader.getPlayerProfile(playerName)[0]
        except:
            logger.log(f"Unable to fetch any balls for {playerName}!")
            return

        p_id = profile['player_id']

        for i, m in DataLoader.matches.items():
            # Check which team player is in, if any
            if p_id in m['team_1_players']:
                teamNum = 1
            elif p_id in m['team_2_players']:
                teamNum = 2
            else:
                continue

            # Check which innings player bowled in
            team_id = getTeamId(m[f'team{teamNum}'])
            inn = 2 if team_id == m['batting_first'] else 1

            # Get all balls from match
            balls = getPlayersBallsFromInnings(profile, m['commentary'][f'innings{inn}'])
            if balls:
                overs.append((i, inn, balls))

        return overs

    @staticmethod
    def getBall(match_id, innings, ball):
        return DataLoader.matches[match_id]['commentary'][f'innings{innings}']['balls'][ball]

    @staticmethod
    def store(line, length, match_id, innings, ball):
        DataLoader.matches[match_id]['commentary'][f'innings{innings}']['balls'][ball]['pitch']['line'] = line
        DataLoader.matches[match_id]['commentary'][f'innings{innings}']['balls'][ball]['pitch']['length'] = length

    @staticmethod
    def commit(name, jsonFile=False):
        with open(f"{name}.pkl", "wb") as f:
            pickle.dump(DataLoader.matches, f)

        if jsonFile:
            with open('matches_pitch.json', 'w') as json_file:
                json.dump(DataLoader.matches, json_file)

    @staticmethod
    def getPlayers(match_id):
        returnDict = {}
        team1players = []
        for player in DataLoader.matches[match_id]['team_1_players']:
            team1players.append(DataLoader.players[player])

        team2players = []
        for player in DataLoader.matches[match_id]['team_2_players']:
            team2players.append(DataLoader.players[player])

        returnDict['team1'] = team1players
        returnDict['team2'] = team2players

        return returnDict

