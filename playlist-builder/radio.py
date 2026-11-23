import hashlib
import json
import os
import random
import sys

from collections import Counter
from datetime import datetime

from lib import audiomuse, db, common, jellyfin

def resetMixTapes(user:common.UserInfo, playlistSuffix:str, serverPlaylist:str) -> None:
    userPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
    for playlist in userPlaylists["Items"]:
        if playlist["Name"] != serverPlaylist:
            if playlistSuffix in playlist["Name"]:
                jellyfin.deletePlaylist(host=user.host, token=user.token, userID=user.token, playlistID=playlist["Id"])

def alchemyListExension(user:common.UserInfo, albumsUsed:list, artistsUsed:list, userLimits:dict, playlistSongs:list[dict], limit:int):
    journeySongs = []
    for song in playlistSongs:
        journeySongs.append(song["Id"])
    alchemyTracks = audiomuse.alchemy(addSongs=journeySongs, songLimit=limit)
    for amSong in alchemyTracks:
        jfItem = jellyfin.item(host=user.host, token=user.token, userID=user.id, itemID=amSong["item_id"])
        allowed = True
        songIds = []
        songIds.append(jfItem["Id"])
        songIds.append(jfItem["AlbumId"])
        for genre in jfItem.get("GenreItems", []):
            songIds.append(genre["Id"])
        for artist in jfItem["ArtistItems"]:
            songIds.append(artist["Id"])
        for albumArtist in jfItem["AlbumArtists"]:
            songIds.append(albumArtist["Id"])
        if any(item in songIds for item in userBans):
            print("{} isn't allowed in lists for {}.".format(song["Name"], user.name))
            allowed = False
        if albumsUsed.count(song["AlbumId"]) >= userLimits["sameAlbumLimit"]:
            allowed = False
        for artist in song["ArtistItems"]:
            if artistsUsed.count(artist["Id"]) >= userLimits["sameArtistLimit"]:
                allowed = False
        if len(playlistSongs) > (limit - 1):
            allowed = False
        if allowed:
            albumsUsed.append(song["AlbumId"])
            for artist in song["ArtistItems"]:
                artistsUsed.append(artist["Id"])
            playlistSongs.append(jfItem)
    return playlistSongs

def journeyPlaylist(user:common.UserInfo, recents:list, userBans:list, usedSourceBands:list, userLimits:dict, limit:int) -> list:
    playlistSongs = []
    usableRecents = []
    albumsUsed = []
    artistsUsed = []
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
            songIds.append(jfItem["Id"])
            songIds.append(jfItem["AlbumId"])
            for genre in jfItem.get("GenreItems", []):
                songIds.append(genre["Id"])
            for artist in jfItem["ArtistItems"]:
                songIds.append(artist["Id"])
            for albumArtist in jfItem["AlbumArtists"]:
                songIds.append(albumArtist["Id"])
            if any(item in songIds for item in userBans):
                print("{} isn't allowed in lists for {}.".format(song["Name"], user.name))
                allowed = False
            if albumsUsed.count(jfItem.get("AlbumId", "none")) >= userLimits["sameAlbumLimit"]:
                allowed = False
            for artist in jfItem["ArtistItems"]:
                if artistsUsed.count(artist["Id"]) >= userLimits["sameArtistLimit"]:
                    allowed = False
            if allowed:
                albumsUsed.append(jfItem.get("AlbumId", "none"))
                for artist in jfItem["ArtistItems"]:
                    artistsUsed.append(artist["Id"])
                playlistSongs.append(jfItem)
    # I want to limit the number of repeated artists and albums, because I think that sounds
    # better, but AudioMuse-AI has no such preference. So it might give back too many repeats
    # In case that it does, we pad out the "journey" part of the playlist with some alchemy
    if len(playlistSongs) < int(0.75 * limit):
        if len(playlistSongs) < 3:
            # fewer than three songs means we're really low, and the song journey is basically a bust
            # I'll return 0 songs and the script will just build some alchemy out of recent listens
            playlistSongs = []
        else:
            endSong = playlistSongs[-1]
            playlistSongs.remove(endSong)    
            playlistSongs = alchemyListExension(user=user, albumsUsed=albumsUsed, artistsUsed=artistsUsed, userLimits=userLimits, playlistSongs=playlistSongs, limit=limit)
            playlistSongs.append(endSong)
    return playlistSongs

