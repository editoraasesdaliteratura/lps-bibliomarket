import sys, asyncio, http.server, threading, functools
from playwright.async_api import async_playwright
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=".")
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(Q, directory=".")); threading.Thread(target=srv.serve_forever, daemon=True).start()
jobs = [a.split("|") for a in sys.argv[1:]]  # nome|query
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for nome, q in jobs:
            w = int(dict(x.split("=") for x in q.split("&")).get("w", 1400)); hh = int(dict(x.split("=") for x in q.split("&")).get("h", 1400))
            pg = await b.new_page(viewport={"width": w, "height": hh}, device_scale_factor=1)
            await pg.goto(f"http://127.0.0.1:8766/livro3d.html?{q}", wait_until="networkidle")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"out/{nome}.png", omit_background=("recorte" in q))
            print("ok", nome)
        await b.close()
asyncio.run(main())
