"use strict";

/*
 * CAUTION
 *
 * Bad code
 *
**/

const $ = document.querySelector;
const docRoot = document.documentElement;
const pauseIcon = $("#btn-pause").firstElementChild;
const b64Start = "data:image/png;base64,";

var wakeLock;
var host = null;

function updateHostName() {
  host = window.location.host;
  if (host === "") host = "127.0.0.1";
}

async function setWakeLock() {
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
  let accent = getAverageRGB($("#cover"));
  docRoot.style.setProperty("--accent", `rgb(${accent.r}, ${accent.g}, ${accent.b})`);
  docRoot.style.setProperty("--cover", `url(${b64Start + data.metadata.cover_data});`);
  $("#cover").cover.src = b64Start + data.metadata.cover_data;
  $("#title").innerText = data.metadata.title;
  $("#artist").innerText = data.metadata.artist;
  let state = data.status == "playing" ? true : false;
  pauseIcon.setAttribute("class", state ? "fa-solid fa-pause" : "fa-solid fa-play");
  // data.metadata.duration
  // data.position
  docRoot.style.setProperty("--progress", `${data.position / data.metadata.duration * 100}%`);
}

function update() {
  fetch(`http://${host}:8888/data`)
    .then((res) => (res ? res.json() : ""))
    .then((res) => (res ? render(res) : ""));
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




setWakeLock(); // Prevent screen from sleeping
if (!host) updateHostName(); // If host is not set, try to guess

update();
setInterval(update, 1000);
