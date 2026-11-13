import datetime
import requests
import sys

def credentialCheck(host:str, token:str, userID:str, verbose:bool=False) -> dict:
    jPath = "/Users/Me".format(userID)
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
    }
    params = {
        "userId": userID
    }
    url = "{}{}".format(host, jPath)
    d = requests.get(url=url, headers=headers, params=params)
    return d.json()

def item(host:str, token:str, userID:str, itemID:str, verbose:bool=False) -> dict:
    jPath = "/Items/{}".format(itemID)
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
    }
    url = "{}{}".format(host, jPath)
    params = {
        "userId": userID
    }
    d = requests.get(url=url, headers=headers, params=params)
    return d.json()

def favourites(host:str, token:str, userID:str, verbose:bool=False) -> dict:
    jPath = "/Users/{}/Items".format(userID)
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
    }
    url = "{}{}".format(host, jPath)
    params = {
        "IncludeItemTypes": "Audio",
        "Recursive": "true",
        "IsFavorite": "true"
    }
    d = requests.get(url=url, headers=headers, params=params)
    return d.json()

def recentPlays(host:str, token:str, userID:str, limit:int=100, verbose:bool=False) -> list:
    q = "SELECT ROWID, * FROM PlaybackActivity WHERE UserId = '{}' AND ItemType = 'Audio' ORDER BY rowid DESC LIMIT {}".format(userID, limit)
    jPath = "/user_usage_stats/submit_custom_query"
    params = {
        "CustomQueryString": q,
        "ReplaceUserId": False
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
    }
    url = "{}{}".format(host, jPath)
    d = requests.post(url=url, headers=headers, json=params)
    try:
        j = d.json()
    except Exception as e:
        print(q)
        print(d.status_code)
        print(d.text)
        print("Couldn't get playback info for {}.".format(userID))
        return []
    playList = []
    jellyfinItems = []
    for result in j["results"]:
        i = 0
        e = {}
        for line in result:
            e[j["colums"][i]] = line
            i = i + 1
        playList.append(e)
    if verbose:
        print("Got {} recent play events".format(len(playList)))
    for r in playList:
        i = item(host=host, token=token, userID=userID, itemID=r["ItemId"], verbose=verbose)
        songLength = int(i["RunTimeTicks"] / 10000000)
        playbackProgress = int((int(r["PlayDuration"]) / songLength) * 100)
        if playbackProgress >= 80:
            jellyfinItems.append(i)
        else:
            if verbose:
                print("Playback progress only {}% for {}".format(playbackProgress, r["ItemName"]), end="\r")
    if verbose:
        print("Got {} tracks listened to at least 80%".format(len(jellyfinItems)))
    return jellyfinItems

def songLastPlay(host:str, token:str, userID:str, itemId:str, verbose:bool=False) -> str:
    action = "SKIP"
    q = "SELECT ROWID, * FROM PlaybackActivity WHERE UserId = '{}' AND ItemId = '{}' ORDER BY rowid DESC LIMIT 1".format(userID, itemId)
    jPath = "/user_usage_stats/submit_custom_query"
    params = {
        "CustomQueryString": q,
        "ReplaceUserId": False
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
    }
    url = "{}{}".format(host, jPath)
    d = requests.post(url=url, headers=headers, json=params)
    try:
        j = d.json()
    except Exception as e:
        print(q)
        print(d.status_code)
        print(d.text)
        print("Couldn't get playback info for {} by {}.".format(itemId, userID))
        return action
    playList = []
    for result in j["results"]:
        i = 0
        e = {}
        for line in result:
            e[j["colums"][i]] = line
            i = i + 1
        playList.append(e)
    if verbose:
        print("Got {} recent play events".format(len(playList)))
    for r in playList:
        i = item(host=host, token=token, userID=userID, itemID=r["ItemId"], verbose=verbose)
        songLength = int(i["RunTimeTicks"] / 10000000)
        playbackProgress = int((int(r["PlayDuration"]) / songLength) * 100)
        if playbackProgress >= 80:
            action = "PLAY"
        else:
            if verbose:
                print("Playback progress only {}% for {}. That's a skip".format(playbackProgress, r["ItemName"]), end="\r")
    if verbose:
        print("Last action for this song was: {}".format(action))
    return action

