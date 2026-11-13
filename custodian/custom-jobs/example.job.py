import json
import random

from datetime import datetime

from lib import jellyfin, common

print("Example job starting at {} and doing super cool stuff.".format(int(datetime.now().timestamp())))

# Run job per user
users = common.getUsers()
for user in users:
    print("===\nHere is where I could do something cool and helpful for user {}".format(user.name))
    try:
        userPlaylists = jellyfin.getAllPlaylists(host=user.host, token=user.token, userID=user.id)
    except Exception as e:
        print("Couldn't get playlists for {}.\nProbably an error worth fixing before setting up your own custom job.".format(user.name))
        print(e)
        userPlaylists = {"Items": []}
    try:
        favouriteSongs = jellyfin.favourites(host=user.host, token=user.token, userID=user.id)
    except Exception as e:
        print("Couldn't get favourite songs for {}.\nProbably an error worth fixing before setting up your own custom job.".format(user.name))
        print(e)
        favouriteSongs = {"Items": []}
    randomPlaylist = random.choice(userPlaylists["Items"])
    randomSong = random.choice(favouriteSongs["Items"])
    print("I could have added '{song}' by '{artist}' to '{playlist}', that would've been cool.".format(song=randomSong["Name"], artist=" & ".join(randomSong["Artists"]), playlist=randomPlaylist["Name"]))
print("All done my custom work.")