def artistAndFriendsPlaylist(user:common.UserInfo, userBans:list, recents:list, usedSourceBands:list, userLimits:dict, limit:int) -> dict:
    candidateArtists = []
    albumsUsed = []
    artistsUsed = []
    artistNameToID = {}
    tapeSongs = []
    for song in recents:
        for artist in song["ArtistItems"]:
            if artist["Id"] not in usedSourceBands:
                candidateArtists.append(artist["Name"])
                if artist["Name"] not in artistNameToID.keys():
                    artistNameToID[artist["Name"]] = artist["Id"]
    artist = Counter(candidateArtists).most_common(1)[0][0]
    artistId = artistNameToID[artist]
    usedSourceBands.append(artistId)
    searchTerm = "{} and similar sounding artists".format(artist)
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
        if albumsUsed.count(jellyfinItem.get("AlbumId", "none")) >= userLimits["sameAlbumLimit"]:
            allowed = False
        for artist in jellyfinItem["ArtistItems"]:
            if artistsUsed.count(artist["Id"]) >= userLimits["sameArtistLimit"]:
                allowed = False
        if allowed:
            albumsUsed.append(jellyfinItem.get("AlbumId", "none"))
            for artist in jellyfinItem["ArtistItems"]:
                artistsUsed.append(artist["Id"])
            tapeSongs.append(jellyfinItem)
    if len(tapeSongs) < int(0.75 * limit):
        tapeSongs = alchemyListExension(user=user, albumsUsed=albumsUsed, artistsUsed=artistsUsed, userLimits=userLimits, playlistSongs=tapeSongs, limit=limit)
    random.shuffle(tapeSongs)
    return {"playlistName": playlistName, "tapeSongs": tapeSongs}

def recentsToAlchemy(user:common.UserInfo, userBans:list, userLimits:dict, limit:int):
    allRecents = jellyfin.recentPlays(host=user.host, token=user.token, userID=user.id, includePartial=True)
    addSongs = []
    subtractSongs = []
    albumsUsed = []
    artistsUsed = []
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
        if albumsUsed.count(jellyfinItem.get("AlbumId", "none")) >= userLimits["sameAlbumLimit"]:
            allowed = False
        for artist in jellyfinItem["ArtistItems"]:
            if artistsUsed.count(artist["Id"]) >= userLimits["sameArtistLimit"]:
                allowed = False
        if allowed:
            albumsUsed.append(jellyfinItem.get("AlbumId", "none"))
            for artist in jellyfinItem["ArtistItems"]:
                artistsUsed.append(artist["Id"])
            playlistSongs.append(jellyfinItem)
    if len(playlistSongs) < int(0.75 * limit):
        playlistSongs = alchemyListExension(user=user, albumsUsed=albumsUsed, artistsUsed=artistsUsed, userLimits=userLimits, playlistSongs=playlistSongs, limit=limit)
    print("Turned {} recent tracks into {} songs for {}.".format(len(allRecents), len(playlistSongs), user.name))
    random.shuffle(playlistSongs)
    return playlistSongs

def getLiveMixtapeHash(user:common.UserInfo, serverPlaylist:str, playlistSuffix:str) -> str:
    customMixtapes = common.getUserPlaylists(userID=user.id)
    customTapeNames = []
    customTapeNames.append(serverPlaylist)
    for tape in customMixtapes:
        customTapeNames.append("{}{}".format(tape.name, playlistSuffix))
    try:
        newUserPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
        filteredPlaylists = []
        for playlist in newUserPlaylists["Items"]:
            if playlist["Name"] not in customTapeNames:
                if playlistSuffix in playlist["Name"]:
                    filteredPlaylists.append(playlist)
        newUserPlaylists["Items"] = filteredPlaylists
        newUserPlaylists["TotalRecordCount"] = len(filteredPlaylists)
    except Exception as e:
        print("Couldn't get playlists for {}.".format(user.name))
        print(e)
        newUserPlaylists = {"Items": []}
    newPlaylistHash = hashlib.md5(json.dumps(newUserPlaylists).encode("utf-8")).hexdigest()
    return newPlaylistHash

def getDBMixtapeHash(userID):
    q = "SELECT * FROM MixtapeHash WHERE userID = ? ORDER BY timestamp DESC LIMIT 1"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="MixtapeHash")
    if len(r) > 0:
        return r[0]
    return {"timestamp": 0}

