import hashlib
import json
import os
import random
import sys

from collections import Counter
from datetime import datetime

from lib import audiomuse, db, common, jellyfin

def resetMixTapes(user:common.UserInfo, playlistSuffix:str) -> None:
    userPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
    for playlist in userPlaylists["Items"]:
        if playlistSuffix in playlist["Name"]:
            jellyfin.deletePlaylist(host=user.host, token=user.token, userID=user.token, playlistID=playlist["Id"])

def journeyPlaylist(user:common.UserInfo, recents:list, userBans:list, usedSourceBands:list, limit:int) -> list:
    playlistSongs = []
    usableRecents = []
    for song in recents:
        allowed = True
        songIds = []
        songIds.append(song["Id"])
        songIds.append(song["AlbumId"])
        for genre in song.get("GenreItems", []):
            songIds.append(genre["Id"])
        for artist in song["ArtistItems"]:
            songIds.append(artist["Id"])
            if artist["Id"] in usedSourceBands:
                allowed = False
        for albumArtist in song["AlbumArtists"]:
            songIds.append(albumArtist["Id"])
            if albumArtist["Id"] in usedSourceBands:
                allowed = False
        if any(item in songIds for item in userBans):
            print("{} isn't allowed in lists for {}.".format(song["Name"], user.name))
            allowed = False
        if allowed:
            usableRecents.append(song)
    if len(usableRecents) > 1:
        #first pick two songs
        songs = random.sample(usableRecents, 2)
        song1 = songs[0]
        song2 = songs[1]
        if song1["Id"] == song2["Id"]:
            notSong1 = []
            # song2 is identical to song1, need another
            # but the recent listens might all be the same song
            # make a list of recent listens that are not song1 first
            for song in usableRecents:
                if song["Id"] != song1["Id"]:
                    notSong1.append(song)
            if len(notSong1) > 0:
                song2 = random.choice(notSong1)
            else:
                # all recent listen seem to be of the
                # same song. That makes this kind of 
                # list impossible
                return playlistSongs
        songPath = audiomuse.songPath(startSongID=song1["Id"], endSongID=song2["Id"], limit=limit)
        for amSong in songPath["path"]:
            jfItem = jellyfin.item(host=user.host, token=user.token, userID=user.id, itemID=amSong["item_id"])
            allowed = True
            songIds = []
            songIds.append(amSong["Id"])
            songIds.append(amSong["AlbumId"])
            for genre in amSong.get("GenreItems", []):
                songIds.append(genre["Id"])
            for artist in amSong["ArtistItems"]:
                songIds.append(artist["Id"])
            for albumArtist in amSong["AlbumArtists"]:
                songIds.append(albumArtist["Id"])
            if any(item in songIds for item in userBans):
                print("{} isn't allowed in lists for {}.".format(song["Name"], user.name))
                allowed = False
            if allowed:
                playlistSongs.append(jfItem)
    return playlistSongs

def recentsToAlchemy(user:common.UserInfo, userBans:list, limit:int):
    allRecents = jellyfin.recentPlays(host=user.host, token=user.token, userID=user.id, includePartial=True)
    addSongs = []
    subtractSongs = []
    usedSongs = []
    for song in allRecents:
        if song["Id"] != usedSongs:
            if song["PlayBackEvent"] == "play":
                addSongs.append(song["Id"])
            else:
                subtractSongs.append(song["Id"])
            usedSongs.append(song["Id"])
    alchemySongs = audiomuse.alchemy(addSongs=addSongs, subtractSongs=subtractSongs, songLimit=limit)
    playlistSongs = []
    for song in alchemySongs:
        allowed = True
        jellyfinItem = jellyfin.item(host=user.host, token=user.token, userID=user.id, itemID=song["item_id"])
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
            print("{} isn't allowed in lists for {}.".format(jellyfinItem["Name"], user.name))
            allowed = False
        if allowed:
            playlistSongs.append(song["item_id"])
    return playlistSongs

def getOldMixtapeHash(userID):
    q = "SELECT * FROM MixtapeHash WHERE userID = ? ORDER BY timestamp DESC LIMIT 1"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="MixtapeHash", verbose=True)
    if len(r) > 0:
        return r[0]
    return {}

def saveMixtapHash(userID, hash):
    now = int(datetime.now().timestamp())
    q = "INSERT INTO MixtapHash VALUES(?,?,?)"
    d = (now,userID,hash)
    db.insert(query=q, datatuple=d, tableName="MixtapeHash")


if os.environ["JELLY_JAMS_RADIO"] != "true":
    print("Jelly Jams Mixtapes are disabled. This job won't run")
    sys.exit(0)
else:
    print("Building Jelly Jams Mixtapes for every user")

amRadio = False
amCron = audiomuse.cron()
for job in amCron:
    if job["name"] == "Radio Playlists":
        amRadio = job["enabled"]
