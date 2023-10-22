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


async def get_media_info():
    current_session = (await MediaManager.request_async()).get_current_session()
    info = await current_session.try_get_media_properties_async()
    info_dict = {}
    for song_attr in dir(info):
        if song_attr[0] != "_":
            try:
                info_dict[song_attr] = info.__getattribute__(song_attr)
            except AttributeError:
                print(f"(-) Cannot get attribute '{song_attr}'")
    info_dict["genres"] = list(info_dict["genres"])

    # Thumbnail
    thumb_stream_ref = info_dict["thumbnail"]
    thumb_read_buffer = Buffer(5000000)
    await read_stream_into_buffer(thumb_stream_ref, thumb_read_buffer)
    buffer_reader = DataReader.from_buffer(thumb_read_buffer)
    byte_buffer = buffer_reader.read_buffer(thumb_read_buffer.length)
    with open("media_thumb.jpg", "wb+") as fobj:
        fobj.write(bytearray(byte_buffer))
    return info_dict


async def current_session_changed():
    print("Session changed!")


MediaManager.add_current_session_changed(MediaManager, current_session_changed)
current_media_info = asyncio.run(get_media_info())
pprint(current_media_info)
