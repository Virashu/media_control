# Media Session HTTP API

## Features

### 1. Get playback information
   
  GET `http://127.0.0.1:8888/data`


### 2. Control playback

GET/POST `http://127.0.0.1:8888/control/<command>`

Command is one of:
  - `play`
  - `pause` (toggle)
  - `next`
  - `prev`
  - `stop`
  - `repeat` (toggle none/track/all)
  - `shuffle` (toggle on/off)
  - `seek` + `&position=<position in %>`

