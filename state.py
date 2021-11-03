# Copyright (c) 2016-2021 Twilio Inc.

import os
import threading
import time

try:  # Python 3
    from queue import Queue
except ImportError:  # Python 2
    from Queue import Queue

import psycopg2

dburl = os.getenv('DATABASE_URL')
if not dburl:
    dburl = 'dbname=test user=cswenson'
conn = psycopg2.connect(dburl)
cur = conn.cursor()
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS adventure (
            num VARCHAR(32) PRIMARY KEY,
            state BYTEA,
            created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            modified TIMESTAMP WITH TIME ZONE DEFAULT NOW());
    """)
    conn.commit()
except Exception:
    pass
cur.close()

from interpret import Game


class StateHandler(object):
    def __init__(self):
        self.outqueue = Queue()
        self.inqueue = Queue()
    def read(self):
        return self.inqueue.get()
    def write(self, data):
        self.outqueue.put(data)

states = {}

def run_for(from_, inp):
    try:
        cur = conn.cursor()
        inp = str(inp).upper().strip()
        inp = inp[:20] # commands shouldn't be longer than this

        cur.execute("SELECT state FROM adventure WHERE num = %s", (from_,))
        row = cur.fetchone()
        exists = row is not None
        ignore_input = False
        new_game = False

        if inp in ('RESET', 'QUIT', 'PURGE'):
            if from_ in states:
                del states[from_]
                exists = False  # force a reset
                cur.execute("DELETE FROM adventure WHERE num = %s", (from_,))
        elif inp == 'PURGE':
            return 'Your data has been purged from the database. Text back to start a new game in the future if you like.'

        if not exists:
            print('starting new game for', from_)
            handler = StateHandler()
            game = Game(handler)
            t = threading.Thread(target=game.go)
            t.daemon = True
            t.start()
            states[from_] = [handler, game, t]
            ignore_input = True
            new_game = True

        if exists and from_ not in states:
            # load from backup
            handler = StateHandler()
            game = Game(handler)
            t = threading.Thread(target=game.go)
            t.daemon = True
            t.start()
            states[from_] = [handler, game, t]
            # wait for it to boot
            while not game.waiting():
                time.sleep(0.001)
            # empty the queues
            while not handler.outqueue.empty():
                handler.outqueue.get_nowait()
            game.setstate(row[0])
            states[from_] = [handler, game, t]

        handler, game, _ = states[from_]
        if not ignore_input:
            handler.inqueue.put(inp)
        time.sleep(0.001)
        while not game.waiting():
            time.sleep(0.001)
        text = ''
        while not text:
            while not handler.outqueue.empty():
                text += handler.outqueue.get()
                time.sleep(0.001)

        # now save the game state to the database
        state = game.getstate()
        if exists:
            cur.execute("UPDATE adventure SET state = %s, modified = NOW() WHERE num = %s", (psycopg2.Binary(state), from_))
        else:
            cur.execute("INSERT INTO adventure (num, state) VALUES (%s,%s)", (from_, psycopg2.Binary(state)))
        conn.commit()

        if new_game:
            text = 'Welcome to Adventure! Type RESET or QUIT to restart the game. Type PURGE to be removed from our database.\n\n' + text
        return text
    finally:
        cur.close()
