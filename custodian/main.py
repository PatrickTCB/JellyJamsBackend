import hashlib
import json
import os
import time

from datetime import datetime

from lib import db, jellyfin, common

def getOldMixtapeHash(userID):
    q = "SELECT * FROM MixtapeHash WHERE userID = ?"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="MixtapeHash")
    for result in r:
        if "hash" in result.keys():
            return result["hash"]
    return ""

def saveMixtapHash(userID, hash):
    now = int(datetime.now().timestamp())
    q = "INSERT INTO MixtapHash VALUES(?,?,?)"
    d = (now,userID,hash)
    db.insert(query=q, datatuple=d, tableName="MixtapeHash")

print("New task loop starting at {}.".format(int(datetime.now().timestamp())))
# Per user jobs
users = common.getUsers()
for user in users:
    print("---\nStarting standard jobs for {}.".format(user.name))
    oldMixtapeHash = getOldMixtapeHash(userID=user.id)
    # Job 1: Scrub bans from _automatic playlists
    userBans = common.getUserBans(userID=user.id)
    extraParams = {
        "includeItemTypes": "Playlist",
        "fields": "ProviderIds,Path,MediaSources,MediaStreams"
    }
    mixtapes = jellyfin.getItemBySearch(host=user.host, token=user.token, userID=user.id, searchTerm="_automatic", extraParams=extraParams)
    currentMixtapeHash = hashlib.md5(json.dumps(mixtapes).encode("utf-8")).hexdigest()
    if currentMixtapeHash == oldMixtapeHash:
        print("Mixtapes for {} haven't changed since I last looked. No work to do.".format(user.name))
    else:
        # The playlists have changed since they were last checked. The should be checked for
        # banable songs. 
        for tape in mixtapes["Items"]:
            print("Checking out {} for {}".format(tape["Name"], user.name))
            if tape["Name"] == "{}_automatic".format(os.environ["SERVER_PLAYLIST"]):
                print("Won't remove user ignores from the family blend")
            else:
                tapeExtraParams = {
                    "parentId": tape["Id"],
                    "sortOrder": "Ascending",
                    "includeItemTypes": "Audio",
                    "sortBy": "IndexNumber"
                }
                tapeTracks = jellyfin.getItemBySearch(host=user.host, token=user.token, userID=user.id, extraParams=tapeExtraParams)
                for track in tapeTracks["Items"]:
                    banned = False
                    songIds = []
                    songIds.append(track["Id"])
                    songIds.append(track["AlbumId"])
                    for genre in track.get("GenreItems", []):
                        songIds.append(genre["Id"])
                    for artist in track["ArtistItems"]:
                        songIds.append(artist["Id"])
                    for albumArtist in track["AlbumArtists"]:
                        songIds.append(albumArtist["Id"])
                    if any(item in songIds for item in userBans):
                        print("{} isn't allowed in lists for {}.".format(track["Name"], user.name))
                        banned = True
                    if banned:
                        print("Removing {} from {}.".format(track["Name"], tape["Name"]))
                        jellyfin.removeFromPlaylist(host=user.host, token=user.token, entryIDs=track["Id"], userID=user.id, playlistID=tape["Id"])
        # By now the tapes are all updated, so let's build the new 'old' hash.
        updatedMixtapes = jellyfin.getItemBySearch(host=user.host, token=user.token, userID=user.id, searchTerm="_automatic", extraParams=extraParams)
        brandNewMixtapeHash = hashlib.md5(json.dumps(updatedMixtapes).encode("utf-8")).hexdigest()
        saveMixtapHash(userID=user.id, hash=brandNewMixtapeHash)
