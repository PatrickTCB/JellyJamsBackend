#!/bin/bash
# These scripts make playlists that are similar to, but not the same as
# the AudioMuse-AI playlists. Because I want JellyFin to treat them the same
# as other mixtapes, I append them with _automatic. But that means that 
# AudioMuse-AI will delete them whenever it rebuilds its automatic playlists
# Therefore the scripts will check every 2 minutes to make sure the playlists
# they control still exist, and rebuild them if they don't. They'll also
# rebuild them if they exist but are over ~23.5h old.
echo "Container started `date`"
while true; do
    echo "====="
    echo `date`
    python3 -u main.py
    echo "User Playlists built"
    echo "====="
    python3 -u server-playlist.py
    echo "$SERVER_PLAYLIST built"
    echo -ne "Sleeping for 2m"\\r
    sleep 120
done