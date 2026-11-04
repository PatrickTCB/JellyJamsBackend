import os
import random
import sys

from datetime import datetime
from typing import List

from lib import audiomuse, jellyfin, db, common
from lib.common import UserInfo

def serverPlaylistUsers() -> List[UserInfo]:
    q = "SELECT * FROM ServerPlaylist"
    d = ()
    r = db.select(query=q, datatuple=d, tableName="ServerPlaylist")
    users = []
    for row in r:
        user = common.getUserInfo(userID=row["userID"])
        users.append(user)
    return users

users = serverPlaylistUsers()

ServerPlaylistSongCount = 100
alchemySongAmount = int(0.2 * ServerPlaylistSongCount)
normalSongAmount = ServerPlaylistSongCount - alchemySongAmount
songsPerUser = int(normalSongAmount / 2)

serverPlaylistName = "{}_automatic".format(os.environ["SERVER_PLAYLIST"])
maxAge = 84600
currentTimeStamp = int(datetime.now().timestamp())

# In case the playlist already exists and is less than 24h old
# I will not remake it.
buildPlaylist = False
print("Attempting to build '{}' for {} users.".format(os.environ["SERVER_PLAYLIST"], len(users)))
reason = "Error. The somehow couldn't tell if the playlist existed or how old it might be. See logs."
for user in users:
    playlistExists = common.playlistExists(userInfo=user, playlistName=serverPlaylistName)
    if playlistExists:
        playlistBuildTime = common.playlistBuildTime(userInfo=user, playlistName=serverPlaylistName)
        print("Playlist build time: {}".format(playlistBuildTime))
        print("Current time: {}".format(currentTimeStamp))
        playlistAge = currentTimeStamp - playlistBuildTime
        if playlistAge > maxAge:
            buildPlaylist = True
            reason = "Existing version is {} seconds old".format(playlistAge)
        else:
            reason = "Exsisting playlist is fresh."
    else:
        buildPlaylist = True
        reason = "Playlist {} doesn't currently exist".format(serverPlaylistName)
    
if buildPlaylist == False:
    print("Not building playlist due to reason: {}".format(reason))
    exitCode = 0
    if "Error" in reason:
        exitCode = 1
    sys.exit(exitCode)
else:
    print("Building new version of {} because of reason: {}".format(serverPlaylistName, reason))

albumsUsed = []
artistsUsed = []
playlistSongIDs = []
familyIgnoredIDs = []
familyLimits = {
    "sameAlbumLimit": 3,
    "sameArtistLimit": 5
}
if len(users) == 0:
    print("0 users on this server have signed up for the '{}' playlist. Nothing to do here.".format(serverPlaylistName))
    sys.exit(0)
    
