"""Cli"""

import asyncio
import json
import copy
import logging
import sys
import threading
import typing as t
import time

from media_session import media_session, MediaSession
from saaba import App, Request, Response

from .utils import write_file, CustomFormatter


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


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]
media_session.COVER_FILE = f"{DIRNAME}/static/media_thumb.png"


data: dict[str, t.Any] = {}


def update(d) -> None:
    data.update(d)
    write_file(f"{DIRNAME}/static/contents.json", json.dumps(data, indent="  "))


player = MediaSession(update)

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

        if isinstance(position, (float, int)):
            return

        # Pylance can't recognize isinstance() with tuples
        asyncio.run(player.seek_percentage(position))  # type: ignore
        logger.info("Seeking to %s", position)

        res.send("")

    @app.get("/data")
    def _(req: Request, res: Response):
        if req.query and req.query.get("cover", "true") == "true":
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
