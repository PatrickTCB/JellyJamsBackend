import os
import random
import threading

from fastapi import FastAPI, Form, Request, Response, HTTPException

from datetime import datetime
from pydantic import BaseModel
from typing import Annotated, List
from zoneinfo import ZoneInfo

from lib import db, jellyfin, audiomuse, common
from lib.common import UserInfo, PlaylistInfo

class ErrorResponse(BaseModel):
    detail: str = ""
class UserCreated(BaseModel):
    User:str = ""
    Created:bool = False
    Saved:bool = False
    Code:str = ""
    PlaylistSuffix:str = "_automatic"
    ServerPlaylist:str = ""
class UserInfoMinimal(BaseModel):
    name:str = ""
    id:str = ""
class UserLimits(BaseModel):
    id:str = ""
    sameArtistLimit:int = 1
    sameAlbumLimit:int = 1
class UserServerPlaylistStatus(BaseModel):
    id:str = ""
    inServerPlaylist:bool = False
class PlaylistCreated(BaseModel):
    Created:bool = False
    Updated:bool = False
    Details:PlaylistInfo = PlaylistInfo()
class PlaylistDeleted(BaseModel):
    Deleted:bool = True
    Name:str = ""
class UserPlaylistInfo(BaseModel):
    User:UserInfoMinimal = UserInfoMinimal()
    Playlists:List[PlaylistInfo] = []
class ExtendedQueue(BaseModel):
    NewTrackIDs:List[str] = []
    Count:int = 0
class ItemsBanned(BaseModel):
    Items:dict = {}
    Success:bool = False
    AlreadyBanned:bool = False
class PingPong(BaseModel):
    message:str = "pong"
    now:int = 0

def serverPlaylistStatus(userID:str) -> bool:
    q = "SELECT * FROM ServerPlaylist WHERE userID = ?"
    d = (userID,)
    r = db.select(query=q, datatuple=d, tableName="ServerPlaylist")
    if len(r) > 0:
        return True
    else:
        return False

def serverPlaylistSignup(userID:str):
    q = "DELETE FROM ServerPlaylist WHERE userID = ?"
    d = (userID,)
    db.delete(query=q, datatuple=d, tableName="ServerPlaylist")
    q = "INSERT INTO ServerPlaylist VALUES(?)"
    db.insert(query=q, datatuple=d, tableName="ServerPlaylist")

def serverPlaylistRemoval(userID:str):
    q = "DELETE FROM ServerPlaylist WHERE userID = ?"
    d = (userID,)
    db.delete(query=q, datatuple=d, tableName="ServerPlaylist")

def saveUserInfo(userID:str, userName:str, userToken:str, jellyfinHost:str):
    q = "DELETE FROM Users WHERE id = ?"
    d = (userID,)
    db.delete(query=q, datatuple=d, tableName="Users")
    q = "INSERT INTO Users VALUES(?,?,?,?)"
    d = (userID,userName,userToken,jellyfinHost)
    db.insert(query=q, datatuple=d, tableName="Users")

def quickConnect(host:str, secret:str, userName:str, userID:str):
    print("Starting quick connect process for {}".format(userName))
    retry = True
    check = jellyfin.quickConnectCheck(host=host, secret=secret)
    while retry:
        if check["Authenticated"]:
            print("Authentication worked.")
            retry = False
    auth = jellyfin.quickConnectAuthorize(host=host, secret=secret, userID=userID)
    print("Saving authentication info for {}".format(auth["User"]["Name"]))
    saveUserInfo(userID=auth["User"]["Id"], userName=auth["User"]["Name"], userToken=auth["AccessToken"], jellyfinHost=host)
    pass

def deleteUser(userID:str, userName:str, userToken:str, jellyfinHost:str):
    q = "DELETE FROM Users WHERE id = ? AND userName = ? AND userToken = ? AND jellyfinHost = ?"
    d = (userID,userName,userToken,jellyfinHost)
    db.delete(query=q, datatuple=d, tableName="Users")
    # Delete from other tables
    tables = ["ServerPlaylist", "Bans", "Playlists", "PlaylistBuilds", "userLimits"]
    for table in tables:
        q = "DELETE FROM {} WHERE id = ?".format(table)
        d = (userID,)
        db.delete(query=q, datatuple=d, tableName=table)

