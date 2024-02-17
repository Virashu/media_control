import asyncio
import json
import logging
import sys
import threading

from saaba import App, Request, Response

from media_control.player import Player
from media_control.utils import read_file, write_file


logging.getLogger("media_control.player").disabled = True

saaba_logger = logging.getLogger("saaba")
saaba_logger.disabled = False

logger = logging.root
logger.setLevel(logging.INFO)

DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]

data = {}
control = read_file(f"{DIRNAME}/media_control/public/control.html")


def update(d):
    data.update(d)
    write_file(
        DIRNAME + "/media_control/content/contents.json", json.dumps(data, indent="  ")
    )


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


def create_command(app: App, name: str, command):
    @app.get(f"/control/{name}")
    def _(req: Request, res: Response):
        logger.info("Running command: %s", name)
        asyncio.run(command())
        res.send(control)


def start_server():
    app = App()

    @app.get("/")
    def _(_, res: Response):
        res.send('<a href="/control">control</a><br><a href="/data">data</a>')

    @app.get("/control")
    def _(_, res: Response):
        res.send(control)

    for command in commands.items():
        create_command(app, *command)

    @app.get("/control/seek")
    def _(req: Request, res: Response):
        position = req.query.get("position")
        # player.seek(position)
        logger.info("Seeking to %s", position)
        res.send(control)

    @app.get("/data")
    def _(_, res: Response):
        res.send(data)

    app.listen("0.0.0.0", 8888)


def start_media_control():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(player.main())


p1 = threading.Thread(target=start_media_control, daemon=True)
p2 = threading.Thread(target=start_server, daemon=True)


try:
    p1.start()
    p2.start()

    while p1.is_alive():
        p1.join(1)

    while p2.is_alive():
        p2.join(1)

except KeyboardInterrupt:
    logger.info("Goodbye!")
    sys.exit()
