import json
import os
import random
import traceback

from datetime import datetime

from lib import audiomuse, jellyfin, db, common
from lib.common import UserInfo

userCount = common.getUserCount()

playlists = common.getPlaylists()
maxAge = 84600
currentTimeStamp = int(datetime.now().timestamp())

# If the an alchemy song has been listened to within this time
# it's not considered 'fresh'
playbackHistoryLimitDays = 365

# Normally, a song is only "played" if you've heard at least 80%
# of it. This allows alchemy songs to be considered as "played"
# with any percentage
alchemyPlaybackUnderEighty = True

print("Found {} users and {} playlists.".format(userCount, len(playlists)))
for playlist in playlists:
    print("Trying to build '{}' for user '{}'.".format(playlist["name"], playlist["userID"]))
    userInfo = common.getUserInfo(playlist["userID"])
    alchemySongAmount = int(playlist["songCount"] * (playlist["alchemyPercent"] / 100))
    normalSongAmount = playlist["songCount"] - alchemySongAmount
    if userInfo is None:
        print("Somehow userID {} has a playlist but isn't registered".format(playlist["userID"]))
        print("Error: Not able to build playlist {} for userID {}".format(playlist["name"], playlist["userID"]))
    else:
        userBans = common.getUserBans(userID=userInfo.id)
        userLimits = common.getUserLimits(userID=userInfo.id)
        playlistName = "{}{}".format(playlist["name"], os.environ['PLAYLIST_SUFFIX'])
        buildPlaylist = False
        reason = "Error. The somehow couldn't tell if the playlist existed or how old it might be. See logs."
        playlistExists = common.playlistExists(userInfo=userInfo, playlistName=playlistName)
        if playlistExists:
            playlistBuildTime = common.playlistBuildTime(userInfo=userInfo, playlistName=playlistName)
            playlistAge = currentTimeStamp - playlistBuildTime
            if playlistAge > maxAge:
                buildPlaylist = True
                reason = "Existing version is {} seconds old".format(playlistAge)
            else:
                reason = "Exsting playlist is fresh."
        else:
            buildPlaylist = True
            reason = "Playlist {} doesn't currently exist for {}.".format(playlist["name"], userInfo.name)
        if buildPlaylist == False:
            print("Not building playlist {} for {} due to reason: {}".format(playlist["name"], userInfo.name, reason))
        else:
            print("Building new version of {} because of reason: {}".format(playlist["name"], reason))
            albumsUsed = []
            artistsUsed = []
            playlistSongIDs = []
            alchemyInputs = []
            # Now get the source songs for the playlist
            try:
                # Getting recent plays depends on the jellyfin user
                # being allowed to use PlaybackReporting which is 
                # only possible with admin rights.
                # I'll warn users about this, but the script
                # should also account for people ignoring that                
                recents = jellyfin.recentPlays(host=userInfo.host, token=userInfo.token, userID=userInfo.id)
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
                    else:
                        if song["Id"] not in alchemyInputs:
                            alchemyInputs.append(song["Id"])
                    if albumsUsed.count(song["Album"]) >= userLimits["sameAlbumLimit"]:
                        allowed = False
                    for artist in song["Artists"]:
                        if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                            allowed = False
                    if song["Id"] in playlistSongIDs:
                        allowed = False
                    if playlist["recents"] != "true":
                        allowed = False
                    if allowed:
                        albumsUsed.append(song["Album"])
                        for artist in song["Artists"]:
                            artistsUsed.append(artist)
                        playlistSongIDs.append(song["Id"])
            except Exception:
                print("Error: Couldn't get recent plays.")
                traceback.print_exc()
            # Get favourites for the user    
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
                else:
                    if song["Id"] not in alchemyInputs:
                        alchemyInputs.append(song["Id"])
                if albumsUsed.count(song["Album"]) >= userLimits["sameAlbumLimit"]:
                    allowed = False
                for artist in song["Artists"]:
                    if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                        allowed = False
                if playlist["favourites"] != "true":
                    allowed = False
                if song["Id"] in playlistSongIDs:
                    allowed = False
                if allowed:
                    albumsUsed.append(song["Album"])
                    for artist in song["Artists"]:
                        artistsUsed.append(artist)
                    playlistSongIDs.append(song["Id"])
            # Fingerprint songs
            songs = audiomuse.sonicFingerprint(userID=userInfo.id, userToken=userInfo.token, songCount=int(playlist["songCount"]))
            print("Got back {} tracks from audiomuse".format(len(songs)))
            random.shuffle(songs)
            for song in songs:
                try:
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
                    else:
                        if jellyfinItem["Id"] not in alchemyInputs:
                            alchemyInputs.append(jellyfinItem["Id"])
                    if albumsUsed.count(jellyfinItem["Album"]) >= userLimits["sameAlbumLimit"]:
                        allowed = False
                    for artist in jellyfinItem["Artists"]:
                        if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                            allowed = False
                    if playlist["fingerprint"] != "true":
                        allowed = False
                    if song["item_id"] in playlistSongIDs:
                        allowed = False
                    if allowed:
                        albumsUsed.append(song["album"])
                        artistsUsed.append(song["author"])
                        playlistSongIDs.append(song["item_id"])
                except Exception:
                    traceback.print_exc()
                    print("Couldn't parse: {}".format(json.dumps(song)))
            # Bulid the playlist
            # Until now, everything's gone via playlistSongIDs. That all changes.
            # In order to make sure the number of alchemy songs ends up correct,
            # I slice playlistSongIDs down to playlistSongs now, then just top
            # it up with alchemy songs until I've hit the limit.
            # Add the user's playback history/favourites/fingerprint songs first
            if len(playlistSongIDs) > 0:
                print("Got {} total options for the Jellyfin playlist".format(len(playlistSongIDs)))
                if len(playlistSongIDs) > normalSongAmount:
                    # In this case, the user has more candidate songs than we need
                    # song just grabbing a random sample is perfect
                    playlistSongs = random.sample(playlistSongIDs, normalSongAmount)
                else:
                    playlistSongs = playlistSongIDs
                    # Now the user didn't have enough songs based on recent plays,
                    # favourites, and fingerprint songs.
                    # So we'll pad the alchemy numbers to make up for it.
                    alchemySongAmount = alchemySongAmount + (normalSongAmount - len(playlistSongIDs))
            else:
                playlistSongs = []
            # Now it's time for alchemy
            # Based only on the actual songs we could have put in the playlist
            # we do some alchemy to get what else we need. Can't use what is in
            # the playlist so far, as the user might have set alchemy to 100%
            alchemySongs = audiomuse.alchemy(addSongs=alchemyInputs, songLimit=(alchemySongAmount * 5))
            alchemySongCount = 0
            random.shuffle(alchemySongs)
            for song in alchemySongs:
                try:
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
                    plays = jellyfin.songPlayCount(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemId=jellyfinItem["Id"], dayLimit=playbackHistoryLimitDays, includePartial=alchemyPlaybackUnderEighty)
                    if (plays > 0) and (playlist["freshAlchemy"] == "true"):
                        allowed = False
                    if albumsUsed.count(jellyfinItem["Album"]) >= userLimits["sameAlbumLimit"]:
                        allowed = False
                    for artist in jellyfinItem["Artists"]:
                        if artistsUsed.count(artist) >= userLimits["sameArtistLimit"]:
                            allowed = False
                    if song["item_id"] in playlistSongIDs:
                        allowed = False
                    if alchemySongCount >= alchemySongAmount:
                        allowed = False
                    if allowed:
                        albumsUsed.append(song["album"])
                        artistsUsed.append(song["author"])
                        playlistSongs.append(song["item_id"])
                        alchemySongCount = alchemySongCount + 1
                except Exception as e:
                    traceback.print_exc()
                    print("Couldn't parse: {}".format(json.dumps(song)))
            print("Creating playlist {} with {} items, including {} alchemy tracks, for {}.".format(playlistName, len(playlistSongs), alchemySongCount, userInfo.name))
            jellyfin.playlistSetup(host=userInfo.host, name=playlistName, token=userInfo.token, userID=userInfo.id, songs=playlistSongs, verbose=False)
            common.setPlaylistBuildTime(timestamp=currentTimeStamp, name=playlistName, userID=userInfo.id, build=True, reason=reason)
        
        