def banForUser(userID:str, itemID:str):
    q = "INSERT INTO Bans VALUES(?,?)"
    d = (userID,itemID,)
    db.insert(query=q, datatuple=d, tableName="Bans")

def checkForExistingBan(userID:str, itemID:str) -> bool:
    q = "SELECT * FROM Bans WHERE userID = ? AND id = ?"
    d = (userID,itemID,)
    r = db.select(query=q, datatuple=d, tableName="Bans")
    if len(r) > 0:
        return True
    else:
        return False

def unBanForUser(userID:str, itemID:str = ""):
    q = "DELETE FROM Bans WHERE userID = ? AND id = ?"
    d = (userID,itemID,)
    if itemID == "":
        q = "DELETE FROM Bans WHERE userID = ?"
        d = (userID,)    
    db.delete(query=q, datatuple=d, tableName="Bans")

def setUserLimits(userID:str, sameAlbumLimit:int, sameArtistLimit:int):
    # Delete any existing limitsCheck to see if this user already has limits
    q = "DELETE FROM userLimits WHERE userID = ?"
    d = (userID,)
    db.delete(query=q, datatuple=d, tableName="userLimits")
    # Set the new limits
    q = "INSERT INTO userLimits VALUES(?,?,?)"
    d = (userID,sameAlbumLimit,sameArtistLimit)
    db.insert(query=q, datatuple=d, tableName="userLimits")

def savePlaylistInfo(userID:str, name:str, recents:bool, favourites:bool, fingerprint:bool, alchemyPercent:int, freshAlchemy:bool, songCount:int, newPlaylist:bool) -> PlaylistInfo:
    p = PlaylistInfo()
    if newPlaylist == False:
        # If this playlist already exists, the cleanest thing is to just delete it from the table
        # and make it again. Since I don't care to actually diff the old and new or anything
        q = "DELETE FROM Playlists WHERE userID = ? AND name = ?"
        d = (userID,name,)
        db.delete(query=q, datatuple=d, tableName="Playlists")
    # Now I can create the playlist. Flags are stored lower-cased because
    # that's what the playlist builder compares them against ("true"), and
    # the columns arrive in the custodian's table order: the fresh-alchemy
    # switch sits between the alchemy percentage and the song count.
    q = "INSERT INTO Playlists VALUES(?,?,?,?,?,?,?,?)"
    d = (userID,name,str(recents).lower(),str(favourites).lower(),str(fingerprint).lower(),alchemyPercent,str(freshAlchemy).lower(),songCount,)
    db.insert(query=q, datatuple=d, tableName="Playlists")
    p.userID = userID
    p.name = name
    p.recents = str(recents).lower()
    p.favourites = str(favourites).lower()
    p.fingerprint = str(fingerprint).lower()
    p.alchemyPercent = alchemyPercent
    p.freshAlchemy = str(freshAlchemy).lower()
    p.songCount = songCount
    return p

def getJellyfinSimilarArtists(userInfo: UserInfo, artistID:str) -> list:
    similarArtists = []
    jfArtists = jellyfin.getSimilarArtists(host=userInfo.host, token=userInfo.token, userID=userInfo.id, artistId=artistID, limit=10)
    for jfArtist in jfArtists["Items"]:
        artist = {}
        artist["artist_id"] = jfArtist["Id"]
        artistTracks = 0
        artistExtraParams = {
            "parentId": jfArtist["Id"],
            "sortOrder": "Ascending",
            "includeItemTypes": "MusicAlbum",
            "sortBy": "PremiereDate"
        }
        artistAlbums = jellyfin.getItemBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, extraParams=artistExtraParams)
        for album in artistAlbums["Items"]:
            albumExtraParams = {
                "parentId": album["Id"],
                "sortOrder": "Ascending",
                "includeItemTypes": "Audio",
                "sortBy": "IndexNumber"
            }
            albumTracks = jellyfin.getItemBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, extraParams=albumExtraParams)
            artistTracks = artistTracks + len(albumTracks["Items"])
        artist["track_count"] = artistTracks
        similarArtists.append(artist)
    return similarArtists

