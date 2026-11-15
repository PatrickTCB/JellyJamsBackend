import hashlib
import json
import random

from datetime import datetime

from lib import common, db, jellyfin

def getPlaylistHash(userID, jobName):
    q = "SELECT * FROM CustomJobHash WHERE userID = ? and jobName = ?"
    d = (userID,jobName,)
    r = db.select(query=q, datatuple=d, tableName="CustomJobHash")
    for result in r:
        if "hash" in result.keys():
            return result["hash"]
    return ""

def savePlaylistHash(userID, jobName, hash):
    now = int(datetime.now().timestamp())
    q = "INSERT INTO CustomJobHash VALUES(?,?,?,?)"
    d = (now,userID,jobName,hash,)
    db.insert(query=q, datatuple=d, tableName="CustomJobHash")

jobName = "ExampleJob"

print("{} starting at {} and doing super cool stuff.".format(jobName, int(datetime.now().timestamp())))

# Run job per user
users = common.getUsers()
print("Running example job for {} users.".format(len(users)))
for user in users:
    oldPlaylistHash = getPlaylistHash(userID=user.id, jobName=jobName)
    print("===\nHere is where I could do something cool and helpful for user {}".format(user.name))
    try:
        userPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
    except Exception as e:
        print("Couldn't get playlists for {}.\nProbably an error worth fixing before setting up your own custom job.".format(user.name))
        print(e)
        userPlaylists = {"Items": []}
    currentPlaylistHash = hashlib.md5(json.dumps(userPlaylists).encode("utf-8")).hexdigest()
    if currentPlaylistHash == oldPlaylistHash:
        print("No need to run {} again. Nothing has changed since the last run.".format(jobName))
    else:
        print("Playlists have changed since last {} run. Running again to do cool stuff.".format(jobName))
        try:
            favouriteSongs = jellyfin.favourites(host=user.host, token=user.token, userID=user.id)
        except Exception as e:
            print("Couldn't get favourite songs for {}.\nProbably an error worth fixing before setting up your own custom job.".format(user.name))
            print(e)
            favouriteSongs = {"Items": []}
        if len(favouriteSongs["Items"]) > 0 and len(userPlaylists["Items"]) > 0:
            randomPlaylist = random.choice(userPlaylists["Items"])
            randomSong = random.choice(favouriteSongs["Items"])
            print("I could have added '{song}' by '{artist}' to '{playlist}', that would've been cool.".format(song=randomSong["Name"], artist=" & ".join(randomSong["Artists"]), playlist=randomPlaylist["Name"]))
        try:
            newUserPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
        except Exception as e:
            print("Couldn't get playlists for {}.\nProbably an error worth fixing before setting up your own custom job.".format(user.name))
            print(e)
            newUserPlaylists = {"Items": []}
        newPlaylistHash = hashlib.md5(json.dumps(newUserPlaylists).encode("utf-8")).hexdigest()
        print("Saved hash of the playlists as they are now, at the end of {}".format(jobName))
print("All done my custom work.")