if amRadio:
    print("WARNING! - The AudoMuse-AI Radio Playlists job is active. This job can step on the results of this script for one or more users.")

users = common.getUsers()
tapeCount = 10
tapeSongLimit = 25
tapeExpiry = 86400 # 24hrs
playlistSuffix = os.environ["PLAYLIST_SUFFIX"]
for user in users:
    oldMixtapeHash = getOldMixtapeHash(userID=user.id)
    now = int(datetime.now().timestamp())
    mixtapeAge = int(now - oldMixtapeHash["timestamp"])
    if mixtapeAge > tapeExpiry:
        userBans = common.getUserBans(userID=user.id)
        recents = jellyfin.recentPlays(host=user.host, token=user.token, userID=user.id)
        # I don't want all the tapes to be based on the same artists so I track which
        # ones were used, and don't use them more than once.
        usedSourceBands = []
        tapesMade = 0
        tapeCount = 0
        while tapesMade < tapeCount:
            tapeMethod = random.randint(1, 3)
            print("Starting tape {} for {} using method {}.".format(tapeCount, user.name, tapeMethod))
            tapeSongs = []
            playlistName = "Mixtape {}{}".format(tapeCount, playlistSuffix)
            if tapeMethod == 1:
                # Method 1 - Take a journey from one song to another
                tapeSongs = journeyPlaylist(user=user, recents=recents, userBans=userBans, usedSourceBands=usedSourceBands, limit=tapeSongLimit)
                # The "source" artists are taken from the first and last songs
                startSong = tapeSongs[0]
                for artist in startSong["ArtistItems"]:
                    usedSourceBands.append(artist["Id"])
                for albumArtist in startSong["AlbumArtists"]:
                    usedSourceBands.append(artist["Id"])
                endSong = tapeSongs[-1]
                for artist in endSong["ArtistItems"]:
                    usedSourceBands.append(artist["Id"])
                for albumArtist in endSong["AlbumArtists"]:
                    usedSourceBands.append(artist["Id"])
                playlistName = "{} to {}{}".format(startSong["AlbumArtist"], endSong["AlbumArtist"], playlistSuffix)
            if tapeMethod == 2:
                # Method 2 - Make a tape based on some artist the user has
                # been listening to
                candidateArtists = []
                artistNameToID = {}
                for song in recents:
                    for artist in song["ArtistsItems"]:
                        if artist["Id"] not in usedSourceBands:
                            candidateArtists.append(artist)
                            if artist["Name"] not in artistNameToID.keys():
                                artistNameToID[artist["Name"]] = artist["Id"]
                artist = Counter(candidateArtists).most_common(1)[0][0]
                artistId = artistNameToID["artist"]
                usedSourceBands.append(artistId)
                searchTerm = "{} and Friends".format(artist)
                playlistName = "{} and Friends{}".format(artist, playlistSuffix)
                audiomuseSongs = audiomuse.instantPlaylist(query=searchTerm, limit=tapeSongLimit)
                tapeSongs = []
                for song in audiomuseSongs:
                    # Respect the user's bans
                    allowed = True
                    jellyfinItem = jellyfin.item(host=user.host, token=user.token, userID=user.id, itemID=song["item_id"])
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
                        print("{} isn't allowed in lists for {}.".format(jellyfinItem["Name"], user.name))
                        allowed = False
                    if allowed:
                        tapeSongs.append(jellyfinItem)
            if len(tapeSongs) == 0:
                tapeSongs = recentsToAlchemy(user=user, userBans=userBans, limit=tapeSongLimit)
                playlistName = "{} Alchemy{}".format(tapeSongs[0]["AlbumArtist"], playlistSuffix)
            if len(tapeSongs) > 0:
                # At this point, the tapeSongs list has the songs we need
                # and the playlist has a name.
                tapeSongIds = []
                for song in tapeSongs:
                    tapeSongIds.append(song["Id"])
                jellyfin.playlistSetup(host=user.host, token=user.token, userID=user.id, name=playlistName, songs=tapeSongIds, verbose=False)
            else:
                print("Somehow tape {} for {} ended with 0 songs, despite my best efforts.".format(tapeCount, user.name))
            print("Done tape {} for {}.".format(tapeCount, user.name))
            tapeCount = tapeCount + 1
        # Logic end
        try:
            newUserPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
        except Exception as e:
            print("Couldn't get playlists for {}.\nProbably an error worth fixing before setting up your own custom job.".format(user.name))
            print(e)
            newUserPlaylists = {"Items": []}
        newPlaylistHash = hashlib.md5(json.dumps(newUserPlaylists).encode("utf-8")).hexdigest()
        saveMixtapHash(userID=user.id, hash=newPlaylistHash)
        print("Saved hash for playlists now that mixtapes for {} are built".format(user.name))
    else:
        print("Mixtapes for {} are only {}s old and they expire at {}s.".format(user.name, mixtapeAge, tapeExpiry))
print("Mixtape builder done.")
            