def getNextAlbum(userInfo:UserInfo, albumID:str) -> str:
    nextAlbumID = ""
    userBans = common.getUserBans(userID=userInfo.id)
    # First, get the album the user is currently listening too
    albumInfo = jellyfin.item(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemID=albumID)
    if albumInfo["Type"] != "MusicAlbum":
        # TODO thing of something smart to do here.
        # This theoretically shouldn't happen, but it's
        # good to be able to actually do something
        print("For some reason id '{}' ('{}') is a '{}' instead of a 'MusicAlbum'".format(albumID, albumInfo["Name"], albumInfo["Type"]))
    else:
        # Got the album, and have confirmed it's an album
        # Option 1 for the next album is just the next album
        # that artist released
        extraParams = {
            "parentId": albumInfo["ParentId"],
            "sortOrder": "Ascending",
            "includeItemTypes": "MusicAlbum",
            "sortBy": "PremiereDate"
        }
        otherAlbums = jellyfin.getItemBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, extraParams=extraParams)
        foundCurrent = False
        print("Found {} total albums by {}".format(len(otherAlbums["Items"]), albumInfo["AlbumArtist"]))
        for album in otherAlbums["Items"]:
            # Check to see if I found the current one yet
            if foundCurrent:
                # Respect the user's bans
                if album["Id"] not in userBans:
                    print("Next album by {} after {} is {}. Returning that now.".format(albumInfo["AlbumArtist"], albumID, album["Id"]))
                    nextAlbumID = album["Id"]
                    return nextAlbumID
                else:
                    print("Technically, {} is the next album. But it's banned, so I'm skipping it.".format(album["Id"]))
            if album["Id"] == albumID:
                # By setting this to true now, on this album
                # it means that on the next lap (if there is one)
                # it'll be this artists next album, and that's what
                # we should return
                foundCurrent = True
        try:
            # At this point in the code path, there is no valid "next"
            # album by this artist. So I'll get a random album from 
            # a similar artist
            similarArtists = audiomuse.similarArtists(artistName=albumInfo["AlbumArtist"], numberOfArtists=10)
        except Exception as e:
            print("Couldn't get similar artists from audiomuse. I'll try getting them from Jellyfin.")
        if len(similarArtists) == 0:
            similarArtists = getJellyfinSimilarArtists(userInfo=userInfo, artistID=albumInfo["ParentId"])
            print("Got {} similar artists from Jellyfin.".format(len(similarArtists)))
        candidateAlbums = []
        print("Found {} similar artists. Checking for albums with at least 5 songs.".format(len(similarArtists)))
        for artist in similarArtists:
            # Respect the user's bans
            bannedArtist = bool(artist["artist_id"] in userBans)
            # Some artists only have one song, and not an album.
            # So limit it to artists with at least 5 songs means
            # we won't just end up in a loop of constantly adding
            # only one or two songs instead of an album.
            if artist["track_count"] > 5 and bannedArtist == False:
                artistExtraParams = {
                    "parentId": artist["artist_id"],
                    "sortOrder": "Ascending",
                    "includeItemTypes": "MusicAlbum",
                    "sortBy": "PremiereDate"
                }
                artistAlbums = jellyfin.getItemBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, extraParams=artistExtraParams)
                for album in artistAlbums["Items"]:
                    albumExtraParams = {
                        "parentId": album["Id"],
                        "sortOrder": "Ascending",
                        "includeItemTypes": "Audio",
                        "sortBy": "IndexNumber"
                    }
                    albumTracks = jellyfin.getItemBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, extraParams=albumExtraParams)
                    # Respect the users bans
                    # For now, I allow an album with one or more
                    # banned songs to come up next, because the album
                    # itself isn't banned, just the song. 
                    # This might change later depending on how it feels
                    # to use
                    bannedAlbum = bool(album["Id"] in userBans)
                    # Same logic as the artist song check.
                    # No point sending a small album back to just
                    # do this again
                    if len(albumTracks["Items"]) > 5 and bannedAlbum == False:
                        candidateAlbums.append(album["Id"])
        print("Found {} candidate albums from the artists.".format(len(candidateAlbums)))
        if len(candidateAlbums) > 0:
            nextAlbumID = random.choice(candidateAlbums)
    return nextAlbumID
    
