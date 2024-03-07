"use strict";

/*
 * CAUTION
 *
 * Bad code
 *
**/

const $ = selectors => document.querySelector(selectors);
const docRoot = document.documentElement;
const pauseIcon = $("button#btn-pause").firstElementChild;
const b64Start = "data:image/png;base64,";

var wakeLock;
var host = null;

function updateHostName() {
  host = window.location.host;
  if (host === "") host = "127.0.0.1";
}

async function setWakeLock() {
  if (wakeLock) return;
  if (!navigator.wakeLock) return;
  wakeLock = await navigator.wakeLock.request("screen");
}

function control(command) {
  fetch(`http://${host}:8888/control/${command}`);
}

function seek(e) {
  const percent = e.offsetX / e.target.offsetWidth;
  // docRoot.style.setProperty("--progress", `${percent * 100}%`);
  control(`seek?position=${percent * 100}`);
}

function render(data) {
  // Get play state & set icon

  let state = data.status == "playing" ? true : false;
  pauseIcon.setAttribute("class", state ? "fa-solid fa-pause" : "fa-solid fa-play");

  // Get full cover
  let cover_b64 = data.metadata.cover_data;
  let full_cover = b64Start + cover_b64

  $("#cover").src = full_cover;
  docRoot.style.setProperty("--cover", `url(${full_cover});`);

  let accent = getAverageRGB($("#cover"));
  docRoot.style.setProperty("--accent", `rgb(${accent.r}, ${accent.g}, ${accent.b})`);

  $("#title").innerText = data.metadata.title;
  $("#artist").innerText = data.metadata.artist;

  // data.metadata.duration
  // data.position
  docRoot.style.setProperty("--progress", `${data.position / data.metadata.duration * 100}%`);
}

async function update() {
  let response = await fetch(`http://${host}:8888/data`, { mode: "cors" });

  if (!response) return;

  let data = await response.json();

  render(data);
}

function download() {
  downloadBase64Image($("#cover").src, "cover.png");
}

async function downloadBase64Image(url, filename) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
}

function getAverageRGB(imgEl) {

  var blockSize = 5, // only visit every 5 pixels
    defaultRGB = { r: 0, g: 0, b: 0 }, // for non-supporting envs
    canvas = document.createElement('canvas'),
    context = canvas.getContext && canvas.getContext('2d'),
    data, width, height,
    i = -4,
    length,
    rgb = { r: 0, g: 0, b: 0 },
    count = 0;

  if (!context) {
    return defaultRGB;
  }

  height = canvas.height = imgEl.naturalHeight || imgEl.offsetHeight || imgEl.height;
  width = canvas.width = imgEl.naturalWidth || imgEl.offsetWidth || imgEl.width;

  context.drawImage(imgEl, 0, 0);

  try {
    data = context.getImageData(0, 0, width, height);
  } catch (e) {
    /* security error, img on diff domain */
    return defaultRGB;
  }

  length = data.data.length;

  while ((i += blockSize * 4) < length) {
    ++count;
    rgb.r += data.data[i];
    rgb.g += data.data[i + 1];
    rgb.b += data.data[i + 2];
  }

  // ~~ used to floor values
  rgb.r = ~~(rgb.r / count);
  rgb.g = ~~(rgb.g / count);
  rgb.b = ~~(rgb.b / count);

  return rgb;
}

function toggleFullScreen() {
  if (!document.fullscreenElement) {
    docRoot.requestFullscreen();
  } else if (document.exitFullscreen) {
    document.exitFullscreen();
  }
}

$("#fullscreen").addEventListener("click", toggleFullScreen);
$("#seekbar").addEventListener("click", seek);
$("#download").addEventListener("click", download);

setWakeLock(); // Prevent screen from sleeping
if (!host) updateHostName(); // If host is not set, try to guess

update();
setInterval(update, 1000);
