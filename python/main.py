import asyncio
import json

import log
from server import App, Response
from player import Player
from utils import *


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]
data = {}
log.set_level(log.LEVELS.INFO)
control = read_file(f"{DIRNAME}/public/control.html")


def update(d):
    data.update(d)
    write_file(DIRNAME + "/content/contents.json", json.dumps(data, indent="  "))


player = Player(update)

commands = {
    "pause": player.play_pause,
    "prev": player.prev,
    "repeat": player.toggle_repeat,
    "shuffle": player.toggle_shuffle,
    "play": player.play,
    "stop": player.stop,
    "next": player.next,
}


def create_command(app, name, command):
    @app.get(f"/control/{name}")
    def _(req, res):
        log.kawaii(f"Running command: {name}")
        asyncio.run(command())
        res.send(control)


def start_server():
    app = App()

    @app.get("/")
    def _(req, res):
        res.send('<a href="/control">control</a><br><a href="/data">data</a>')

    @app.get("/control")
    def _(req, res):
        res.send(control)

    for command in commands.items():
        create_command(app, *command)

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