def getTracksIDsFromAlbum(userInfo:UserInfo, albumID:str) -> list:
    albumTrackIDs = []
    albumExtraParams = {
        "parentId": albumID,
        "sortOrder": "Ascending",
        "includeItemTypes": "Audio",
        "sortBy": "IndexNumber"
    }
    albumTracks = jellyfin.getItemBySearch(host=userInfo.host, token=userInfo.token, userID=userInfo.id, extraParams=albumExtraParams)
    for track in albumTracks["Items"]:
        albumTrackIDs.append(track["Id"])
    print("Found {} tracks for album id {}".format(len(albumTrackIDs), albumID))
    return albumTrackIDs

def alchemySongs(userInfo:UserInfo, sourceSongs:list[str], songLimit:int):
    userBans = common.getUserBans(userID=userInfo.id)
    # Search for twice as many songs as we need, as we'll ignore ones the users has banned
    # and we don't want to return too few songs.
    alchemyAdd = []
    alchemySubtract = []
    for song in sourceSongs:
        lastAction = jellyfin.songLastPlay(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemId=song)
        if lastAction == "PLAY":
            alchemyAdd.append(song)
        else:
            alchemySubtract.append(song)
    try:
        alchemySongs = audiomuse.alchemy(addSongs=alchemyAdd, subtractSongs=alchemySubtract, songLimit=(int(songLimit * 2)))
    except Exception as e:
        print("Couldn't get alchemy songs from audiomuse. Check the logs of that container")
        alchemySongs = []
    alchemySongIDs = []
    for song in alchemySongs:
        # Respect the user's bans
        banned = False
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
            banned = True
        if banned:
            try:
                print("Skipping alchemy song '{}' by '{}' because it's banned".format(jellyfinItem["Name"], ", ".join(jellyfinItem["Artists"])))
            except Exception as e:
                print("Couldn't properly right error message about skipping: {}\n{}".format(song, e))
        else:
            alchemySongIDs.append(song["item_id"])
    if len(alchemySongIDs) == 0:
        print("Ended with 0 permitted alchemy songs.")
        print("Grabbing 2 favourites")
        rawFavs = jellyfin.favourites(host=userInfo.host, token=userInfo.token, userID=userInfo.id)
        favs = []
        for song in rawFavs["Items"]:
            favs.append(song["Id"])
        if len(favs) > 2:
            alchemySongIDs = random.sample(favs, 2)
    if len(alchemySongIDs) > songLimit:
        return random.sample(alchemySongIDs, songLimit)
    else:
        return alchemySongIDs

app = FastAPI()

@app.get("/ping", response_model=PingPong)
async def ping(request:Request) -> PingPong:
    # Users call this to see if the server exists and can be reached.
    if request.client != None:
        print("Ping from {}.".format(request.client.host))
    xff = request.headers.get("x-forwarded-for", "")
    if xff != "":
        print("Ping x_forwarded_for: {}".format(xff))
    r = PingPong()
    r.message = "pong"
    r.now = int(datetime.now().timestamp())
    print("Pong at {}.".format(r.now))
    return r

@app.get("/tapes", response_model=UserPlaylistInfo, responses={404: {"description": "User not found", "model": ErrorResponse}})
async def get_playlists(request:Request, userID:str) -> UserPlaylistInfo:
    # Check to see if the user exists
    userInfo = common.getUserInfo(userID)
    if userInfo is None:
        print("User {} could not be found".format(userID))
        raise HTTPException(status_code=404, detail="User {} not found".format(userID))
    # User does exist
    print("Getting playlists for {}.".format(userID))
    r = UserPlaylistInfo()
    r.User.name = userInfo.name
    r.User.id = userInfo.id
    r.Playlists = common.getUserPlaylists(userID = userInfo.id)
    print("Got {} playlists.".format(len(r.Playlists)))
    return r

