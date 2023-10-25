from copy import copy, deepcopy
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Callable, Self, Any
from os.path import exists
import log
from mimetypes import guess_type

from utils import read_file


__all__ = ["App"]

DIRNAME = __file__.replace("\\", "/").rsplit("/", 1)[0]
log.set_level(log.LEVELS.NONE)


class _Request:
    __slots__ = ["path"]


class _Response:
    __slots__ = ["end", "send", "status", "headers", "add"]


class Request(_Request):
    ...


class Response(_Response):
    def send(self, data: str | dict) -> Self:
        ...


class _Server(BaseHTTPRequestHandler):
    def do_GET(self):
        ...

    def do_POST(self):
        ...


class App:
    def __init__(self) -> None:
        self.routes = {}
        self._static_dict = {}

    def listen(self, ip: str, port: int, callback: Callable | None = None) -> None:
        _routes_arg = self.routes
        _static_arg = self._static_dict
        _find_static_arg = self.find_static

        def do_GET(self):
            nonlocal _routes_arg, _static_arg, _find_static_arg

            log.info("GET", self.path)

            if self.path.rstrip("/") in _routes_arg:
                _req = _Request()
                _res = _Response()

                _req.path = self.path

                response = {
                    "data": "",
                    "headers": {
                        "Content-type": "text/html",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "status": 200,
                }

                def _send(data: dict | str) -> _Response:
                    if isinstance(data, dict):
                        content_type = "application/json"
                        data = json.dumps(data)
                    else:
                        content_type = "text/html"
                    response["headers"]["Content-type"] = content_type
                    response["data"] = data
                    return _res

                def _add(data: dict | str) -> _Response:
                    content_type = response["headers"]["Content-type"]
                    if isinstance(data, dict):
                        if response["data"]:
                            if content_type == "application/json":
                                data_merge = json.loads(response["data"])
                                data |= data_merge
                            else:
                                log.warn("Incompatible type: str + dict")
                                return _res

                        data = json.dumps(data)
                    response["data"] += data
                    return _res

                def _status(value: int) -> _Response:
                    response["status"] = value
                    return _res

                def _set_headers(header: dict[str, str]) -> _Response:
                    # if len(header) == 1:
                    #     response["headers"][list(header.keys())[0]] = list(
                    #         header.values()
                    #     )[0]
                    response["headers"] |= header
                    return _res

                _res.send = _send
                _res.end = _res.send
                _res.status = _status
                _res.headers = _set_headers
                _res.add = _add

                _routes_arg[self.path.rstrip("/")](_req, _res)

                self.send_response(response["status"])

                for key, value in response["headers"].items():
                    self.send_header(key, value)

                self.end_headers()

                self.wfile.write(bytes(response["data"], "utf-8"))

            elif any((self.path.startswith(x) for x in _static_arg.keys())):
                abspath = _find_static_arg(_static_arg, self.path)

                log.info(abspath)
                log.kawaii(str(_static_arg))

                if abspath.endswith("/"):
                    abspath += "index.html"

                if not exists(abspath):
                    self.send_response(404)
                    self.end_headers()
                    return

                content = read_file(abspath)

                self.send_response(200)

                ct = guess_type(abspath)
                self.send_header("Content-type", ct)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                self.wfile.write(bytes(content, "utf-8"))

            else:
                self.send_response(404)

                self.send_header("Content-type", "text/html")
                self.end_headers()

                self.wfile.write(bytes("<h1>File not found</h1>", "utf-8"))

        _Server.do_GET = do_GET
        _Server.do_POST = do_GET

        webServer = HTTPServer((ip, port), _Server)
        if callback is not None:
            callback()
        webServer.serve_forever()

    def get(self, path: str) -> Callable:
        def decorator(func: Callable[[Request, Response], Any]):
            self.routes[path.rstrip("/")] = deepcopy(func)
            return func

        return decorator

    def static(self, path: str, localdir: str) -> None:
        self._static_dict[path] = localdir

    def find_static(self, static: dict, path: str) -> str:
        """returns final path"""
        f = filter(lambda a: path.startswith(a), static.keys())
        s = sorted(f, key=lambda a: len(a.split("/")))
        return path.replace(s[-1], static[s[-1]])


if __name__ == "__main__":
    log.set_level(log.LEVELS.DEBUG)

    app = App()

    # @app.get("/")
    # def _(req, res):
    #     res.send('Hello, world!<br><a href="/api">-></a>')
    #     res.add("<style>*{font-family:'Fira Code';}</style>")

    @app.get("/api")
    def _(req, res: Response):
        res.send('API<br><a href="/"><-</a>')
        res.add("<style>*{font-family:'Fira Code';}</style>")
        res.add(f"{req.path}")

    # app.static("/", f"{DIRNAME}/public/")

    try:
        app.listen("0.0.0.0", 8888)
    except KeyboardInterrupt:
        ...
