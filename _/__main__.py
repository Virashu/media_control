# https://stackoverflow.com/questions/65011660/how-can-i-get-the-title-of-the-currently-playing-media-in-windows-10-with-python

import asyncio
from pprint import pprint

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winrt.windows.storage.streams import DataReader, Buffer, InputStreamOptions


async def read_stream_into_buffer(stream_ref, buffer):
    readable_stream = await stream_ref.open_read_async()
    readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)


def set_title(title):
    return f"\x1b]2;{title}\a"


def clear_screen(mode=2):
    return f"\x1b[{mode}J"


def clear_line(mode=2):
    return f"\x1b[{mode}K"


async def get_media_info():
    sessions = await MediaManager.request_async()

    # This source_app_user_model_id check and if statement is optional
    # Use it if you want to only get a certain player/program's media
    # (e.g. only chrome.exe's media not any other program's).

    # To get the ID, use a breakpoint() to run sessions.get_current_session()
    # while the media you want to get is playing.
    # Then set TARGET_ID to the string this call returns.

    current_session = sessions.get_current_session()
    if current_session:  # there needs to be a media session running
        info = await current_session.try_get_media_properties_async()

        # song_attr[0] != '_' ignores system attributes
        info_dict = {}
        for song_attr in dir(info):
            if song_attr[0] != "_":
                try:
                    info_dict[song_attr] = info.__getattribute__(song_attr)
                except AttributeError:
                    print(f"(-) Cannot get attribute '{song_attr}'")

        # converts winrt vector to list
        info_dict["genres"] = list(info_dict["genres"])

        # create the current_media_info dict with the earlier code first
        thumb_stream_ref = info_dict["thumbnail"]

        # 5MB (5 million byte) buffer - thumbnail unlikely to be larger
        thumb_read_buffer = Buffer(5000000)

        # copies data from data stream reference into buffer created above
        await read_stream_into_buffer(thumb_stream_ref, thumb_read_buffer)

        # reads data (as bytes) from buffer
        buffer_reader = DataReader.from_buffer(thumb_read_buffer)
        byte_buffer = buffer_reader.read_buffer(thumb_read_buffer.length)

        with open("media_thumb.jpg", "wb+") as fobj:
            fobj.write(bytearray(byte_buffer))

        return info_dict

    # It could be possible to select a program from a list of current
    # available ones. I just haven't implemented this here for my use case.
    # See references for more information.
    raise Exception("TARGET_PROGRAM is not the current media session")


if __name__ == "__main__":
    current_media_info = asyncio.run(get_media_info())
    print(clear_screen(), end="")
    pprint(current_media_info)
