import sys
from difflib import SequenceMatcher
from pydantic import BaseModel

from lib import db, jellyfin

class UserInfo:
    name:str
    id:str
    token:str
    host:str

class PlaylistInfo(BaseModel):
    userID:str = ""
    name:str = ""
    recents:str = ""
    favourites:str = ""
    fingerprint:str = ""
    alchemyPercent:int = 0
    freshAlchemy:str = ""
    songCount:int = 0


def stringToFile(fileName, contentsRaw):
    contents = str(contentsRaw)
    with open(fileName, "w+") as output_file:
        output_file.write(contents)
        output_file.close()

def fileToString(fileName) :
    fileContents = ""
    with open(fileName, 'r') as myfile:
        fileContents = myfile.read()
    return str(fileContents)

def parseArgs(allArgs):
    adict = {}
    adict["v"] = False
    i = 1
    for arg in allArgs:
        if arg[0] == "-":
            try:
                adict[arg[1:]] = allArgs[i]
            except IndexError:
                adict[arg[1:]] = True
            except Exception as e:
                print("Couldn't parse {}.\n{}", arg, e)
                sys.exit(3)
        i = i + 1
    return adict

def similarity(a:str, b:str):
    return int(SequenceMatcher(None, a, b).ratio() * 100)

def getPlaylists() -> list:
    q = "SELECT * FROM Playlists"
    d = ()
    r = db.select(query=q, datatuple=d, tableName="Playlists")
    return r

def getUserCount() -> int:
    q = "SELECT * FROM Users"
    d = ()
    r = db.select(query=q, datatuple=d, tableName="Users")
    return len(r)

def getUsers() -> list[UserInfo]:
    q = "SELECT * FROM Users"
    d = ()
    r = db.select(query=q, datatuple=d, tableName="Users")
    userList = []
    for row in r:
        user = UserInfo()
        user.id = row["id"]
        user.name = row["name"]
        user.token = row["token"]
        user.host = row["jellyfinHost"]
        userList.append(user)
    return userList

def getUserInfo(userID:str) -> UserInfo | None:
    q = "SELECT * FROM Users WHERE id = ?"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="Users", verbose=False)
    for row in r:
        # It's okay to return the first match because I 
        # never want users to appear here more than once
        if row["id"] == userID:
            user = UserInfo()
            user.id = row["id"]
            user.name = row["name"]
            user.token = row["token"]
            user.host = row["jellyfinHost"]
            return user
    # This only happens if the user couldn't be found
    return None

def getUserBans(userID:str) -> list:
    q = "SELECT * FROM Bans WHERE userID = ?"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="Bans")
    bannedIDs = []
    for line in r:
        bannedIDs.append(line["id"])
    return bannedIDs

def getUserLimits(userID:str) -> dict:
    defaultLimits = {
        "sameAlbumLimit": 3,
        "sameArtistLimit": 5
    }
    q = "SELECT * FROM userLimits WHERE userID = ?"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="userLimits")
    for line in r:
        if line["userID"] == userID:
            # A limit of 0 makes no sense for these values
            # so I make sure they're 1 or more before giving
            # them back.
            albumLimit = int(line["sameAlbumLimit"])
            if albumLimit == 0:
                albumLimit = 1
            artistLimit = int(line["sameArtistLimit"])
            if artistLimit == 0:
                artistLimit = 1
            return {
                "sameAlbumLimit": albumLimit,
                "sameArtistLimit": artistLimit
            }
    return defaultLimits

def getUserPlaylists(userID:str) -> list:
    q = "SELECT * FROM Playlists WHERE userID = ?"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="Playlists", verbose=False)
    playlists = []
    for row in r:
        playlist = PlaylistInfo()
        playlist.alchemyPercent = row["alchemyPercent"]
        playlist.favourites = row["favourites"]
        playlist.fingerprint = row["fingerprint"]
        playlist.freshAlchemy = row["freschAlchemy"]
        playlist.name = row["name"]
        playlist.songCount = row["songCount"]
        playlist.recents = row["recents"]
        playlist.userID = row["userID"]
        playlists.append(playlist)
    return playlists

def playlistExists(userInfo:UserInfo, playlistName:str):
    p = jellyfin.getPlaylistBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, playlistName=playlistName)
    if "Name" in p.keys():
        if p["Name"] == playlistName:
            return True
    return False

def playlistBuildTime(userInfo:UserInfo, playlistName:str) -> int:
    q = "SELECT * FROM PlaylistBuilds WHERE userID = ? AND name = ? ORDER BY timestamp DESC limit 1"
    d = (userInfo.id, playlistName,)
    r = db.select(query=q, datatuple=d, tableName="PlaylistBuilds")
    age = 0
    print("Found {} result for {}".format(len(r), playlistName))
    for row in r:
        if row["name"] == playlistName:
            return int(row["timestamp"])
    return age

def setPlaylistBuildTime(timestamp:int, name:str, userID:str, build:bool, reason:str):
    q = "INSERT INTO PlaylistBuilds VALUES(?,?,?,?,?)"
    d = (timestamp, name, userID, build, reason,)
    r = db.insert(query=q, datatuple=d, tableName="PlaylistBuilds")