for userInfo in users:
    userSongs = []
    userBans = common.getUserBans(userID=userInfo.id)
    userLimits = common.getUserLimits(userID=userInfo.id)
    recents = jellyfin.recentPlays(host=userInfo.host, token=userInfo.token, userID=userInfo.id)
    # User's Recents
    print("Got {} recents".format(len(recents)))
    random.shuffle(recents)
    for song in recents:
        allowed = True
        if "Album" not in song.keys():
            print("{} didn't have an album".format(song["Name"]))
            song["Album"] = "None"
        songIds = []
        songIds.append(song["Id"])
        songIds.append(song["AlbumId"])
        for genre in song.get("GenreItems", []):
            songIds.append(genre["Id"])
        for artist in song["ArtistItems"]:
            songIds.append(artist["Id"])
        for albumArtist in song["AlbumArtists"]:
            songIds.append(albumArtist["Id"])
        if any(item in songIds for item in userBans):
            print("{} isn't allowed in lists for {}.".format(song["Name"], userInfo.name))
            allowed = False
        if albumsUsed.count(song["Album"]) >= userLimits["sameAlbumLimit"]:
            allowed = False
        for artist in song["Artists"]:
            if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                allowed = False
        if (song["Id"] in playlistSongIDs) or (song["Id"] in userSongs):
            allowed = False
        if allowed:
            albumsUsed.append(song["Album"])
            for artist in song["Artists"]:
                artistsUsed.append(artist)
            userSongs.append(song["Id"])
    # Favs
    favs = jellyfin.favourites(host=userInfo.host, token=userInfo.token, userID=userInfo.id)
    random.shuffle(favs["Items"])
    print("Got {} favourites".format(len(favs["Items"])))
    for song in favs["Items"]:
        allowed = True
        if "Album" not in song.keys():
            print("{} didn't have an album".format(song["Name"]))
            song["Album"] = "None"
        songIds = []
        songIds.append(song["Id"])
        songIds.append(song["AlbumId"])
        for genre in song.get("GenreItems", []):
            songIds.append(genre["Id"])
        for artist in song["ArtistItems"]:
            songIds.append(artist["Id"])
        for albumArtist in song["AlbumArtists"]:
            songIds.append(albumArtist["Id"])
        if any(item in songIds for item in userBans):
            print("{} isn't allowed in lists for {}.".format(song["Name"], userInfo.name))
            allowed = False
        if albumsUsed.count(song["Album"]) >= userLimits["sameAlbumLimit"]:
            allowed = False
        for artist in song["Artists"]:
            if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                allowed = False
        if (song["Id"] in playlistSongIDs) or (song["Id"] in userSongs):
            allowed = False
        if allowed:
            albumsUsed.append(song["Album"])
            for artist in song["Artists"]:
                artistsUsed.append(artist)
            userSongs.append(song["Id"])
    # Fingerprint songs
    songs = audiomuse.sonicFingerprint(userID=userInfo.id, userToken=userInfo.token, songCount=int(songsPerUser))
    print("Got back {} tracks from audiomuse".format(len(songs)))
    random.shuffle(songs)
    for song in songs:
        allowed = True
        jellyfinItem = jellyfin.item(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemID=song["item_id"])
        songIds = []
        songIds.append(jellyfinItem["Id"])
        songIds.append(jellyfinItem["AlbumId"])
        for genre in jellyfinItem.get("GenreItems", []):
            songIds.append(genre["Id"])
        for artist in jellyfinItem["ArtistItems"]:
            songIds.append(artist["Id"])
        for albumArtist in jellyfinItem["AlbumArtists"]:
            songIds.append(albumArtist["Id"])
        if any(item in songIds for item in userBans):
            print("{} isn't allowed in lists for {}.".format(jellyfinItem["Name"], userInfo.name))
            allowed = False
        if albumsUsed.count(jellyfinItem["Album"]) >= userLimits["sameAlbumLimit"]:
            allowed = False
        for artist in jellyfinItem["Artists"]:
            if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                allowed = False
        if (song["item_id"] in playlistSongIDs) or (song["item_id"] in userSongs):
            allowed = False
        if allowed:
            albumsUsed.append(song["album"])
            artistsUsed.append(song["author"])
            userSongs.append(song["item_id"])
    if len(userSongs) > songsPerUser:
        playlistSongIDs.extend(random.sample(userSongs, songsPerUser))
    else:
        playlistSongIDs.extend(userSongs)
# Now each users songs are in `playlistSongs`
# I'll take that list of songs and use the alchemy feature to fill out
# the last 20% of songs.
print("Making alchemy out of {} server playlist songs".format(len(playlistSongIDs)))
alchemySongs = audiomuse.alchemy(addSongs=playlistSongIDs, songLimit=(alchemySongAmount * 5))
print("Will try to get {} songs out of {} alchemy options returned".format(alchemySongAmount, len(alchemySongs)))
alchemySongsAdded = 0
for song in alchemySongs:
    allowed = True
    jellyfinItem = jellyfin.item(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemID=song["item_id"])
    songIds = []
    songIds.append(jellyfinItem["Id"])
    songIds.append(jellyfinItem["AlbumId"])
    for genre in jellyfinItem.get("GenreItems", []):
        songIds.append(genre["Id"])
    for artist in jellyfinItem["ArtistItems"]:
        songIds.append(artist["Id"])
    for albumArtist in jellyfinItem["AlbumArtists"]:
        songIds.append(albumArtist["Id"])
    if any(item in songIds for item in userBans):
        print("{} isn't allowed in lists for {}.".format(jellyfinItem["Name"], userInfo.name))
        allowed = False
    if albumsUsed.count(jellyfinItem["Album"]) >= familyLimits["sameAlbumLimit"]:
        allowed = False
    for artist in jellyfinItem["Artists"]:
        if artistsUsed.count(artist) >= familyLimits["sameArtistLimit"]:
            allowed = False
    if song["item_id"] in playlistSongIDs:
        allowed = False
    if alchemySongsAdded >= alchemySongAmount:
        allowed = False
    if allowed:
        albumsUsed.append(song["album"])
        artistsUsed.append(song["author"])
        playlistSongIDs.append(song["item_id"])
        alchemySongsAdded = alchemySongsAdded + 1

print("Family blend will now be built out of {} songs after adding {} alchemy songs.".format(len(playlistSongIDs), alchemySongsAdded))
random.shuffle(playlistSongIDs)
if len(playlistSongIDs) == 0:
    print("Somehow, after all this we've got 0 songs for the Family Blend. Something has probably gone wrong.")
    sys.exit(1)
    
for userInfo in users:
    jellyfin.playlistSetup(host=userInfo.host, name=serverPlaylistName, token=userInfo.token, userID=userInfo.id, songs=playlistSongIDs, verbose=False)
    common.setPlaylistBuildTime(timestamp=currentTimeStamp, name=serverPlaylistName, userID=userInfo.id, build=True, reason=reason)