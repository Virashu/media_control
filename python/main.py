import asyncio
import json

import log
from server import App
from player import Player
from utils import *

from color import get_color


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]
data = {}
log.set_level(log.LEVELS.INFO)


def update(d):
    global data
    d["metadata"]["accent"] = get_color(d["metadata"]["cover"])
    data = d
    write_file(DIRNAME + "/content/contents.json", json.dumps(data, indent="  "))


player = Player(update)


def start_server():
    control = read_file(DIRNAME + "/public/control.html")

    app = App()

    @app.get("/")
    def _(req, res):
        res.send('<a href="/control">control</a><br><a href="/data">data</a>')

    @app.get("/control")
    def _(req, res):
        res.send(control)

    @app.get("/control/pause")
    def _(req, res):
        asyncio.run(player.play_pause())
        res.send(control)

    @app.get("/control/prev")
    def _(req, res):
        asyncio.run(player.prev())
        res.send(control)

    @app.get("/control/next")
    def _(req, res):
        asyncio.run(player.next())
        res.send(control)

    @app.get("/control/repeat")
    def _(req, res):
        asyncio.run(player.toggle_repeat())
        res.send(control)

    @app.get("/data")
    def _(req, res):
        res.send(data)

    app.listen("0.0.0.0", 8888, lambda: log.info("Server started!"))


def start_media_control():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(player.main())


import threading

p1 = threading.Thread(target=start_media_control)
p2 = threading.Thread(target=start_server)
p1.daemon = True
p2.daemon = True

try:
    p1.start()
    p2.start()
    while p1.is_alive():
        p1.join(1)
    while p2.is_alive():
        p2.join(1)
except KeyboardInterrupt:
    log.kawaii("Goodbye!")
    quit(0)
