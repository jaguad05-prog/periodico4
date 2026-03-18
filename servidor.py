#!/usr/bin/env python3
import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos.json")
BASE  = os.path.dirname(os.path.abspath(__file__))
store = {}

def guardar():
    with open(DATOS, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)

def cargar():
    global store
    if os.path.exists(DATOS):
        try:
            with open(DATOS, encoding="utf-8") as f:
                store = json.load(f)
        except:
            pass

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,PUT,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.strip("/")

        if path == "" or path.endswith(".html"):
            filename = path if path else "periodico.html"
            filepath = os.path.join(BASE, filename)
            if os.path.exists(filepath):
                data = open(filepath, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.cors()
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
            return

        val = store.get(path)
        body = json.dumps(val, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        path = self.path.strip("/")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            store[path] = json.loads(body)
            guardar()
            self.send_response(200)
            self.cors()
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            self.send_response(500)
            self.end_headers()

if __name__ == "__main__":
    cargar()
    port = int(os.environ.get('PORT', 8000))
    print(f'Servidor Periodico activo en puerto {port}')
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
