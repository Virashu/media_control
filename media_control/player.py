__all__ = ["Player"]

import asyncio
import json
import logging
from base64 import b64encode
from pprint import pformat
from time import time
from typing import Any, Callable

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

from .utils import read_file, read_file_bytes, async_callback, write_file


logger = logging.getLogger(__name__)


async def read_stream_into_buffer(
    stream_ref: IRandomAccessStreamReference, buffer: Buffer
) -> None:
    readable_stream = await stream_ref.open_read_async()
    readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]


class Player:
    """Media controller using Windows.Media.Control"""

    def __init__(self, callback: Callable) -> None:
        self.update_callback = callback
        self.manager: MediaManager | None = None
        self.session: MediaSession | None = None
        # self.data = {}
        self.data = json.loads(read_file(f"{DIRNAME}/content/template.json"))
        self.data["media_properties"]["thumbnail_data"] = b64encode(
            read_file_bytes(f"{DIRNAME}/content/placeholder.png")
        ).decode()

    def _update_data(self, key: Any, value: Any) -> None:
        self.data[key] = value
        self._send_data()

    def _send_data(self):
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
            "position": self.data["timeline_properties"]["position_soft"],
            "loop": self.data["playback_info"].get("auto_repeat_mode"),
        }
        self.update_callback(data_send)

    async def main(self) -> None:
        self.manager = await MediaManager.request_async()
        self.manager.add_current_session_changed(async_callback(self._session_events))
        self.manager.add_sessions_changed(async_callback(self._sessions_changed))
        await self._session_events(self.manager)

        if self.session:
            await self._playback_info_changed()
            await self._timeline_properties_changed()
            await self._media_properties_changed()

        self._send_data()

        while True:
            self._update_time()

            await asyncio.sleep(0.1)

    def _update_time(self):
        if not self.session:
            return
        if self.data["playback_info"]["playback_status"] != "playing":
            return
        now = time()

        position = self.data["timeline_properties"]["position"]
        last_update = self.data["timeline_properties"]["last_updated_time"]
        rate = self.data["playback_info"]["playback_rate"]

        if last_update < 0:
            return

        delta_time = now - last_update
        delta_position = int(rate * delta_time)

        position_now = position + delta_position

        self.data["timeline_properties"]["position_soft"] = min(
            position_now, self.data["timeline_properties"]["end_time"]
        )

        self._send_data()

    async def _session_events(self, *_: Any):
        logger.info("Session changed")

        if not self.manager:
            return

        self.session = self.manager.get_current_session()

        if not self.session:
            return

        self._update_data("provider", self.session.source_app_user_model_id)

        await self._playback_info_changed()
        await self._timeline_properties_changed()
        await self._media_properties_changed()

        self.session.add_media_properties_changed(
            async_callback(self._media_properties_changed)
        )
        self.session.add_playback_info_changed(
            async_callback(self._playback_info_changed)
        )
        self.session.add_timeline_properties_changed(
            async_callback(self._timeline_properties_changed)
        )

    async def _sessions_changed(self, *_: Any):
        logger.info("Sessions changed")

        if self.manager is None:
            return

        if (sessions := self.manager.get_sessions()) is None:
            return

        sessions = list(sessions)

        logger.debug("Active sessions count: %s", len(sessions))

    async def _media_properties_changed(self, *_):
        logger.info("Media properties changed")

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
                info_dict[field] = getattr(info, field)
            except AttributeError:
                logger.warning("Cannot get attribute '%s'", field)

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
                logger.error("Failed to get thumbnail!\n%s", e)
        else:
            logger.warning("No correct thumbnail info, using placeholder.")
        # log.kawaii(str(thumb_img))
        thumbnail_data = b64encode(thumb_img).decode("utf-8")
        write_file(f"{DIRNAME}/content/media_thumb.png", thumb_img)
        info_dict["thumbnail"] = f"{DIRNAME}/content/media_thumb.png"
        info_dict["thumbnail_url"] = "file:///" + info_dict["thumbnail"]
        info_dict["thumbnail_data"] = thumbnail_data

        logger.debug(pformat(info_dict))
        self._update_data("media_properties", info_dict)

    async def _playback_info_changed(self, *_):
        logger.info("Playback info changed")

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
                info_dict[field] = getattr(info, field)
            except AttributeError:
                logger.warning("Cannot get attribute '%s'", field)
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
        if (repeat_mode := info_dict.get("auto_repeat_mode")) is not None:
            info_dict["auto_repeat_mode"] = repeat_codes[int(repeat_mode)]
        info_dict["controls"] = None
        logger.debug(pformat(info_dict))
        self._update_data("playback_info", info_dict)

    async def _timeline_properties_changed(self, *_):
        logger.info("Timeline properties changed")
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
                info_dict[field] = getattr(info, field)
            except AttributeError:
                logger.warning("Cannot get attribute '%s'", field)

        for f in (
            "end_time",
            "max_seek_time",
            "min_seek_time",
            "position",
            "start_time",
        ):
            info_dict[f] = int(info_dict[f].total_seconds())
        info_dict["last_updated_time"] = int(info_dict["last_updated_time"].timestamp())
        info_dict["position_soft"] = info_dict["position"]
        logger.debug(pformat(info_dict))
        self._update_data("timeline_properties", info_dict)

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
        """Position in seconds"""
        if self.session is not None:
            await self.session.try_change_playback_position_async(int(position * 1e7))

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
        """mode: 'none', 'track', 'list'"""
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
        await self.session.try_change_auto_repeat_mode_async((repeat + 1) % 3)

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
        position = int(duration.total_seconds() * percentage / 100)
        await self.set_position(position)

    async def rewind(self):
        if self.session is None:
            return
        await self.session.try_rewind_async()


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