def songPlayCount(host:str, token:str, userID:str, itemId:str, includePartial:bool=False, dayLimit:int=300, verbose:bool=False) -> int:
    playCount = 0
    q = "SELECT ROWID, * FROM PlaybackActivity WHERE UserId = '{}' AND ItemId = '{}' AND DateCreated >= date('now','-{} day') ORDER BY rowid DESC".format(userID, itemId, dayLimit)
    jPath = "/user_usage_stats/submit_custom_query"
    params = {
        "CustomQueryString": q,
        "ReplaceUserId": False
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
    }
    url = "{}{}".format(host, jPath)
    d = requests.post(url=url, headers=headers, json=params)
    try:
        j = d.json()
    except Exception as e:
        print(q)
        print(d.status_code)
        print(d.text)
        print("Couldn't get playback info for {} by {}.".format(itemId, userID))
        return 0
    playList = []
    for result in j["results"]:
        i = 0
        e = {}
        for line in result:
            e[j["colums"][i]] = line
            i = i + 1
        playList.append(e)
    if verbose:
        print("Got {} recent play events".format(len(playList)))
    for r in playList:
        i = item(host=host, token=token, userID=userID, itemID=r["ItemId"], verbose=verbose)
        songLength = int(i["RunTimeTicks"] / 10000000)
        playbackProgress = int((int(r["PlayDuration"]) / songLength) * 100)
        if playbackProgress >= 80 or includePartial:
            playCount = playCount + 1
        else:
            if verbose:
                print("Playback progress only {}% for {}".format(playbackProgress, r["ItemName"]), end="\r")
    if verbose:
        print("Got {} plays listened to at least 80%".format(playCount))
    return playCount

def library(host:str, token:str, userID:str, verbose:bool=False) -> dict:
    jPath = "/Items"
    params = {
        "userId": userID,
        "recursive": "true"
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token)
    }
    url = "{}{}".format(host, jPath)
    r = requests.get(url=url, headers=headers, params=params)
    if verbose:
        print("Received all Jellyfin Items from {}.".format(host))
    return r.json()

