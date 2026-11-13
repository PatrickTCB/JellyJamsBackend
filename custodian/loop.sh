#!/bin/bash
# These scripts make playlists that are similar to, but not the same as
# the AudioMuse-AI playlists. Because I want JellyFin to treat them the same
# as other mixtapes, I append them with _automatic. But that means that 
# AudioMuse-AI will delete them whenever it rebuilds its automatic playlists
# Therefore the scripts will check every 2 minutes to make sure the playlists
# they control still exist, and rebuild them if they don't. They'll also
# rebuild them if they exist but are over ~23.5h old.
echo "Container started `date`"
python3 -u setup.py
while true; do
    echo "====="
    echo `date`
    python3 -u main.py
    echo "Standard custodian jobs done"
    echo "====="
    for job in custom-jobs/*.py; do
        echo "===== $job"
        python3 -u "$job" || echo "$job exited with status $?"
    done
    echo -ne "Sleeping for 2m"\\r
    sleep 120
done