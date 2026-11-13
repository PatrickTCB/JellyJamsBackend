import hashlib
import json
import os
import time

from datetime import datetime

from lib import db

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
# Create 'MixtapeHash' table
mixtapeHashColumns = ["timestamp", "userID", "hash"]
db.table(tableName="MixtapeHash", tableColumns=mixtapeHashColumns)
# Setup is done, now for the task loop.