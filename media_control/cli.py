"""Cli"""

import asyncio
import copy
import json
import logging
import os
import sys
import threading
import time
import typing as t

from media_session import AbstractMediaSession, MediaSession
from media_session import constants as settings
from media_session.datastructures import MediaInfo
from saaba import App, Request, Response

from .utils import CustomFormatter, write_file

logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(
    CustomFormatter(
        "{levelname:<10} | {name:<32} | {message}",
        style="{",
    )
)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

logging.getLogger("http.server").disabled = True
logging.getLogger("saaba").disabled = True


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]
STATIC_PATH = f"{DIRNAME}/static"

if not os.path.exists(STATIC_PATH):
    os.mkdir(STATIC_PATH)

settings.COVER_FILE = f"{STATIC_PATH}/media_thumb.png"

data: dict[str, t.Any] = {}


def update(info: MediaInfo) -> None:
    info_dict = info.as_dict()
    data.update(info_dict)
    write_file(f"{STATIC_PATH}/contents.json", json.dumps(info_dict, indent="  "))


player: AbstractMediaSession = MediaSession(update)
type AsyncPlayerCommand = t.Callable[[], t.Coroutine[t.Any, t.Any, None]]

# id (url) : Callable
commands: dict[str, AsyncPlayerCommand] = {
    "pause": player.play_pause,
    "prev": player.prev,
    # "repeat": player.toggle_repeat,
    # "shuffle": player.toggle_shuffle,
    "play": player.play,
    "stop": player.stop,
    "next": player.next,
}


def create_command(app: App, name: str, command: AsyncPlayerCommand):
    @app.route(["get", "post"], f"/control/{name}")
    def _(_, res: Response):
        logger.info("Running command: %s", name)
        asyncio.run(command())
        res.send("")


def start_server():
    app = App()

    @app.get("/")
    def _(_, res: Response):
        res.send(
            """
            <h1>MediaControl API</h1>
            <p>This is API please consider using frontend for it.</p>
            <br>
            <a href="/data"> data </a>
            """
        )

    for command in commands.items():
        create_command(app, *command)

    @app.get("/control/seek")
    def _(req: Request, res: Response):
        logger.info("Got command: seek")
        if req.query is None:
            return
        position = req.query.get("position")
        if not isinstance(position, str):
            return
        if not position.isnumeric():
            return
        position = int(float(position))
        asyncio.run(player.seek_percentage(position))
        logger.info("Seeking to %s", position)
        res.send("")

    @app.post("/control/seek")
    def _(req: Request, res: Response):
        logger.info("Got command: seek")

        if req.body is None:
            return

        position = req.body.get("position")

        if not isinstance(position, (float, int)):
            return

        asyncio.run(player.seek_percentage(position))
        logger.info("Seeking to %s%", position)

        res.send("")

    @app.get("/data")
    def _(req: Request, res: Response):
        if (not req.query) or req.query.get("cover", "true") == "true":
            res.send(data)
        else:
            temp_data = copy.deepcopy(data)
            del temp_data["metadata"]["cover_data"]
            res.send(temp_data)

    app.listen("0.0.0.0", 8888)


def start_media_control():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(player.loop())


def main():
    p1 = threading.Thread(target=start_media_control, daemon=True)
    p2 = threading.Thread(target=start_server, daemon=True)

    try:
        p1.start()
        p2.start()

        while threading.active_count() > 1:
            time.sleep(1e6)

    except KeyboardInterrupt:
        sys.exit()
