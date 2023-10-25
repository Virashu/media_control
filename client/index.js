const start = "data:image/png;base64,";
const doc = {
  root: document.documentElement,
  cover: document.getElementById("cover"),
  title: document.getElementById("title"),
  artist: document.getElementById("artist"),
  icon: document.getElementById("btn-pause").firstElementChild,
  // duration: document.getElementById("duration"),
  // position: document.getElementById("position"),
}

update();
setInterval(update, 100);

function control(command) {
  fetch(`http://127.0.0.1:8888/control/${command}`);
}
function render(data) {
  let accent = getAverageRGB(doc.cover);
  doc.root.style.setProperty("--accent", `rgb(${accent.r}, ${accent.g}, ${accent.b})`);
  doc.root.style.setProperty("--cover", `url(${start + data.metadata.cover_data});`);
  doc.cover.src = start + data.metadata.cover_data;
  doc.title.innerText = data.metadata.title;
  doc.artist.innerText = data.metadata.artist;
  state = data.status == "playing" ? true : false;
  doc.icon.setAttribute("class", state ? "fa-solid fa-pause" : "fa-solid fa-play");
  // doc.duration.innerText = data.metadata.duration;
  // doc.position.innerText = data.position;
}

function update() {
  fetch("http://127.0.0.1:8888/data")
    .then((res) => (res ? res.json() : ""))
    .then((res) => (res ? render(res) : ""));
}

function download() {
  downloadBase64Image(doc.cover.src, "cover.png");
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