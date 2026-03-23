from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
import html

PRODUCTS = {
    "1": {"name": "Firewall", "price": "$100 per month", "desc": "A barrier for your network."},
    "2": {"name": "Multi-Factor Authentication", "price": "$5 per user per month", "desc": "Keep the hackers out."},
    "3": {"name": "Data Encryption", "price": "$8 per month", "desc": "No more leaked secrets."},
    "4": {"name": "Incident Response", "price": "$20 per user per month", "desc": "Get your company back on its feet."},
    "5": {"name": "Cybersecurity Training", "price": "$15 per user per month", "desc": "Don't get fooled by phishing."},
}

BASE_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f6f7fb; color: #222; }}
    header {{ background: #1f2937; color: white; padding: 14px 22px; }}
    header a {{ color: white; text-decoration: none; margin-right: 18px; font-weight: bold; }}
    .container {{ max-width: 1000px; margin: 24px auto; padding: 0 16px; }}
    .card {{ background: white; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 18px; margin-bottom: 16px; }}
    .product-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
    .button {{ display: inline-block; background: #2563eb; color: white; text-decoration: none; border: none; border-radius: 8px; padding: 10px 14px; cursor: pointer; }}
    .muted {{ color: #555; }}
    input[type=text] {{ width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; box-sizing: border-box; margin-bottom: 10px; }}
    .success {{ color: #166534; font-weight: bold; }}
    .error {{ color: #991b1b; font-weight: bold; }}
  </style>
</head>
<body>
<header>
  <a href="/">Home</a>
  <a href="/chat">Chat</a>
</header>

<div class="container">
  {main}
</div>
</body>
</html>
"""

def is_same_origin(url: str):
    parsed = urlparse(url)
    port = parsed.port if parsed.port is not None else 80
    return (
        parsed.scheme == "http" and
        parsed.hostname == "127.0.0.1" and
        port == 80
    )

class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def follow_link(url: str):
    opener = build_opener(NoRedirectHandler)
    current = url

    for _ in range(5):
        req = Request(current, method="GET")
        try:
            with opener.open(req, timeout=3) as resp:
                return resp.geturl()
        except HTTPError as e:
            if 300 <= e.code < 400:
                location = e.headers.get("Location")
                if not location:
                    return current
                current = urljoin(current, location)
                continue
            return current
        except URLError:
            return current

    return current

def render_page(title, main_html):
    return BASE_TEMPLATE.format(
        title=html.escape(title),
        main=main_html,
    )

class AppHandler(BaseHTTPRequestHandler):
    def send_html(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_redirect(self, location: str, status: int = 302):
        self.send_response(status)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self.handle_home()
            return

        if path == "/chat":
            self.handle_chat(query)
            return

        if path.startswith("/product/"):
            product_id = path[len("/product/"):]
            self.handle_product(product_id)
            return

        if path == "/redirect":
            self.handle_redirect(query)
            return

        self.send_text("Not found", 404)

    def handle_home(self):
        cards = []
        for pid, p in PRODUCTS.items():
            cards.append(f"""
            <div class="card">
              <h3>{escape(p['name'])}</h3>
              <p><strong>Product ID:</strong> {escape(pid)}</p>
              <a class="button" href="/redirect?path=/product/{pid}">View Product</a>
            </div>
            """)

        main = f"""
        <div class="card">
          <h1>Business Solutions</h1>
          <p class="muted">Browse our security products, or visit Chat to submit a link.</p>
        </div>
        <div class="product-grid">{''.join(cards)}</div>
        """
        self.send_html(render_page("Home", main))

    def handle_product(self, product_id: str):
        p = PRODUCTS.get(product_id)
        if not p:
            self.send_text("Product not found", 404)
            return

        main = f"""
        <div class="card">
          <h1>{escape(p['name'])}</h1>
          <p>{escape(p['desc'])}</p>
          <p><strong>Price:</strong> {escape(p['price'])}</p>
          <p><strong>Product ID:</strong> {escape(product_id)}</p>
        </div>
        """
        self.send_html(render_page(p["name"], main))

    def handle_chat(self, query):
        submitted_link = (query.get("link", [""])[0] or "").strip()
        result_html = ""

        if submitted_link:
            if not is_same_origin(submitted_link):
                result_html = """
                <div class="card">
                  <p class="error">This link is not same-origin, so I cannot open it.</p>
                </div>
                """
            else:
                result_url = follow_link(submitted_link)
                print(result_url)
                if is_same_origin(result_url):
                    result_html = """
                    <div class="card">
                      <p class="success">Looks great!</p>
                    </div>
                    """
                else:
                    result_html = """
                    <div class="card">
                      <p class="success">You got the flag!</p>
                    </div>
                    """

        main = f"""
        <div class="card">
          <h1>Chat</h1>
          <form method="GET" action="/chat">
            <input type="text" name="link" placeholder="Enter a link" value="{escape(submitted_link)}">
            <button class="button" type="submit">Submit</button>
          </form>
        </div>
        {result_html}
        """
        self.send_html(render_page("Chat", main))

    def handle_redirect(self, query):
        product_page = (query.get("path", [""])[0] or "").strip()
        new_url = f"http://127.0.0.1{product_page}"
        self.send_redirect(new_url)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 80), AppHandler)
    print("Serving on http://127.0.0.1:80")
    server.serve_forever()