@app.post("/new-tape", status_code=201, response_model=PlaylistCreated, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def new_playlist(request:Request, userID:Annotated[str, Form()], name:Annotated[str, Form()], recents:Annotated[bool, Form()], favourites:Annotated[bool, Form()], fingerprint:Annotated[bool, Form()], alchemyPercent:Annotated[int, Form()], freshAlchemy:Annotated[bool, Form()], songCount:Annotated[int, Form()]):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't create playlist {} for {} as it looks like {} doesn't exist.".format(name, userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    print("Creating {} for user {}".format(name, userID))
    playlists = common.getUserPlaylists(userID=userID)
    newPlaylist = True
    for playlist in playlists:
        if playlist["name"] == name:
            newPlaylist = False
            print("This playlist actually already exists, so it will be removed and re-created.")
    p = savePlaylistInfo(userID=userID, name=name, recents=recents, favourites=favourites, fingerprint=fingerprint, alchemyPercent=alchemyPercent, freshAlchemy=freshAlchemy, songCount=songCount, newPlaylist=newPlaylist)
    r = PlaylistCreated()
    r.Created = True
    r.Updated = bool(newPlaylist == False)
    r.Details = p
    return r

@app.delete("/delete-tape", status_code=200, response_model=PlaylistDeleted, responses={401: {"description": "User invalid", "model": ErrorResponse}, 404: {"description": "Playlist not found", "model": ErrorResponse}})
async def delete_playlist(request:Request, userID:str, name:str):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Cannot delete {} for {} is it looks like the user {} does not exist.".format(name, userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    playlists = common.getUserPlaylists(userID=userID)
    for playlist in playlists:
        if playlist["name"] == name:
            print("Found {} for user {}. Deleteing it.".format(name, userID))
            q = "DELETE FROM Playlists WHERE userID = ? AND name = ?"
            d = (userID,name,)
            db.delete(query=q, datatuple=d, tableName="Playlists")
            r = PlaylistDeleted()
            r.Name = name
            r.Deleted = True
            return r
    raise HTTPException(status_code=404, detail="Can't find playlist {} for user {}".format(name, userID))

@app.get("/extend-queue", response_model=ExtendedQueue, responses={404: {"description": "User not found", "model": ErrorResponse}})
async def extend_queue(request:Request, userID:str, existingQueue:str) -> ExtendedQueue:
    extendBy = 5
    existingQueueList = existingQueue.split(",")
    print("Will try to extend the exsiting queue of {} song s with {} more.".format(len(existingQueueList), extendBy))
    # Check to see if the user exists
    userInfo = common.getUserInfo(userID)
    if userInfo is None:
        print("User {} could not be found".format(userID))
        raise HTTPException(status_code=404, detail="User {} not found".format(userID))
    # User does exist
    # Alchemy requires at least 2 songs, but a user might actually just send one
    # so I should handle that possibility right away
    if len(existingQueueList) < 2:
        print("Existing queue was only {} song(s) long and alchemy requires 2 or more songs. Grabbing 2 favourites".format(len(existingQueueList)))
        rawFavs = jellyfin.favourites(host=userInfo.host, token=userInfo.token, userID=userInfo.id)
        NewTrackIDs = []
        favs = []
        for song in rawFavs["Items"]:
            favs.append(song["Id"])
        if len(favs) > 2:
            NewTrackIDs = random.sample(favs, 2)
        else:
            NewTrackIDs = favs
        r = ExtendedQueue()
        r.NewTrackIDs = NewTrackIDs
        r.Count = len(r.NewTrackIDs)
        return r
    # If I'm here, then the users queue is over 2 and needs up to 5 more songs
    r = ExtendedQueue()
    r.NewTrackIDs = alchemySongs(userInfo=userInfo, sourceSongs=existingQueueList, songLimit=extendBy)
    r.Count = len(r.NewTrackIDs)
    print("Got {} songs to extend the queue for {} with.".format(len(r.NewTrackIDs), userID))
    return r

@app.get("/extend-queue-by-album", response_model=ExtendedQueue, responses={404: {"description": "User not found", "model": ErrorResponse}})
async def extend_queue_by_album(request:Request, userID:str, currentAlbumID:str) -> ExtendedQueue:
    # Check to see if the user exists
    userInfo = common.getUserInfo(userID)
    nextAlbumTracks = []
    if userInfo is None:
        print("User {} could not be found".format(userID))
        raise HTTPException(status_code=404, detail="User {} not found".format(userID))
    # User does exist
    # Now the user is listening to an album, and wants another one to
    # listen to next. 
    nextAlbum = getNextAlbum(userInfo=userInfo, albumID=currentAlbumID)
    print("Got '{}' by as the next album due up".format(nextAlbum))
    if nextAlbum != "":
        nextAlbumTracks = getTracksIDsFromAlbum(userInfo=userInfo, albumID=nextAlbum)
    # Backup alchemy songs
    # In case there are no songs by now, I'll just do alchemy based on the current album to give the user something
    if len(nextAlbumTracks) == 0:
        print("I'll need to get random alchemy songs since my 'next album' idea didn't work.")
        currentAlbumTracks = getTracksIDsFromAlbum(userInfo=userInfo, albumID=currentAlbumID)
        nextAlbumTracks = alchemySongs(userInfo=userInfo, sourceSongs=currentAlbumTracks, songLimit=5)
        print("Found {} alchemy songs. That'll do for now.".format(len(nextAlbumTracks)))
    r = ExtendedQueue()
    r.NewTrackIDs = nextAlbumTracks
    r.Count = len(nextAlbumTracks)
    print("Got {} songs to extend the queue for {} with.".format(len(nextAlbumTracks), userID))
    return r

@app.post("/register", status_code=201, response_model=UserCreated, responses={200: {"description": "User already registered", "model": UserCreated}, 401: {"description": "User invalid", "model": ErrorResponse}})
async def new_user(requset:Request,response: Response, userName:Annotated[str, Form()], userID:Annotated[str, Form()], userToken:Annotated[str, Form()], jellyfinHost:Annotated[str, Form()]) -> UserCreated:
    print("Checking to see if {} has been registered yet.".format(userID))
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is not None:
        print("User {} already exists.".format(userID))
        qc = jellyfin.quickConnectInitialize(host=jellyfinHost, userID=userID)
        thread = threading.Thread(target=quickConnect, args=(jellyfinHost, qc["Secret"], userName, userID))
        thread.start()
        r = UserCreated()
        r.User = userName
        r.Created = False
        r.Saved = True
        r.Code = qc["Code"]
        r.PlaylistSuffix = os.environ["PLAYLIST_SUFFIX"]
        r.ServerPlaylist = os.environ["SERVER_PLAYLIST"]
        response.status_code = 200
        return r
    # User does not exist
    print("Creating user {}.".format(userID))
    user = jellyfin.credentialCheck(host=jellyfinHost, token=userToken, userID=userID)
    if "Id" in user.keys():
        if user["Id"] == userID:
            print("Credentials for {} seem valid and will be saved.".format(userName))
            qc = jellyfin.quickConnectInitialize(host=jellyfinHost, userID=userID)
            thread = threading.Thread(target=quickConnect, args=(jellyfinHost, qc["Secret"], userName, userID))
            thread.start()
            r = UserCreated()
            r.User = userName
            r.Created = True
            r.Saved = True
            r.Code = qc["Code"]
            r.PlaylistSuffix = os.environ["PLAYLIST_SUFFIX"]
            r.ServerPlaylist = os.environ["SERVER_PLAYLIST"]
            return r
    raise HTTPException(status_code=401, detail="User credentials submitted for {} could not be validated".format(userName))

@app.delete("/delete-me", status_code=200, response_model=UserCreated, responses={200: {"description": "User not registered", "model": UserCreated}, 401: {"description": "User invalid", "model": ErrorResponse}})
async def delete_user(requset:Request,response: Response, userName:str, userID:str, userToken:str, jellyfinHost:str) -> UserCreated:
    print("Checking to see if {} has been registered yet.".format(userID))
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("User {} does not exist.".format(userID))
        r = UserCreated()
        r.User = userName
        r.Created = False
        r.Saved = False
        r.PlaylistSuffix = os.environ["PLAYLIST_SUFFIX"]
        r.ServerPlaylist = os.environ["SERVER_PLAYLIST"]
        response.status_code = 200
        return r
    # User does not exist
    print("Deleting user {}.".format(userID))
    user = jellyfin.credentialCheck(host=jellyfinHost, token=userToken, userID=userID)
    if "Id" in user.keys():
        if user["Id"] == userID:
            print("Credentials for {} seem valid and will be deleted.".format(userName))
            deleteUser(userID=userID, userName=userName, userToken=userToken, jellyfinHost=jellyfinHost)
            r = UserCreated()
            r.User = userName
            r.Created = False
            r.Saved = False
            r.PlaylistSuffix = os.environ["PLAYLIST_SUFFIX"]
            r.ServerPlaylist = os.environ["SERVER_PLAYLIST"]
            return r
    raise HTTPException(status_code=401, detail="User credentials submitted for {} could not be validated".format(userName))

@app.post("/limits", status_code=201, response_model=UserLimits, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def set_limits(requset:Request,response: Response, userID:Annotated[str, Form()], sameAlbumLimit:Annotated[int, Form()], sameArtistLimit:Annotated[int, Form()]) -> UserLimits:
    # Check to see if the user exists
    userInfo = common.getUserInfo(userID)
    if userInfo is None:
        print("User {} could not be found".format(userID))
        raise HTTPException(status_code=401, detail="User {} not valid".format(userID))
    setUserLimits(userID=userID, sameAlbumLimit=sameAlbumLimit, sameArtistLimit=sameArtistLimit)
    limits = common.getUserLimits(userID=userID)
    r = UserLimits()
    r.id = userID
    r.sameArtistLimit = limits["sameArtistLimit"]
    r.sameAlbumLimit = limits["sameAlbumLimit"]
    return r

@app.get("/limits", status_code=201, response_model=UserLimits, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def get_limits(requset:Request,response: Response, userID:str) -> UserLimits:
    # Check to see if the user exists
    userInfo = common.getUserInfo(userID)
    if userInfo is None:
        print("User {} could not be found".format(userID))
        raise HTTPException(status_code=401, detail="User {} not valid".format(userID))
    limits = common.getUserLimits(userID=userID)
    r = UserLimits()
    r.id = userID
    r.sameArtistLimit = limits["sameArtistLimit"]
    r.sameAlbumLimit = limits["sameAlbumLimit"]
    return r

@app.post("/ban", status_code=201, response_model=ItemsBanned, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def new_ban(request:Request, userID:Annotated[str, Form()], itemID:Annotated[str, Form()]):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't ban {} for {} as it looks like {} doesn't exist.".format(itemID, userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    print("Banning {} for user {}".format(itemID, userID))
    alreadyBanned = checkForExistingBan(userID=userID, itemID=itemID)
    r = ItemsBanned()
    r.AlreadyBanned = alreadyBanned
    jellyfinItem = jellyfin.item(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemID=itemID)
    r.Items = {
        "{}".format(jellyfinItem["Type"]): [jellyfinItem]
        }
    if alreadyBanned == False:
        banForUser(userID=userID, itemID=itemID)
        r.Success = True
    return r

@app.delete("/ban", status_code=200, response_model=ItemsBanned, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def un_ban(request:Request, userID:str, itemID:str):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't unban {} for {} as it looks like {} doesn't exist.".format(itemID, userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    print("Un-Banning {} for user {}".format(itemID, userID))
    alreadyBanned = checkForExistingBan(userID=userID, itemID=itemID)
    unBanForUser(userID=userID, itemID=itemID)
    r = ItemsBanned()
    r.AlreadyBanned = alreadyBanned
    jellyfinItem = jellyfin.item(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemID=itemID)
    r.Items = {
        "{}".format(jellyfinItem["Type"]): [jellyfinItem]
        }
    r.Success = True
    return r

@app.delete("/reset-bans", status_code=201, response_model=ItemsBanned, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def reset_bans(request:Request, userID:str):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't unban everything for {} as it looks like {} doesn't exist.".format(userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    print("Un-Banning everything for user {}".format(userID))
    unBanForUser(userID=userID)
    # There is no single item to echo here (an `itemID` was left in the
    # copied body from /ban and would crash the handler); the cleared
    # list is what a client reads back from GET /bans.
    r = ItemsBanned()
    r.Success = True
    return r

@app.get("/bans", status_code=200, response_model=ItemsBanned, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def get_bans(request:Request, userID:str):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't sign {} up for the family blend as it looks like {} doesn't exist.".format(userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    print("Getting bans for user {}".format(userID))
    bans = common.getUserBans(userID=userID)
    bannedItems = {}
    print("Found {} bans. Sorting them into the proper dictionary".format(len(bans)))
    for id in bans:
        jellyfinItem = jellyfin.item(host=userInfo.host, token=userInfo.token, userID=userInfo.id, itemID=id)
        itemType = jellyfinItem["Type"]
        if itemType in bannedItems.keys():
            itemList = bannedItems[itemType]
            itemList.append(jellyfinItem)
            bannedItems[itemType] = itemList
        else:
            bannedItems[itemType] = [jellyfinItem]
    r = ItemsBanned()
    r.AlreadyBanned = True
    r.Items = bannedItems
    r.Success = True
    return r

@app.get("/text-to-tunes", response_model=ExtendedQueue, responses={404: {"description": "User not found", "model": ErrorResponse}})
async def text_to_tunes(request:Request, userID:str, query:str, limit:int=50) -> ExtendedQueue:
    # Check to see if the user exists
    userInfo = common.getUserInfo(userID)
    userBans = common.getUserBans(userID=userID)
    if userInfo is None:
        print("User {} could not be found".format(userID))
        raise HTTPException(status_code=404, detail="User {} not found".format(userID))
    # User does exist
    try:
        alchemySongs = audiomuse.instantPlaylist(query=query, limit=limit)
    except Exception as e:
        print("Couldn't get any songs from audiomuse. Check the logs there.{}\n".format(e))
        alchemySongs = []
    alchemySongIDs = []
    for song in alchemySongs:
        # Respect the user's bans
        banned = False
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
            banned = True
        if banned:
            try:
                print("Skipping alchemy song '{}' by '{}' because it's banned".format(jellyfinItem["Name"], ", ".join(jellyfinItem["Artists"])))
            except Exception as e:
                print("Couldn't properly right error message about skipping: {}\n{}".format(song, e))
        else:
            alchemySongIDs.append(song["item_id"])
    r = ExtendedQueue()
    r.NewTrackIDs = alchemySongIDs
    r.Count = len(alchemySongs)
    print("Got {} songs for the query '{}'.".format(len(alchemySongs), query))
    return r

@app.get("/server-playlist", status_code=200, response_model=UserServerPlaylistStatus, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def family_blend_status(request:Request, userID:str):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't sign {} up for the Family Blend as it looks like {} doesn't exist.".format(userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    r = UserServerPlaylistStatus()
    r.inServerPlaylist = serverPlaylistStatus(userID=userID)
    r.id = userID
    return r

@app.post("/server-playlist", status_code=201, response_model=UserServerPlaylistStatus, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def family_blend_signup(request:Request, userID:Annotated[str, Form()]):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't sign {} up for the Family Blend as it looks like {} doesn't exist.".format(userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    serverPlaylistSignup(userID=userID)
    r = UserServerPlaylistStatus()
    r.inServerPlaylist = True
    r.id = userID
    return r

@app.delete("/server-playlist", status_code=200, response_model=UserServerPlaylistStatus, responses={401: {"description": "User invalid", "model": ErrorResponse}})
async def family_blend_removal(request:Request, userID:str):
    userInfo = common.getUserInfo(userID=userID)
    if userInfo is None:
        print("Can't sign {} up for the Family Blend as it looks like {} doesn't exist.".format(userID, userID))
        raise HTTPException(status_code=401, detail="User {} does not seem to exist".format(userID))
    # User does exist
    serverPlaylistRemoval(userID=userID)
    r = UserServerPlaylistStatus()
    r.inServerPlaylist = False
    r.id = userID
    return r
