import os
import json
import sqlcipher3
import sqlite3
import time

def tableExists(tableName, verbose=False):
    dbname="/data/jellyjams-server.db"
    tableExistsInDB = False
    con = sqlcipher3.connect(dbname)
    con.execute("PRAGMA key='{}'".format(os.environ['DB_PW']))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()
    #dupcheck
    dq = "SELECT * FROM sqlite_master WHERE name = '{}'".format(tableName)
    dr = cur.execute(dq)
    if len(dr.fetchall()) > 0:
        tableExistsInDB = True
        if verbose:
            print("{} already exists".format(tableName))
    con.commit()
    con.close()
    return tableExistsInDB

def create(useExisting=False, verbose=False):
    dbname="/data/jellyjams-server.db"
    if useExisting == False:
        alreadyExists = os.path.isfile(dbname)
        if alreadyExists:
            if verbose:
                print("{} already exists. Deleting it to create from scratch.".format(dbname))
            os.remove(dbname)
    con = sqlcipher3.connect(dbname)
    con.execute("PRAGMA key='{}'".format(os.environ['DB_PW']))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()
    r = cur.execute("SELECT * FROM sqlite_master")
    if verbose:
        print("DB created with {} tables.".format(len(r.fetchall())))
    con.close()
    return dbname

def table(tableName, tableColumns, verbose=False):
    dbname="/data/jellyjams-server.db"
    con = sqlcipher3.connect(dbname)
    con.execute("PRAGMA key='{}'".format(os.environ['DB_PW']))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()
    #dupcheck
    if tableExists(tableName=tableName, verbose=verbose) == False:
        query = "CREATE TABLE {}({})".format(tableName, ",".join(tableColumns))
        if verbose:
            print("db query: {}".format(query))
        cur.execute(query)
    con.commit()
    con.close()
    
def delete(query, datatuple, tableName, verbose=False):
    dbname="/data/jellyjams-server.db"
    con = sqlcipher3.connect(dbname)
    con.execute("PRAGMA key='{}'".format(os.environ['DB_PW']))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()
    keepTrying = True
    count = 0
    # Writes should be re-tried if they fail at first. Only one thread can write to an SQLite DB at a time, and so multi-threaded scripts could run into problems.
    while keepTrying:
        count = count + 1
        try:
            cur.execute(query, datatuple)
            if verbose:
                print("attempt {}: {} | {}".format(count, query, datatuple))
                tableSize = cur.execute("SELECT * FROM {}".format(tableName))
                print("{} already has {} entries".format(tableName, len(tableSize.fetchall())))
            #if there's an error it'll happen above so reaching this line is a sign that things worked.
            keepTrying = False
        except Exception as e:
            time.sleep(count)
            if count > 5:
                keepTrying = False
            if verbose:
                print("Error: {} on attempt {}. '{}'".format(e, count, query))
    con.commit()
    con.close()

def insert(query, datatuple, tableName, verbose=False):
    dbname="/data/jellyjams-server.db"
    con = sqlcipher3.connect(dbname)
    con.execute("PRAGMA key='{}'".format(os.environ['DB_PW']))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()
    if tableExists(tableName=tableName, verbose=verbose) == False:
        if verbose:
            print("table {} dosen't exist in {}.".format(tableName, dbname))
        return
    else:
        keepTrying = True
        count = 0
        # Writes should be re-tried if they fail at first. Only one thread can write to an SQLite DB at a time, and so multi-threaded scripts could run into problems.
        while keepTrying:
            count = count + 1
            try:
                cur.execute(query, datatuple)
                if verbose:
                    print("attempt {}: db: {} | {} | {}".format(count, dbname, query, datatuple))
                    tableSize = cur.execute("SELECT * FROM {}".format(tableName))
                    print("{} already has {} entries".format(tableName, len(tableSize.fetchall())))
                #if there's an error it'll happen above so reaching this line is a sign that things worked.
                keepTrying = False
            except Exception as e:
                time.sleep(count)
                if count > 5:
                    keepTrying = False
                if verbose:
                    print("Error on {}: {} on attempt {}. '{}'".format(dbname, e, count, query))
    con.commit()
    con.close()

def select(query, datatuple, tableName, verbose=False) -> list:
    dbname="/data/jellyjams-server.db"
    results = []
    con = sqlcipher3.connect(dbname)
    con.execute("PRAGMA key='{}'".format(os.environ['DB_PW']))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()
    if verbose:
        print("db: {} | q: {} | {}".format(dbname, query, datatuple))
    if tableExists(tableName=tableName, verbose=verbose) == False:
        if verbose:
            print("table {} dosen't exist in {}.".format(tableName, dbname))
    else:
        r = cur.execute(query, datatuple)
        try:
            resultsList = r.fetchall()
            tableSchema = {}
            if verbose:
                print("Building table scheme by getting all column names")
            try:
                tableSchemaR = cur.execute("PRAGMA table_info({})".format(tableName))
                tableSchemaTup = tableSchemaR.fetchall()
                # maps the column index to its name
                for i in tableSchemaTup:
                    tableSchema[int(i[0])] = i[1]
                if verbose:
                    print("{} schema: {}".format(tableName, json.dumps(tableSchema)))
            except Exception as e:
                print("Couldn't build schema for {}".format(tableName))
                if verbose:
                    print("{}".format(e))
            try:
                if verbose:
                    print("{} schema: {}".format(tableName, json.dumps(tableSchema)))
                for result in resultsList:
                    if verbose:
                        print("{}".format('|'.join(map(str, result))))
                    # uses the mapping from above to build a dictionary out of tuple results
                    rd = {}
                    i = 0
                    for column in result:
                        rd[tableSchema[i]] = column
                        i = i + 1
                    results.append(rd)
            except Exception as e:
                print("Couldn't build results dictionary for {}".format(query))
                if verbose:
                    print("{}".format(e))
                    
        except Exception as e:
            if verbose:
                print("tried to run {}".format(query))
            print("{}".format(e))
    con.commit()
    con.close()
    return results