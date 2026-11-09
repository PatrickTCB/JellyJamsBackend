import json
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
    path = "/api/sonic_fingerprint/generate"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    if "AUDIOMUSE_API_KEY" in os.environ:
        headers["Authorization"] = "Bearer: {}".format(os.environ["AUDIOMUSE_API_KEY"])
        cookies = RequestsCookieJar()
    else:
        cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
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
    path = "/api/alchemy"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    if "AUDIOMUSE_API_KEY" in os.environ:
        headers["Authorization"] = "Bearer: {}".format(os.environ["AUDIOMUSE_API_KEY"])
        cookies = RequestsCookieJar()
    else:
        cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
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
    path = "/api/clap/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    if "AUDIOMUSE_API_KEY" in os.environ:
        headers["Authorization"] = "Bearer: {}".format(os.environ["AUDIOMUSE_API_KEY"])
        cookies = RequestsCookieJar()
    else:
        cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
    body = {
        "query": query,
        "limit": limit
    }
    url = "{}{}".format(host, path)
    r = requests.post(url=url, headers=headers, cookies=cookies, json=body)
    if r.status_code != 200:
        print("ERROR: audiomuse response {}\n{}".format(r.status_code, r.text))
    return r.json()

def instantPlaylist(query:str, limit:int) -> dict:
    host=os.environ['AUDIOMUSE_HOST']
    path = "/chat/api/chatPlaylistStream"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    if "AUDIOMUSE_API_KEY" in os.environ:
        headers["Authorization"] = "Bearer: {}".format(os.environ["AUDIOMUSE_API_KEY"])
        cookies = RequestsCookieJar()
    else:
        cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
    body = {
        "userInput": query,
        "ai_provider": "OLLAMA",
        "ai_model": "flint:latest",
        "n": limit,
        "ollama_server_url": "https://ollama.aseriesoftubes.net/api/generate"
    }
    url = "{}{}".format(host, path)
    r = requests.post(url=url, headers=headers, json=body)
    resp = str(r.text.split("\n")[-3]).replace("data: ", "")
    if r.status_code != 200:
        print("ERROR: audiomuse response {}\n{}".format(r.status_code, r.text))
    jr = json.loads(resp)
    return jr["response"]["query_results"]

def similarArtists(artistName:str, numberOfArtists:int=3) -> list:
    host=os.environ['AUDIOMUSE_HOST']
    path = "/api/similar_artists"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    if "AUDIOMUSE_API_KEY" in os.environ:
        headers["Authorization"] = "Bearer: {}".format(os.environ["AUDIOMUSE_API_KEY"])
        cookies = RequestsCookieJar()
    else:
        cookies = auth(user=os.environ['AUDIOMUSE_USER'], pw=os.environ['AUDIOMUSE_PW'], host=host)
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