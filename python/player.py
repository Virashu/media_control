from base64 import b64encode
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
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
from utils import *

__all__ = ["Player"]


log.set_level("info")


async def read_stream_into_buffer(
    stream_ref: IRandomAccessStreamReference, buffer: Buffer
) -> None:
    readable_stream = await stream_ref.open_read_async()
    readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]


class Player:
    def __init__(self, callback) -> None:
        self.update_callback = callback
        self.manager = None
        self.session = None
        # self.data = {}
        self.data = json.loads(read_file(f"{DIRNAME}/content/template.json"))
        self.data["media_properties"]["thumbnail_data"] = b64encode(
            open(f"{DIRNAME}/content/placeholder.png", "rb").read()
        ).decode()

    def update_data(self, key, value) -> None:
        self.data[key] = value
        self.send_data()

    def send_data(self):
        data_send = {
            "provider": self.data["provider"],
            "metadata": {
                "title": self.data["media_properties"]["title"],
                "album": self.data["media_properties"]["album_title"],
                "album_artist": self.data["media_properties"]["album_artist"],
                "artist": self.data["media_properties"]["artist"],
                "cover": self.data["media_properties"]["thumbnail"],
                "cover_data": self.data["media_properties"]["thumbnail_data"],
                "duration": self.data["timeline_properties"]["end_time"],
            },
            "status": self.data["playback_info"]["playback_status"],
            "shuffle": self.data["playback_info"]["is_shuffle_active"],
            "position": self.data["timeline_properties"]["position"],
            "loop": self.data["playback_info"]["auto_repeat_mode"],
        }
        self.update_callback(data_send)

    async def main(self) -> None:
        self.manager = await MediaManager.request_async()
        self.manager.add_current_session_changed(async_callback(self.session_events))
        self.manager.add_sessions_changed(async_callback(self.sessions_changed))
        await self.session_events(self.manager)

        if self.session:
            await self.playback_info_changed()
            await self.timeline_properties_changed()
            await self.media_properties_changed()
        self.send_data()

    async def session_events(self, *_):
        log.info(f"Session changed")

        if not self.manager:
            return

        self.session = self.manager.get_current_session()

        if not self.session:
            return

        self.update_data("provider", self.session.source_app_user_model_id)

        await self.playback_info_changed()
        await self.timeline_properties_changed()
        await self.media_properties_changed()

        self.session.add_media_properties_changed(
            async_callback(self.media_properties_changed)
        )
        self.session.add_playback_info_changed(
            async_callback(self.playback_info_changed)
        )
        self.session.add_timeline_properties_changed(
            async_callback(self.timeline_properties_changed)
        )

    async def sessions_changed(self, *_):
        log.info(f"Sessions changed")

        if self.manager is None:
            return

        sessions = list(self.manager.get_sessions())

        log.debug("Active sessions count:", len(sessions))

    async def media_properties_changed(self, *_):
        log.info(f"Media properties changed")

        if not self.session:
            return

        info = await self.session.try_get_media_properties_async()
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
                log.warn(f"Cannot get attribute '{field}'")

        info_dict["genres"] = list(info_dict["genres"])

        thumb_stream_ref = info_dict["thumbnail"]

        thumb_img = read_file_bytes(f"{DIRNAME}/content/placeholder.png")
        if thumb_stream_ref is not None:
            try:
                thumb_read_buffer = Buffer(5000000)
                await read_stream_into_buffer(thumb_stream_ref, thumb_read_buffer)
                buffer_reader = DataReader.from_buffer(thumb_read_buffer)
                byte_buffer = buffer_reader.read_buffer(thumb_read_buffer.length)
                img_bytes = bytes(byte_buffer)
                if img_bytes:
                    thumb_img = img_bytes
            except OSError as e:
                log.error("Failed to get thumbnail!\n", e)
        else:
            log.warn("No correct tumbnail info, using placeholder.")
        # log.kawaii(str(thumb_img))
        thumbnail_data = b64encode(thumb_img).decode("utf-8")
        write_file(f"{DIRNAME}/content/media_thumb.png", thumb_img)
        info_dict["thumbnail"] = f"{DIRNAME}/content/media_thumb.png"
        info_dict["thumbnail_url"] = "file:///" + info_dict["thumbnail"]
        info_dict["thumbnail_data"] = thumbnail_data

        log.debug(pformat(info_dict))
        self.update_data("media_properties", info_dict)

    async def playback_info_changed(self, *_):
        log.info(f"Playback info changed")

        if not self.session:
            return
        info = self.session.get_playback_info()
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
                log.warn(f"Cannot get attribute '{field}'")
        status_codes = {
            0: "closed",
            1: "opened",
            2: "changing",
            3: "stopped",
            4: "playing",
            5: "paused",
        }
        repeat_codes = {
            0: "none",
            1: "track",
            2: "all",
        }
        info_dict["playback_status"] = status_codes[int(info_dict["playback_status"])]
        if (repeat_mode := info_dict["auto_repeat_mode"]) is not None:
            info_dict["auto_repeat_mode"] = repeat_codes[int(repeat_mode)]
        info_dict["controls"] = None
        log.debug(pformat(info_dict))
        self.update_data("playback_info", info_dict)

    async def timeline_properties_changed(self, *_):
        log.info(f"Timeline properties changed")
        if not self.session:
            return

        info = self.session.get_timeline_properties()
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
                log.warn(f"Cannot get attribute '{field}'")

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
        self.update_data("timeline_properties", info_dict)

    async def play(self):
        if self.session is not None:
            await self.session.try_play_async()

    async def stop(self):
        if self.session is not None:
            await self.session.try_stop_async()

    async def pause(self):
        if self.session is not None:
            await self.session.try_pause_async()

    async def set_position(self, position: int):
        if self.session is not None:
            await self.session.try_change_playback_position_async(position)

    async def play_pause(self):
        if self.session is not None:
            await self.session.try_toggle_play_pause_async()

    async def next(self):
        if self.session is not None:
            await self.session.try_skip_next_async()

    async def prev(self):
        if self.session is not None:
            await self.session.try_skip_previous_async()

    async def change_repeat(self, mode: str | int):
        if isinstance(mode, str):
            mode = {"none": 0, "track": 1, "list": 2}[mode]
        if self.session is not None:
            await self.session.try_change_auto_repeat_mode_async(mode)

    async def change_shuffle(self, shuffle: bool):
        if self.session is not None:
            await self.session.try_change_shuffle_async(shuffle)

    async def toggle_repeat(self):
        if self.session is None:
            return
        if (playback_info := self.session.get_playback_info()) is None:
            return
        if (repeat := playback_info.auto_repeat_mode) is None:
            return
        match repeat:
            case 0:
                await self.session.try_change_auto_repeat_mode_async(1)
            case 1:
                await self.session.try_change_auto_repeat_mode_async(2)
            case 2:
                await self.session.try_change_auto_repeat_mode_async(0)

    async def toggle_shuffle(self):
        if self.session is None:
            return
        if (playback_info := self.session.get_playback_info()) is None:
            return
        if (shuffle := playback_info.is_shuffle_active) is None:
            return
        await self.session.try_change_shuffle_async(not shuffle)

    async def seek_percentage(self, percentage: int | float):
        if self.session is None:
            return
        if (timeline_properties := self.session.get_timeline_properties()) is None:
            return
        if (duration := timeline_properties.max_seek_time) is None:
            return
        position = int(duration * percentage)
        await self.session.try_change_playback_position_async(position)


if __name__ == "__main__":

    def update(data):
        write_file(f"{DIRNAME}/content/contents.json", json.dumps(data, indent="  "))

    async def run():
        await _p.main()
        await asyncio.Future()

    _p = Player(update)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        ...
