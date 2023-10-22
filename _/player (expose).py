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


# log.set_level("none")


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
        self.data = json.loads(open(f"{DIRNAME}/content/template.json", "r").read())

    def update_data(self, key, value) -> None:
        self.data[key] = value
        self.update_callback(self.data)

    async def main(self) -> None:
        self.manager = await MediaManager.request_async()
        self.manager.add_current_session_changed(ahandler(self.session_events))
        self.manager.add_sessions_changed(ahandler(self.sessions_changed))
        await self.session_events(self.manager)

        if self.session:
            await self.playback_info_changed()
            await self.timeline_properties_changed()
            await self.media_properties_changed()

    async def session_events(self, *_):
        log.info(f"Session changed")

        if not self.manager:
            return

        self.session = self.manager.get_current_session()

        if not self.session:
            return

        self.update_data("provider", self.session.source_app_user_model_id)

        self.session.add_media_properties_changed(
            ahandler(self.media_properties_changed)
        )
        self.session.add_playback_info_changed(ahandler(self.playback_info_changed))
        self.session.add_timeline_properties_changed(
            ahandler(self.timeline_properties_changed)
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

        if thumb_stream_ref is not None:
            thumb_read_buffer = Buffer(5000000)
            await read_stream_into_buffer(thumb_stream_ref, thumb_read_buffer)
            buffer_reader = DataReader.from_buffer(thumb_read_buffer)
            byte_buffer = buffer_reader.read_buffer(thumb_read_buffer.length)
            thumb_img = bytes(byte_buffer)
        else:
            log.warn("Cannot save the thumbnail")
            thumb_img = read_file_bytes(f"{DIRNAME}/content/placeholder.png")
        write_file(f"{DIRNAME}/content/media_thumb.png", thumb_img)
        info_dict["thumbnail"] = f"{DIRNAME}/content/media_thumb.jpg"
        info_dict["thumbnail_url"] = "file:///" + info_dict["thumbnail"]

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
        info_dict["playback_status"] = status_codes[int(info_dict["playback_status"])]
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
        if (playback_info := self.data.get("playback_info")) is None:
            return
        if (repeat := playback_info.get("auto_repeat_mode")) is None:
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
        if (shuffle := self.data.get("is_shuffle_active")) is None:
            return
        await self.session.try_change_shuffle_async(not shuffle)

    async def seek_percentage(self, percentage: int | float):
        if self.session is None:
            return
        if (playback_info := self.data.get("playback_info")) is None:
            return
        if (duration := playback_info.get("duration")) is None:
            return
        position = int(duration * percentage)
        await self.session.try_change_playback_position_async(position)


if __name__ == "__main__":

    def update(data):
        # print(data)
        pass

    async def run():
        await _p.main()
        await asyncio.Future()

    _p = Player(update)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\x1b[2J", end="")
