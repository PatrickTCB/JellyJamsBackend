import hashlib
import json
import os
import time

from datetime import datetime

from lib import db, jellyfin, common

print("Container starting at {} and running the initial DB custodial work.".format(int(datetime.now().timestamp())))
# At startup make sure the db and required tables all exist
db.create(useExisting=True, verbose=False)
# Create 'Users' table if it doesn't exist
usersColumns = ["id", "name", "token", "jellyfinHost"]
db.table(tableName="Users", tableColumns=usersColumns, verbose=False)
# Create 'Bans' table
banColumns = ["userID", "id"]
db.table(tableName="Bans", tableColumns=banColumns)
# Create 'User Limits' table. Helps users generate playlists without
# them being dominated by too many of the same artist/album songs
dupColumns = ["userID", "sameAlbumLimit", "sameArtistLimit"]
db.table(tableName="userLimits", tableColumns=dupColumns)
# Create 'Playlists' table
playlistsColumns = ["userID", "name", "recents", "favourites", "fingerprint", "alchemyPercent", "freshAlchemy", "songCount"]
db.table(tableName="Playlists", tableColumns=playlistsColumns)
# Create 'Family Blend' table.
serverPlaylistColumns = ["userID"]
db.table(tableName="ServerPlaylist", tableColumns=serverPlaylistColumns)
print("DB Setup is done.")
# Create 'PlaylistBuilds' table
playlistBuildsColumns = ["timestamp", "name", "userID", "built", "reason"]
db.table(tableName="PlaylistBuilds", tableColumns=playlistBuildsColumns)

# Setup is done, now for the task loop.

# Variables that need to be set at the start
oldMixtapeHash = ""
while True:
    print("New task loop starting at {}.".format(int(datetime.now().timestamp())))
    # Per user jobs
    users = common.getUsers()
    for user in users:
        # Job 1: Scrub bans from _automatic playlists
        userBans = common.getUserBans(userID=user.id)
        extraParams = {
            "includeItemTypes": "Playlist",
            "fields": "ProviderIds,Path,MediaSources,MediaStreams"
        }
        mixtapes = jellyfin.getItemBySearch(host=user.host, token=user.token, userID=user.id, searchTerm="_automatic", extraParams=extraParams)
        newMixtapeHash = hashlib.md5(json.dumps(mixtapes).encode("utf-8")).hexdigest()
        if newMixtapeHash == oldMixtapeHash:
            print("Mixtapes for {} haven't changed since I last looked. No work to do.".format(user.name))
        else:
            # The playlists have changed since they were last checked. The should be checked for
            # banable songs. 
            for tape in mixtapes["Items"]:
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
            oldMixtapeHash = hashlib.md5(json.dumps(updatedMixtapes).encode("utf-8")).hexdigest()
    print("Waiting...", end="\r")
    time.sleep(120)
