from lib import common, db, jellyfin

lyricsCache = {}
lyricsCacheQ = "SELECT * FROM Lyrics"
currentyricsCacheRaw = db.select(query=lyricsCacheQ, datatuple=(), tableName="Lyrics")
for row in currentyricsCacheRaw:
    lyricsCache[row["id"]] = row["text"]


user = common.getUsers()[0]
  
morePages = True
startIndex = 0
songsProcessed = 0
pageLimit = 200
dbUpdates = 0
while morePages:
    extraParamas = {
        "sortBy": "Artist,SortName",
        "sortOrder": "Ascending",
        "startIndex": startIndex,
        "IncludeItemTypes": "Audio",
    }
    songs = jellyfin.getItemBySearch(host=user.host, token=user.token, userID=user.id, extraParams=extraParamas, limit=pageLimit)
    lyricsQueries = []
    deleteQueries = []
    q = "INSERT INTO Lyrics VALUES(?,?)"
    dq = "DELETE FROM Lyrics WHERE id = ?"
    print("Checking out {}/{} songs.".format(songs["StartIndex"], songs["TotalRecordCount"]), end="\r")
    for song in songs["Items"]:
        if song.get("HasLyrics", False):
            lyricsRaw = jellyfin.getLyrics(host=user.host, token=user.token, userID=user.id, itemID=song["Id"])
            lyricsText = ""
            for line in lyricsRaw["Lyrics"]:
                if lyricsText == "":
                    lyricsText = line["Text"]
                else:
                    lyricsText = "{}\n{}".format(lyricsText, line["Text"])
            updateLyricsForSong = True
            if song["Id"] in lyricsCache.keys():
                if lyricsCache[song["Id"]] == lyricsText:
                    updateLyricsForSong = False
            if updateLyricsForSong:
                deleteQuery = db.BatchQuery()
                deleteQuery.query = dq
                deleteQuery.dataTuple = (song["Id"],)
                deleteQueries.append(deleteQuery)
                lyricsQuery = db.BatchQuery()
                lyricsQuery.query = q
                lyricsQuery.dataTuple = (song["Id"], lyricsText)
                lyricsQueries.append(lyricsQuery)
        songsProcessed = songsProcessed + 1
    if songsProcessed >= songs["TotalRecordCount"]:
        morePages = False
    else:
        startIndex = songsProcessed
    # do db work
    # delete first
    db.batchJob(queries=deleteQueries, tableName="Lyrics")
    # then insert
    db.batchJob(queries=lyricsQueries, tableName="Lyrics")
    print("Finished page. Processed {} songs with {} db updates so far.".format(songsProcessed, dbUpdates), end="\r")
    dbUpdates = dbUpdates + len(lyricsQueries)
print("Done. Processed {} songs total resulting in {} songs having their lyrics updated in the db.".format(songsProcessed), dbUpdates)