import requests
import sys
import os
from requests.cookies import RequestsCookieJar

def auth(host:str, user:str, pw:str) -> RequestsCookieJar:
    path = "/auth"
    data = {
        "user": user,
        "password": pw
    }
    url = "{}{}".format(host, path)
    r = requests.post(url=url, data=data, allow_redirects=False)
    return r.cookies
    

def sonicFingerprint(userID:str, userToken:str, songCount:int) -> list:
    host=os.environ['AUDIOMUSE_HOST']
    cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
    path = "/api/sonic_fingerprint/generate"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    body = {
        "n": songCount,
        "jellyfin_user_identifier": userID,
        "jellyfin_token": userToken
    }
    url = "{}{}".format(host, path)
    r = requests.post(url=url, headers=headers, cookies=cookies, json=body)
    if r.status_code != 200:
        print("ERROR: audiomuse response {}\n{}".format(r.status_code, r.text))
    return r.json()
    
def alchemy(addSongs:list[str], subtractSongs:list[str]=[], songLimit:int=50) -> list:
    host=os.environ['AUDIOMUSE_HOST']
    cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
    path = "/api/alchemy"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    items = []
    for song in addSongs:
        s = {
            "id": song,
            "op": "ADD",
            "type": "song"
        }
        items.append(s)
    for song in subtractSongs:
        s = {
            "id": song,
            "op": "SUBTRACT",
            "type": "song"
        }
        items.append(s)
    body = {
        "items": items,
        "n": songLimit,
        "temperature": 1,
        "substract_disc": 0.2
    }
    url = "{}{}".format(host, path)
    r = requests.post(url=url, headers=headers, cookies=cookies, json=body)
    if r.status_code != 200:
        print("ERROR: audiomuse response {}\n{}".format(r.status_code, r.text))
    j = r.json()
    return j["results"]

def clap(query:str, limit:int) -> dict:
    host=os.environ['AUDIOMUSE_HOST']
    cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
    path = "/api/clap/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    body = {
        "query": query,
        "limit": limit
    }
    url = "{}{}".format(host, path)
    r = requests.post(url=url, headers=headers, cookies=cookies, json=body)
    if r.status_code != 200:
        print("ERROR: audiomuse response {}\n{}".format(r.status_code, r.text))
    return r.json()

def similarArtists(artistName:str, numberOfArtists:int=3) -> list:
    host=os.environ['AUDIOMUSE_HOST']
    cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
    path = "/api/similar_artists"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    params = {
        "artist": artistName,
        "n": numberOfArtists,
        "include_component_matches": True
    }
    url = "{}{}".format(host, path)
    r = requests.get(url=url, headers=headers, cookies=cookies, params=params)
    if r.status_code != 200:
        print("ERROR: audiomuse response {}\n{}".format(r.status_code, r.text))
    return r.json()