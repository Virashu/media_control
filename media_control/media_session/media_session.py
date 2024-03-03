"""

Media Control API
"""

__all__ = ["MediaSession", "MediaRepeatMode"]

import asyncio
import json
import logging
from typing import Any, Callable, TypeAlias
from base64 import b64encode
from pprint import pformat
from time import time

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as _MediaManager,
    GlobalSystemMediaTransportControlsSession as _MediaSession,
    #
    GlobalSystemMediaTransportControlsSessionMediaProperties as _MediaProperties,
    GlobalSystemMediaTransportControlsSessionPlaybackInfo as _PlaybackInfo,
    GlobalSystemMediaTransportControlsSessionTimelineProperties as _TimelineProperties,
)

# pylint: disable=no-name-in-module
from winrt.windows.media import MediaPlaybackAutoRepeatMode as MediaRepeatMode

from winrt.windows.storage.streams import (
    Buffer as _Buffer,
    IBuffer as _IBuffer,
    IRandomAccessStreamReference as _StreamReference,
    IRandomAccessStreamWithContentType as _Stream,
    InputStreamOptions as _InputStreamOptions,
)

from ..utils import read_file, read_file_bytes, write_file


def _async_callback(callback: Callable) -> Callable:
    """Use async function as sync callback"""

    def f(*args, **kwargs):
        return asyncio.run(callback(*args, **kwargs))

    return f


logger = logging.getLogger(__name__)


DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]

MediaSessionUpdateCallback: TypeAlias = Callable[[dict[str, Any]], Any]

#############
# Constants #
#############

MEDIA_DATA_TEMPLATE: dict[str, Any] = json.loads(
    read_file(f"{DIRNAME}/../content/template.json")
)
COVER_FILE: str = f"{DIRNAME}/../content/media_thumb.png"
COVER_PLACEHOLDER_FILE: str = f"{DIRNAME}/../content/placeholder.png"
COVER_PLACEHOLDER_RAW: bytes = read_file_bytes(COVER_PLACEHOLDER_FILE)
COVER_PLACEHOLDER_B64: str = b64encode(COVER_PLACEHOLDER_RAW).decode("utf-8")


