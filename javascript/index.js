import MediaControl from "@nodert-win10-21h1/windows.media.control";
import Streams from "@nodert-win10-21h1/windows.storage.streams";
import fs from 'node:fs';

function unwrap(func, ...args) {
  return new Promise(resolve => {
    func(...args, response => resolve(response));
  });
}

/** 
 * @param {Streams.IRandomAccessStreamReference} stream_ref 
 * @param {Streams.Buffer} buffer 1
 */
function huy(stream_ref) {
  return new Promise(resolve => {
    stream_ref.openReadAsync(async (err, readable_stream) => {
      resolve(readable_stream)
    });
  });
}

async function readStream(stream_ref) {
  var readable_stream = await huy(stream_ref);
  var ibuffer = await Streams.DataReader(readable_stream).readBuffer(1);
  return ibuffer;
}

MediaControl.GlobalSystemMediaTransportControlsSessionManager.requestAsync((err, sessions) => {
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
    var r = await readStream(thumb_stream_ref, 5000000);
    var thumb_read_buffer = Streams.Buffer.createMemoryBufferOverIBuffer(r);
    let buffer_reader = Streams.DataReader.fromBuffer(thumb_read_buffer)
    let byte_buffer = buffer_reader.readBuffer(thumb_read_buffer.length)
    fs.writeFileSync("media_thumb.jpg", new Uint8Array(byte_buffer), "binary")
  });
});