def saveMixtapeHash(userID, hash):
    now = int(datetime.now().timestamp())
    q = "INSERT INTO MixtapeHash VALUES(?,?,?)"
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
serverPlaylistName = "{}{}".format(os.environ["SERVER_PLAYLIST"], os.environ["PLAYLIST_SUFFIX"])
for user in users:
    print("Starting mixtape job for {}.".format(user.name))
    oldMixtapeHash = getDBMixtapeHash(userID=user.id)
    currentMixtapeHash = getLiveMixtapeHash(user=user, serverPlaylist=serverPlaylistName, playlistSuffix=playlistSuffix)
    now = int(datetime.now().timestamp())
    mixtapeAge = int(now - oldMixtapeHash["timestamp"])
    rebuildTapes = False
    if mixtapeAge > tapeExpiry:
        print("The mixtapes have expired.")
        rebuildTapes = True
    if oldMixtapeHash["hash"] != currentMixtapeHash:
        print("The mixtapes didn't match the expected hash")
        rebuildTapes = True
    if rebuildTapes:
        print("Time to make new mixtapes for {}.".format(user.name))
        resetMixTapes(user=user, playlistSuffix=playlistSuffix, serverPlaylist=serverPlaylistName)
        userBans = common.getUserBans(userID=user.id)
        userLimits = common.getUserLimits(userID=user.id)
        recents = jellyfin.recentPlays(host=user.host, token=user.token, userID=user.id)
        # I don't want all the tapes to be based on the same artists so I track which
        # ones were used, and don't use them more than once.
        usedSourceBands = []
        tapesMade = 0
        while tapesMade < tapeCount:
            tapeMethod = random.randint(1, 3)
            print("Starting tape {} for {} using method {}.".format(tapesMade, user.name, tapeMethod))
            tapeSongs = []
            playlistName = "Mixtape {}{}".format(tapeCount, playlistSuffix)
            if tapeMethod == 1:
                # Method 1 - Take a journey from one song to another
                tapeSongs = journeyPlaylist(user=user, recents=recents, userBans=userBans, usedSourceBands=usedSourceBands, limit=tapeSongLimit, userLimits=userLimits)
                # The "source" artists are taken from the first and last songs
                if len(tapeSongs) > 0:
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
                    if "AlbumArtist" in startSong.keys() and "AlbumArtist" in endSong.keys():
                        playlistName = "{} to {}{}".format(startSong["AlbumArtist"], endSong["AlbumArtist"], playlistSuffix)
                    else:
                        playlistName = "{} to {}{}".format(startSong["Name"], endSong["Name"], playlistSuffix)
            if tapeMethod == 2:
                # Method 2 - Make a tape based on some artist the user has
                # been listening to
                i = artistAndFriendsPlaylist(user=user, recents=recents, userBans=userBans, userLimits=userLimits, limit=tapeSongLimit, usedSourceBands=usedSourceBands)
                playlistName = i["playlistName"]
                tapeSongs = i["tapeSongs"]
            # This is a fallback option. But it's also deliberately called with tapeMethod 3
            if len(tapeSongs) == 0:
                tapeSongs = recentsToAlchemy(user=user, userBans=userBans, userLimits=userLimits, limit=tapeSongLimit)
                playlistName = "{} Alchemy{}".format(tapeSongs[0]["AlbumArtist"], playlistSuffix)
            if len(tapeSongs) > 0:
                # At this point, the tapeSongs list has the songs we need
                # and the playlist has a name.
                tapeSongIds = []
                for song in tapeSongs:
                    tapeSongIds.append(song["Id"])
                print("Setting up {} for {} with {} songs".format(playlistName, user.name, len(tapeSongIds)))
                jellyfin.playlistSetup(host=user.host, token=user.token, userID=user.id, name=playlistName, songs=tapeSongIds, verbose=False)
            else:
                print("Somehow tape {} for {} ended with 0 songs, despite my best efforts.".format(tapesMade, user.name))
            print("Done tape {} for {}.".format(tapesMade, user.name))
            tapesMade = tapesMade + 1
        # Logic end
        newPlaylistHash = getLiveMixtapeHash(user=user, serverPlaylist=serverPlaylistName, playlistSuffix=playlistSuffix)
        saveMixtapeHash(userID=user.id, hash=newPlaylistHash)
        print("Saved hash for playlists now that mixtapes for {} are built".format(user.name))
    else:
        print("Mixtapes for {} are only {}s old and they expire at {}s.".format(user.name, mixtapeAge, tapeExpiry))
print("Mixtape builder done.")
            