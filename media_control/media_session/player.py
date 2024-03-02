"""

Media Control API
"""

__all__ = ["Player", "MediaRepeatMode"]

import asyncio
import json
import logging
from typing import Any, Callable, TypeAlias, Optional
import typing as t
from base64 import b64encode
from pprint import pformat
from time import time

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSession as MediaSession,
)

from winrt.windows.media import MediaPlaybackAutoRepeatMode as MediaRepeatMode

from winrt.windows.storage.streams import (
    DataReader,
    Buffer,
    IBuffer,
    InputStreamOptions,
    IRandomAccessStreamReference,
    IRandomAccessStreamWithContentType,
)

from ..utils import read_file, read_file_bytes, write_file


def _async_callback(callback: Callable) -> Callable:
    """Use async function as sync callback"""

    def f(*args, **kwargs):
        return asyncio.run(callback(*args, **kwargs))

    return f


logger = logging.getLogger(__name__)


async def _read_stream_into_buffer(
    stream_ref: IRandomAccessStreamReference, buffer: IBuffer
) -> None:
    readable_stream: IRandomAccessStreamWithContentType = (
        await stream_ref.open_read_async()
    )
    readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]

_PlayerUpdateCallback: TypeAlias = Callable[[dict[str, Any]], Any]

###########
# Constants #
###########

MEDIA_DATA_TEMPLATE: dict[str, Any] = json.loads(
    read_file(f"{DIRNAME}/content/template.json")
)
COVER_FILE: str = f"{DIRNAME}/content/media_thumb.png"
COVER_PLACEHOLDER_FILE: str = f"{DIRNAME}/content/placeholder.png"
COVER_PLACEHOLDER_RAW: bytes = read_file_bytes(COVER_PLACEHOLDER_FILE)
COVER_PLACEHOLDER_B64: str = b64encode(COVER_PLACEHOLDER_RAW).decode("utf-8")


class Player:
    """Media controller using Windows.Media.Control"""

    def __init__(self, callback: _PlayerUpdateCallback) -> None:
        self.update_callback = callback
        self.manager: Optional[MediaManager] = None
        self.session: MediaSession | None = None

        self.data = MEDIA_DATA_TEMPLATE.copy()
        self.data["media_properties"]["thumbnail_data"] = COVER_PLACEHOLDER_B64

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

    async def load(self) -> None:
        """Load"""

        self.manager = await MediaManager.request_async()
        self.manager.add_current_session_changed(_async_callback(self._session_events))
        self.manager.add_sessions_changed(_async_callback(self._sessions_changed))
        await self._session_events(self.manager)

        if self.session:
            await self._playback_info_changed()
            await self._timeline_properties_changed()
            await self._media_properties_changed()

        self._send_data()

    async def main(self) -> None:
        """Main loop"""

        await self.load()

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

    async def _session_events(self, *_: t.Any):
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
            _async_callback(self._media_properties_changed)
        )
        self.session.add_playback_info_changed(
            _async_callback(self._playback_info_changed)
        )
        self.session.add_timeline_properties_changed(
            _async_callback(self._timeline_properties_changed)
        )

    async def _sessions_changed(self, *_: t.Any):
        logger.info("Sessions changed")

        if self.manager is None:
            return

        if (sessions := self.manager.get_sessions()) is None:
            return

        sessions = list(sessions)

        logger.debug("Active sessions count: %s", len(sessions))

    async def _try_load_thumbnail(
        self, stream_ref: IRandomAccessStreamReference
    ) -> bytes | None:
        if stream_ref is None:
            return

        try:
            thumb_read_buffer: IBuffer = Buffer(5_000_000)  # type: ignore
            await _read_stream_into_buffer(stream_ref, thumb_read_buffer)

            buffer_reader = DataReader.from_buffer(thumb_read_buffer)
            if buffer_reader is None:
                return

            byte_buffer = buffer_reader.read_buffer(thumb_read_buffer.length)
            if byte_buffer is None:
                return

            return bytes(byte_buffer)

        except OSError as e:
            logger.error("Failed to get thumbnail!\n%s", e)

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

        thumb_img: bytes

        thumb = await self._try_load_thumbnail(thumb_stream_ref)

        if thumb is not None:
            thumb_img = thumb
        else:
            thumb_img = COVER_PLACEHOLDER_RAW
            logger.warning("No correct thumbnail info, using placeholder.")

        write_file(COVER_FILE, thumb_img)

        thumbnail_data: str = b64encode(thumb_img).decode("utf-8")

        info_dict["thumbnail"] = COVER_FILE
        info_dict["thumbnail_url"] = "file:///" + COVER_FILE
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

    async def set_position(self, position: float):
        """Set position in seconds"""

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

    previous = prev

    async def set_repeat(self, mode: str | int | MediaRepeatMode):
        """Set repeat mode

        Available modes: 'none', 'track', 'list'"""

        _mode: MediaRepeatMode
        if isinstance(mode, str):
            _mode = {
                "none": MediaRepeatMode.NONE,
                "track": MediaRepeatMode.TRACK,
                "list": MediaRepeatMode.LIST,
            }.get(mode, MediaRepeatMode.NONE)
        elif isinstance(mode, int):
            _mode = MediaRepeatMode(mode)
        else:
            _mode = mode
        if self.session is not None:
            await self.session.try_change_auto_repeat_mode_async(_mode)

    async def set_shuffle(self, shuffle: bool):
        """shuffle: True, False"""

        if self.session is not None:
            await self.session.try_change_shuffle_active_async(shuffle)

    async def toggle_repeat(self):
        """Toggle repeat (none, track, list)"""

        if self.session is None:
            return
        if (playback_info := self.session.get_playback_info()) is None:
            return
        if (repeat := playback_info.auto_repeat_mode) is None:
            return
        _mode = MediaRepeatMode((repeat + 1) % 3)
        await self.session.try_change_auto_repeat_mode_async(_mode)

    async def toggle_shuffle(self):
        """Toggle shuffle (on, off)"""

        if self.session is None:
            return
        if (playback_info := self.session.get_playback_info()) is None:
            return
        if (shuffle := playback_info.is_shuffle_active) is None:
            return
        await self.session.try_change_shuffle_active_async(not shuffle)

    async def seek_percentage(self, percentage: int | float):
        """Seek to percentage in range [0, 100]"""

        if self.session is None:
            return
        if (timeline_properties := self.session.get_timeline_properties()) is None:
            return
        if (duration := timeline_properties.max_seek_time) is None:
            return
        position = int(duration.total_seconds() * percentage / 100)
        await self.set_position(position)

    async def rewind(self):
        """Idk what it is"""

        if self.session is None:
            return
        await self.session.try_rewind_async()


if __name__ == "__main__":

    def _update(data):
        write_file(f"{DIRNAME}/content/contents.json", json.dumps(data, indent="  "))

    async def _run():
        await _p.main()
        await asyncio.Future()

    _p = Player(_update)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        ...
