import json
import requests
import curlify
import time
from urllib import parse
from lib import common

def searchByDetails(track, artist, album, token, verbose=False):
    try:
        headers = {
            "Authorization": "Discogs token={token}".format(token=token)
        }
        if artist == "various artists":
            url = "https://api.discogs.com/database/search?track={track}&release_title={album}".format(track=parse.quote_plus(track), album=parse.quote_plus(album))
        else:
            url = "https://api.discogs.com/database/search?track={track}&artist={artist}&release_title={album}".format(track=parse.quote_plus(track), artist=parse.quote_plus(artist), album=parse.quote_plus(album))
        r = requests.get(url=url, headers=headers)
        RateLimit = int(dict(r.headers).get("x-discogs-ratelimit-remaining", 0))
        #print("Discogs rate limit {}".format(RateLimit))
        if RateLimit < 3:
            time.sleep(2)
        if r.status_code == 200:
            return json.loads(r.text)
        else:
            # slow down when hitting errors
            time.sleep(2)
            if verbose:
                print("Error getting track info\nStatus: {}\n{}".format(r.status_code, r.text))
                print(curlify.to_curl(r.request))
            return {}
    except Exception as e:
        # slow down when hitting errors
        time.sleep(4)
        if verbose:
            print("Error looking for {} by {} on {} using discogs.".format(track, artist, album))
            print("Error: {}".format(e))
        return {}

def release(masterId, token, verbose=False):
    try:
        headers = {
            "Authorization": "Discogs token={token}".format(token=token)
        }
        url = "https://api.discogs.com/masters/{masterId}".format(masterId=masterId)
        r = requests.get(url=url, headers=headers)
        RateLimit = int(dict(r.headers).get("x-discogs-ratelimit-remaining", 0))
        #print("Discogs rate limit {}".format(RateLimit))
        if RateLimit < 3:
            time.sleep(2)
        if r.status_code == 200:
            releaseInfo = json.loads(r.text)
            trackNameList = []
            for track in releaseInfo.get("tracklist", []):
                if "title" in track.keys():
                    trackNameList.append(track["title"].lower())
            releaseInfo["trackNameList"] = trackNameList
            return releaseInfo
        else:
            # slow down when hitting errors
            time.sleep(2)
            if verbose:
                print("Error getting track info\nStatus: {}\n{}".format(r.status_code, r.text))
                print(curlify.to_curl(r.request))
            return {}
    except Exception as e:
        # slow down when hitting errors
        time.sleep(4)
        if verbose:
            print("Error looking for {} using discogs.".format(masterId))
            print("Error: {}".format(e))
        return {}