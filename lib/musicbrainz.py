import curlify
import requests
import json
import time
from urllib import parse
from lib import common

def recordingSearch(host, contact, title, album, artist, verbose=False):
    try:
        url = "{host}recording/?query=track:{track}ANDartist:{artist}ANDtitle:{album}&fmt=json".format(host=host, track=parse.quote_plus(title), artist=parse.quote_plus(artist), album=parse.quote_plus(album))
        headers = {
            "User-Agent": "Plex Smart Playlist Builder/0.1 {}".format(contact)
        }

        r = requests.get(url, headers=headers)
        XRateLimitRemaining = int(dict(r.headers).get("X-RateLimit-Remaining", 0))
        #print("X-RateLimit-Remaining: {}".format(XRateLimitRemaining))
        if XRateLimitRemaining < 900:
            time.sleep(2)
        if r.status_code == 200:
            return json.loads(r.text)
        else:
            # slow down when hitting errors
            time.sleep(2)
            if verbose:
                print("Error looking for {} by {} on {} using {}.".format(title, artist, album, host))
                print("Status: {}\n{}\n{}".format(r.status_code, r.text, curlify.to_curl(r.request)))
            return {}
    except Exception as e:
        # slow down when hitting errors
        time.sleep(4)
        if verbose:
            print("Error looking for {} by {} on {} using {}.".format(title, artist, album, host))
            print("Error: {}".format(e))
        return {}

def recordingByID(host, contact, mbid, verbose=False):
    try:
        url = "{host}recording/{mbid}/?fmt=json".format(host=host, mbid=mbid)
        headers = {
            "User-Agent": "Plex Smart Playlist Builder/0.1 {}".format(contact)
        }

        r = requests.get(url, headers=headers)
        XRateLimitRemaining = int(dict(r.headers).get("X-RateLimit-Remaining", 0))
        #print("X-RateLimit-Remaining: {}".format(XRateLimitRemaining))
        if XRateLimitRemaining < 900:
            time.sleep(2)
        if r.status_code == 200:
            if verbose:
                common.stringToFile("{}.json".format(mbid), r.text)
                print("Saved {}.json".format(mbid))
            return json.loads(r.text)
        else:
            # slow down when hitting errors
            time.sleep(2)
            if verbose:
                print("Error looking for {} using {}.".format(mbid, host))
                print("Status: {}\n{}\n{}".format(r.status_code, r.text, curlify.to_curl(r.request)))
            return {}
    except Exception as e:
        # slow down when hitting errors
        time.sleep(4)
        if verbose:
            print("Error looking for {} using {}.".format(mbid, host))
            print("Error: {}".format(e))
        return {}

def tags(host, contact, mbid, verbose=False):
    try:
        url = "{host}recording/{mbid}?inc=genres&fmt=json".format(host=host, mbid=mbid)
        headers = {
            "User-Agent": "Plex Smart Playlist Builder/0.1 {}".format(contact)
        }

        r = requests.get(url, headers=headers)
        XRateLimitRemaining = int(dict(r.headers).get("X-RateLimit-Remaining", 0))
        #print("X-RateLimit-Remaining: {}".format(XRateLimitRemaining))
        if XRateLimitRemaining < 900:
            time.sleep(2)
        if r.status_code == 200:
            return json.loads(r.text)
        else:
            # slow down when hitting errors
            time.sleep(2)
            if verbose:
                print("Error looking for {} using {}.".format(mbid, host))
                print("Status: {}\n{}\n{}".format(r.status_code, r.text, curlify.to_curl(r.request)))
            return {}
    except Exception as e:
        # slow down when hitting errors
        time.sleep(4)
        if verbose:
            print("Error looking for {} using {}.".format(mbid, host))
            print("Error: {}".format(e))
        return {}