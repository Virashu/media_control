import wmc from "@nodert-win10-21h1/windows.media.control";
import streams from "@nodert-win10-21h1/windows.storage.streams";
import fs from 'node:fs';


/** 
 * @param {streams.IRandomAccessStreamReference} stream_ref 
 * @param {streams.Buffer} buffer 
 */
async function read_stream_into_buffer(stream_ref, buffer) {
  stream_ref.openReadAsync(async (err, readable_stream) => {
    if (err) return void console.log(err);
    await readable_stream.ReadAsync(buffer, buffer.capacity, streams.InputStreamOptions.READ_AHEAD, () => {})
  });
}

wmc.GlobalSystemMediaTransportControlsSessionManager.requestAsync((err, sessions) => {
  var current_session = sessions.getCurrentSession();
  current_session.tryGetMediaPropertiesAsync(async (err, props) => {
    var info = {};
    for (var key in props) {
      if (key[0] === '_') continue;
      info[key] = props[key];
    }
    var genres = [];
    for (let i = 0; i < info.genres.length; i++) {
      genres.push(info.genres[i]);
    }
    info.genres = genres;
    console.log(info);
    /* Thumbnail */
    let thumb_stream_ref = info.thumbnail;
    let thumb_read_buffer = streams.Buffer(5000000);
    await read_stream_into_buffer(thumb_stream_ref, thumb_read_buffer)
    let buffer_reader = streams.DataReader.fromBuffer(thumb_read_buffer)
    let byte_buffer = buffer_reader.readBuffer(thumb_read_buffer.length)
    fs.writeFileSync("media_thumb.jpg", new Uint8Array(byte_buffer), "binary")
  });
});
