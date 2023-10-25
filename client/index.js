const start = "data:image/png;base64,";
const doc = {
  root: document.documentElement,
  cover: document.getElementById("cover"),
  title: document.getElementById("title"),
  artist: document.getElementById("artist"),
  duration: document.getElementById("duration"),
  position: document.getElementById("position"),
}

update();
setInterval(update, 1000);

function control(command) {
  fetch(`http://127.0.0.1:8888/control/${command}`);
}

function render(data) {
  doc.root.style.setProperty("--accent", `rgb(${data.metadata.accent})`);
  doc.root.style.setProperty("--cover", `url(${start + data.metadata.cover_data});`);
  doc.cover.src = start + data.metadata.cover_data;
  doc.title.innerText = data.metadata.title;
  doc.artist.innerText = data.metadata.artist;
  doc.duration.innerText = data.metadata.duration;
  doc.position.innerText = data.position;
}

function update() {
  fetch("http://127.0.0.1:8888/data")
    .then((res) => (res ? res.json() : ""))
    .then((res) => (res ? render(res) : ""));
}
