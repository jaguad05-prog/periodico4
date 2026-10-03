#!/usr/bin/env python3
# Servidor del periódico de aula · v5
# El nombre del grupo viaja siempre codificado (encodeURIComponent), igual que en las claves guardadas
# v5: cada noticia se guarda por separado y solo puede escribirla una persona a la vez
import json, os, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos.json")
BASE  = os.path.dirname(os.path.abspath(__file__))
store = {}
lock = threading.Lock()

# Bloqueos de noticias: (grupo, id) -> {"sesion": str, "hasta": segundos}
bloqueos = {}
DURACION = 40   # si el editor deja de avisar 40 segundos, la noticia queda libre

def guardar():
    tmp = DATOS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)
    os.replace(tmp, DATOS)

def cargar():
    global store
    if os.path.exists(DATOS):
        try:
            with open(DATOS, encoding="utf-8") as f:
                store = json.load(f)
        except:
            pass

def clave(grupo, id):
    return (str(grupo), str(id))

def dueno(grupo, id):
    b = bloqueos.get(clave(grupo, id))
    if b and b["hasta"] > time.time():
        return b["sesion"]
    return None

def buscar(arts, id):
    for i, a in enumerate(arts):
        if str(a.get("id")) == str(id):
            return i
    return -1

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,PUT,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def responder(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def leer_cuerpo(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"null")

    def do_OPTIONS(self):
        self.send_response(200)
        self.cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].strip("/")

        if path == "" or path.endswith(".html"):
            filename = path if path else "periodico.html"
            filepath = os.path.join(BASE, filename)
            if os.path.exists(filepath):
                data = open(filepath, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.cors()
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
            return

        if path.startswith("__bloqueos/"):
            grupo = path[len("__bloqueos/"):]
            ahora = time.time()
            with lock:
                lista = [{"id": k[1], "sesion": v["sesion"]}
                         for k, v in bloqueos.items() if k[0] == grupo and v["hasta"] > ahora]
            self.responder(lista)
            return

        with lock:
            val = store.get(path)
        self.responder(val)

    def do_PUT(self):
        path = self.path.split("?")[0].strip("/")
        try:
            data = self.leer_cuerpo()
            with lock:
                store[path] = data
                guardar()
            self.responder({"ok": True})
        except Exception:
            self.send_response(500)
            self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0].strip("/")
        try:
            d = self.leer_cuerpo() or {}
        except Exception:
            self.responder({"ok": False, "motivo": "datos"}, 400)
            return
        grupo = str(d.get("grupo", ""))
        sesion = str(d.get("sesion", ""))

        # Coger, renovar o soltar una noticia
        if path == "__bloqueo":
            id = d.get("id")
            with lock:
                otro = dueno(grupo, id)
                if d.get("accion") == "soltar":
                    if otro == sesion:
                        bloqueos.pop(clave(grupo, id), None)
                    self.responder({"ok": True})
                    return
                if otro and otro != sesion:
                    self.responder({"ok": False, "motivo": "ocupada"})
                    return
                bloqueos[clave(grupo, id)] = {"sesion": sesion, "hasta": time.time() + DURACION}
                arts = (store.get(grupo) or {}).get("articles") or []
                i = buscar(arts, id)
                self.responder({"ok": True, "articulo": arts[i] if i >= 0 else None})
            return

        # Guardar una sola noticia sin tocar las de los compañeros
        if path == "__articulo":
            art = d.get("articulo") or {}
            id = art.get("id")
            with lock:
                otro = dueno(grupo, id)
                if otro and otro != sesion:
                    self.responder({"ok": False, "motivo": "ocupada"})
                    return
                doc = store.get(grupo) or {"articles": []}
                arts = doc.get("articles") or []
                i = buscar(arts, id)
                if i >= 0:
                    arts[i] = art
                else:
                    arts.append(art)
                doc["articles"] = arts
                store[grupo] = doc
                guardar()
                if otro == sesion:
                    bloqueos[clave(grupo, id)] = {"sesion": sesion, "hasta": time.time() + DURACION}
            self.responder({"ok": True})
            return

        # Orden de la portada, piezas nuevas, borradas y nombre del periódico
        if path == "__estructura":
            with lock:
                doc = store.get(grupo) or {"articles": []}
                arts = doc.get("articles") or []
                borrar = [str(x) for x in (d.get("borrar") or [])]
                for b in borrar:
                    otro = dueno(grupo, b)
                    if otro and otro != sesion:
                        self.responder({"ok": False, "motivo": "ocupada"})
                        return
                porId = {str(a.get("id")): a for a in arts}
                for n in d.get("nuevas") or []:
                    if str(n.get("id")) not in porId:
                        porId[str(n.get("id"))] = n
                orden = [str(x) for x in (d.get("orden") or [])]
                nueva = []
                for x in orden:
                    if x in porId and x not in borrar:
                        nueva.append(porId.pop(x))
                for a in arts:
                    k = str(a.get("id"))
                    if k in porId and k not in borrar:
                        nueva.append(porId.pop(k))
                for k, a in list(porId.items()):
                    if k not in borrar:
                        nueva.append(a)
                doc["articles"] = nueva
                if d.get("paperName"):
                    doc["paperName"] = d["paperName"]
                store[grupo] = doc
                guardar()
                self.responder({"ok": True, "doc": doc})
            return

        self.responder({"ok": False, "motivo": "ruta"}, 404)

if __name__ == "__main__":
    cargar()
    port = int(os.environ.get('PORT', 8000))
    print(f'Servidor Periodico v5 activo en puerto {port}')
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
