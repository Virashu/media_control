# class MyServer(BaseHTTPRequestHandler):
#     def do_GET(self):
#         self.send_response(200)
#         self.send_header("Content-type", "application/json")
#         self.end_headers()
#         with open("contents.json", "r") as f:
#             response = f.read()
#         self.wfile.write(bytes(response, "utf-8"))


# webServer = HTTPServer(("0.0.0.0", 8000), MyServer)

# try:
#     webServer.serve_forever()
# except KeyboardInterrupt:
#     pass