def getAllPlaylists(host:str, token:str, userID:str, verbose=False) -> dict:
    # https://api.jellyfin.org/#tag/Items/operation/GetItems
    jPath = "/Items"
    params = {
        "userId": userID,
        "recursive": "true",
        "includeItemTypes": "Playlist"
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    url = "{}{}".format(host, jPath)
    r = requests.get(url=url, headers=headers, params=params)
    if r.status_code != 200:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.json()

def getPlaylistBySearch(host:str, token:str, userID:str, playlistName:str, limit:int=100, verbose=False) -> dict:
    # https://api.jellyfin.org/#tag/Items/operation/GetItems
    jPath = "/Items"
    params = {
        "userId": userID,
        "limit": "".format(limit),
        "recursive": "true",
        "searchTerm": playlistName,
        "includeItemTypes": "Playlist",
        "fields": "ProviderIds,Path,MediaSources,MediaStreams"
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    url = "{}{}".format(host, jPath)
    r = requests.get(url=url, headers=headers, params=params)
    if r.status_code != 200:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    result = {}
    searchResults = r.json()
    if searchResults["TotalRecordCount"] > 0:
        for item in searchResults["Items"]:
            if item["Type"] == "Playlist" and playlistName == item["Name"]:
                result = item
    return result

def getItemBySearch(host:str, token:str, userID:str, searchTerm:str="", extraParams:dict={}, limit:int=100, verbose=False) -> dict:
    # https://api.jellyfin.org/#tag/Items/operation/GetItems
    jPath = "/Items"
    params = {
        "userId": userID,
        "limit": "{}".format(limit),
        "recursive": "true"
    }
    if searchTerm != "":
        params["searchTerm"] = searchTerm
    for k in extraParams.keys():
        params[k] = extraParams[k]
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    url = "{}{}".format(host, jPath)
    r = requests.get(url=url, headers=headers, params=params)
    if r.status_code != 200:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.json()

def getSimilarArtists(host:str, token:str, userID:str, artistId:str="", limit:int=10, verbose=False) -> dict:
    # https://api.jellyfin.org/#tag/Items/operation/GetItems
    jPath = "/Artists/{}/Similar".format(artistId)
    params = {
        "userId": userID,
        "limit": "{}".format(limit),
        "recursive": "true"
    }
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    url = "{}{}".format(host, jPath)
    r = requests.get(url=url, headers=headers, params=params)
    if r.status_code != 200:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.json()

def createPlaylist(host:str, token:str, userID:str, name:str, items:list=[]):
    body = {
        "Name": name,
        "Ids": items,
        "UserId": userID,
        "MediaType": "Audio",
        "Users": [
            {
            "UserId": userID,
            "CanEdit": True
            }
        ],
        "IsPublic": False
    }
    jPath = "/Playlists"
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    url = "{}{}".format(host, jPath)
    r = requests.post(url=url, headers=headers, json=body)
    if r.status_code != 200:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.json()

def getPlaylist(host: str, token:str, userID:str, playlistID:str):
    # https://api.jellyfin.org/#tag/Playlists/operation/GetPlaylist
    jPath = "/Playlists/{}".format(playlistID)
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    params = {
        "userId": userID
    }
    url = "{}{}".format(host, jPath)
    r = requests.get(url=url, headers=headers, params=params)
    if r.status_code != 200:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.json()

def addToPlaylist(host: str, token:str, name:str, itemIDs:str, userID:str, playlistID: str):
    # https://api.jellyfin.org/#tag/Playlists/operation/RemoveItemFromPlaylist
    jPath = "/Playlists/{}".format(playlistID)
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    body = {
        "Name": name,
        "Ids": itemIDs,
        "UserId": userID,
        "MediaType": "Audio",
        "Users": [
            {
            "UserId": userID,
            "CanEdit": True
            }
        ],
        "IsPublic": False
    }
    url = "{}{}".format(host, jPath)
    r = requests.post(url=url, headers=headers, json=body)
    if r.status_code != 204:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.text

def removeFromPlaylist(host: str, token:str, entryIDs: str, userID:str, playlistID: str):
    # https://api.jellyfin.org/#tag/Playlists/operation/RemoveItemFromPlaylist
    jPath = "/Playlists/{}/Items".format(playlistID)
    headers = {
        "Authorization": "MediaBrowser Client=\"Script\", Device=\"backend\", Token=\"{}\"".format(token),
        "Accept": "application/json"
    }
    params = {
        "entryIds": entryIDs,
        "userId": userID
    }
    url = "{}{}".format(host, jPath)
    r = requests.delete(url=url, headers=headers, params=params)
    if r.status_code != 204:
        print("ERROR: Jellyfin response {}\n{}".format(r.status_code, r.text))
    return r.text

def playlistSetup(host:str, token:str, userID:str, name:str, songs:list, verbose:bool):
    # attempt to find existing list
    s = getPlaylistBySearch(host=host, token=token, userID=userID, playlistName=name, verbose=verbose)
    if len(s.keys()) > 0:
        existingList = getPlaylist(host=host, token=token, userID=userID, playlistID=s["Id"])
        removeFromPlaylist(host=host, token=token, playlistID=s["Id"], entryIDs=",".join(existingList["ItemIds"]), userID=userID)
        addToPlaylist(host=host, token=token, userID=userID, name=name, itemIDs=",".join(songs), playlistID=s["Id"])
    else:
        createPlaylist(host=host, token=token, userID=userID, name=name, items=songs)