class MediaSession:
    """Media controller using Windows.Media.Control"""

    def __init__(
        self, callback: MediaSessionUpdateCallback, initial_load: bool = True
    ) -> None:
        self._update_callback = callback
        self._manager: _MediaManager | None = None
        self._session: _MediaSession | None = None

        self._data = MEDIA_DATA_TEMPLATE.copy()
        self._data["media_properties"]["thumbnail_data"] = COVER_PLACEHOLDER_B64

        if initial_load:
            asyncio.run(self.load())

    def _update_data(self, key: Any, value: Any) -> None:
        self._data[key] = value
        self._send_data()

    @property
    def data(self) -> dict[str, Any]:
        """Get media session data"""
        return {
            "provider": self._data["provider"],
            "metadata": {
                "title": self._data["media_properties"]["title"],
                "album": self._data["media_properties"]["album_title"],
                "album_artist": self._data["media_properties"]["album_artist"],
                "artist": self._data["media_properties"]["artist"],
                "cover": self._data["media_properties"]["thumbnail"],
                "cover_data": self._data["media_properties"]["thumbnail_data"],
                "duration": self._data["timeline_properties"]["end_time"],
            },
            "status": self._data["playback_info"]["playback_status"],
            "shuffle": self._data["playback_info"]["is_shuffle_active"],
            "position": self._data["timeline_properties"]["position_soft"],
            "loop": self._data["playback_info"].get("auto_repeat_mode"),
        }

    @property
    def data_raw(self) -> dict[str, Any]:
        """Get media session data"""
        return self._data

    def _send_data(self) -> None:
        self._update_callback(self.data)

    async def load(self) -> None:
        """Load"""

        self._manager = await _MediaManager.request_async()
        self._manager.add_current_session_changed(_async_callback(self._session_events))
        self._manager.add_sessions_changed(_async_callback(self._sessions_changed))

        await self._session_events(self._manager)

        self._send_data()

    async def update(self) -> None:
        """Update"""

        self._update_time()

    async def loop(self) -> None:
        """Main loop"""

        if self._manager is None:
            await self.load()

        while True:
            await self.update()
            await asyncio.sleep(0.1)

    def _update_time(self) -> None:
        if not self._session:
            return
        if self._data["playback_info"]["playback_status"] != "playing":
            return
        now = time()

        position = self._data["timeline_properties"]["position"]
        last_update = self._data["timeline_properties"]["last_updated_time"]
        rate = self._data["playback_info"]["playback_rate"]

        if last_update < 0:
            return

        delta_time = now - last_update
        delta_position = int(rate * delta_time)

        position_now = position + delta_position

        self._data["timeline_properties"]["position_soft"] = min(
            position_now, self._data["timeline_properties"]["end_time"]
        )

        self._send_data()

    async def _session_events(self, *_: Any) -> None:
        logger.info("Session changed")

        if self._manager is None:
            return

        self._session = self._manager.get_current_session()

        if self._session is None:
            return

        self._update_data("provider", self._session.source_app_user_model_id)

        await self._playback_info_changed()
        await self._timeline_properties_changed()
        await self._media_properties_changed()

        self._session.add_media_properties_changed(
            _async_callback(self._media_properties_changed)
        )
        self._session.add_playback_info_changed(
            _async_callback(self._playback_info_changed)
        )
        self._session.add_timeline_properties_changed(
            _async_callback(self._timeline_properties_changed)
        )

    async def _sessions_changed(self, *_: Any) -> None:
        logger.info("Sessions changed")

        if self._manager is None:
            return

        if (sessions := self._manager.get_sessions()) is None:
            return

        sessions = list(sessions)

        logger.debug("Active sessions count: %s", len(sessions))

    async def _try_load_thumbnail(
        self, stream_ref: _StreamReference | None
    ) -> bytes | None:

        if stream_ref is None:
            return

        readable_stream: _Stream = await stream_ref.open_read_async()
        thumb_buffer: _IBuffer = _Buffer(readable_stream.size)  # type: ignore

        try:
            readable_stream.read_async(
                thumb_buffer, thumb_buffer.capacity, _InputStreamOptions.READ_AHEAD
            )

            return bytes(thumb_buffer)

        except OSError as e:
            logger.error("Failed to get thumbnail!\n%s", e)

    async def _media_properties_changed(self, *_) -> None:
        logger.info("Media properties changed")

        if self._session is None:
            return

        try:
            info: _MediaProperties = (
                await self._session.try_get_media_properties_async()
            )
        except PermissionError:
            return

        info_dict = {}
        fields = [
            "album_artist",
            "album_title",
            "album_track_count",
            "artist",
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

        info_dict["genres"] = list(info.genres or [])

        thumb_stream_ref = info.thumbnail

        thumb_img: bytes

        thumb = await self._try_load_thumbnail(thumb_stream_ref)

        if thumb:  # (thumb != None) & (thumb != b"")
            thumb_img = thumb
        else:
            thumb_img = COVER_PLACEHOLDER_RAW
            logger.warning("No correct thumbnail info, using placeholder.")

        write_file(COVER_FILE, thumb_img)

        thumbnail_data: str = b64encode(thumb_img).decode("utf-8")

        info_dict["thumbnail_data"] = thumbnail_data

        info_dict["thumbnail"] = COVER_FILE
        info_dict["thumbnail_url"] = "file:///" + COVER_FILE

        logger.debug(pformat(info_dict))
        self._update_data("media_properties", info_dict)

    async def _playback_info_changed(self, *_):
        logger.info("Playback info changed")

        if self._session is None:
            return

        info: _PlaybackInfo | None = self._session.get_playback_info()

        if info is None:
            return

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

        if not self._session:
            return

        info: _TimelineProperties | None = self._session.get_timeline_properties()

        if info is None:
            return

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

    #
    # PUBLIC METHODS
    #

    async def play(self) -> None:
        """Start playback"""

        if self._session is not None:
            await self._session.try_play_async()

    async def stop(self) -> None:
        """Stop playback"""

        if self._session is not None:
            await self._session.try_stop_async()

    async def pause(self) -> None:
        """Pause playback"""

        if self._session is not None:
            await self._session.try_pause_async()

    async def set_position(self, position: float):
        """Set position in seconds"""

        if self._session is not None:
            await self._session.try_change_playback_position_async(int(position * 1e7))

    async def play_pause(self) -> None:
        """Toggle play/pause"""

        if self._session is not None:
            await self._session.try_toggle_play_pause_async()

    async def next(self) -> None:
        """Select next track"""

        if self._session is not None:
            await self._session.try_skip_next_async()

    async def prev(self) -> None:
        """Select previous track"""

        if self._session is not None:
            await self._session.try_skip_previous_async()

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
        if self._session is not None:
            await self._session.try_change_auto_repeat_mode_async(_mode)

    async def set_shuffle(self, shuffle: bool):
        """shuffle: True, False"""

        if self._session is not None:
            await self._session.try_change_shuffle_active_async(shuffle)

    async def toggle_repeat(self):
        """Toggle repeat (none, track, list)"""

        if self._session is None:
            return
        if (playback_info := self._session.get_playback_info()) is None:
            return
        if (repeat := playback_info.auto_repeat_mode) is None:
            return
        _mode = MediaRepeatMode((repeat + 1) % 3)
        await self._session.try_change_auto_repeat_mode_async(_mode)

    async def toggle_shuffle(self):
        """Toggle shuffle (on, off)"""

        if self._session is None:
            return
        if (playback_info := self._session.get_playback_info()) is None:
            return
        if (shuffle := playback_info.is_shuffle_active) is None:
            return
        await self._session.try_change_shuffle_active_async(not shuffle)

    async def seek_percentage(self, percentage: int | float):
        """Seek to percentage in range [0, 100]"""

        if self._session is None:
            return
        if (timeline_properties := self._session.get_timeline_properties()) is None:
            return
        if (duration := timeline_properties.max_seek_time) is None:
            return
        position = int(duration.total_seconds() * percentage / 100)
        await self.set_position(position)

    async def rewind(self):
        """Idk what it is"""

        if self._session is None:
            return
        await self._session.try_rewind_async()


if __name__ == "__main__":

    def _update(data):
        write_file(f"{DIRNAME}/content/contents.json", json.dumps(data, indent="  "))

    async def _run():
        await _p.loop()
        await asyncio.Future()

    _p = MediaSession(_update)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        ...
