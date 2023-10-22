from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSession as MediaSession,
)

from winrt.windows.storage.streams import (
    DataReader,
    Buffer,
    InputStreamOptions,
    IRandomAccessStreamReference,
)

import asyncio
import json
from pprint import pformat

import log
import server
from utils import *


async def read_stream_into_buffer(
    stream_ref: IRandomAccessStreamReference, buffer: Buffer
) -> None:
    readable_stream = await stream_ref.open_read_async()
    readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)


data = {}
__dirname = __file__.replace("\\", "/").rsplit("/", 1)[0]
current_session: MediaSession = None


def update_data(key, value, save=True) -> None:
    data[key] = value
    if save:
        write_file(__dirname + "/contents.json", json.dumps(data, indent="  "))


async def main():
    global current_session
    manager = await MediaManager.request_async()
    manager.add_current_session_changed(ahandler(manager_current_session_changed))
    session = await manager_current_session_changed(manager)

    if session:
        await session_playback_info_changed(session)
        await session_timeline_properties_changed(session)
        await session_media_properties_changed(session)

    await asyncio.Future()


async def manager_current_session_changed(manager, _=None):
    global current_session
    log.info(f"Session changed")

    current_session = manager.get_current_session()

    if not current_session:
        return None

    current_session.add_media_properties_changed(
        ahandler(session_media_properties_changed)
    )
    current_session.add_playback_info_changed(ahandler(session_playback_info_changed))
    current_session.add_timeline_properties_changed(
        ahandler(session_timeline_properties_changed)
    )

    return current_session


async def session_media_properties_changed(session, _=None):
    log.info(f"Media properties changed")

    info = await session.try_get_media_properties_async()
    info_dict = {}
    fields = [
        "album_artist",
        "album_title",
        "album_track_count",
        "artist",
        "genres",
        "subtitle",
        "thumbnail",
        "title",
        "track_number",
        "playback_type",
    ]

    for field in fields:
        try:
            info_dict[field] = info.__getattribute__(field)
        except AttributeError:
            log.warning(f"Cannot get attribute '{field}'")

    info_dict["genres"] = list(info_dict["genres"])

    thumb_stream_ref = info_dict["thumbnail"]

    if thumb_stream_ref is not None:
        thumb_read_buffer = Buffer(5000000)
        await read_stream_into_buffer(thumb_stream_ref, thumb_read_buffer)
        buffer_reader = DataReader.from_buffer(thumb_read_buffer)
        byte_buffer = buffer_reader.read_buffer(thumb_read_buffer.length)
        thumb_img = bytes(byte_buffer)
    else:
        log.warning("Cannot save the thumbnail")
        thumb_img = read_file_bytes(f"{__dirname}/content/placeholder.png")
    write_file(f"{__dirname}/content/media_thumb.png", thumb_img)
    info_dict["thumbnail"] = f"{__dirname}/content/media_thumb.jpg"
    info_dict["thumbnail_url"] = "file:///" + info_dict["thumbnail"]

    log.debug(pformat(info_dict))
    update_data("media_properties", info_dict)


async def session_playback_info_changed(session, _=None):
    log.info(f"Playback info changed")

    info = session.get_playback_info()
    info_dict = {}
    fields = (
        "auto_repeat_mode",
        "controls",
        "is_shuffle_active",
        "playback_rate",
        "playback_status",
        "playback_type",
    )
    for field in fields:
        try:
            info_dict[field] = info.__getattribute__(field)
        except AttributeError:
            log.warning(f"Cannot get attribute '{field}'")
    status_codes = {
        0: "closed",
        1: "opened",
        2: "changing",
        3: "stopped",
        4: "playing",
        5: "paused",
    }
    info_dict["playback_status"] = status_codes[int(info_dict["playback_status"])]
    info_dict["controls"] = None
    log.debug(pformat(info_dict))
    update_data("playback_info", info_dict)


async def session_timeline_properties_changed(session, _=None):
    log.info(f"Timeline properties changed")
    info = session.get_timeline_properties()
    info_dict = {}

    fields = (
        "end_time",
        "last_updated_time",
        "max_seek_time",
        "min_seek_time",
        "position",
        "start_time",
    )

    for field in fields:
        try:
            info_dict[field] = info.__getattribute__(field)
        except AttributeError:
            log.warning(f"Cannot get attribute '{field}'")

    for f in (
        "end_time",
        "max_seek_time",
        "min_seek_time",
        "position",
        "start_time",
    ):
        info_dict[f] = int(info_dict[f].total_seconds())
    info_dict["last_updated_time"] = int(info_dict["last_updated_time"].timestamp())
    log.debug(pformat(info_dict))
    update_data("timeline_properties", info_dict)


async def control_toggle_play_pause():
    if current_session is not None:
        await current_session.try_toggle_play_pause_async()


async def control_next():
    if current_session is not None:
        await current_session.try_skip_next_async()


async def control_prev():
    if current_session is not None:
        await current_session.try_skip_previous_async()


def start_server():
    control = read_file(__dirname + "/control.html")

    commands = (
        {
            "name": "pause",
            "friendly_name": "Pause",
            "function": control_toggle_play_pause,
        },
        {
            "name": "prev",
            "friendly_name": "Previous",
            "function": control_prev,
        },
        {
            "name": "next",
            "friendly_name": "Next",
            "function": control_next,
        },
    )

    app = server.App()

    @app.get("/")
    def _(req, res):
        res.send('<a href="/control">control</a><br><a href="/data">data</a>')

    @app.get("/control")
    def _(req, res):
        res.send(control)

    for command in commands:

        @app.get(f"/control/{command['name']}")
        def _(req, res):
            asyncio.run(command["function"]())
            res.send(control)

    @app.get("/data")
    def _(req, res):
        res.send(data)

    app.listen("0.0.0.0", 8888, lambda: log.info("Server started!"))


def start_media_control():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())


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
