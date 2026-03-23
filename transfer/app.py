import html
import os
import secrets
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse, unquote_plus

HOST = "127.0.0.1"
PORT = 80

USERS = {
    "admin": {"password": "admin", "balance": 100.0},
    "user": {"password": "pass", "balance": 0.0},
}

# token -> username
SESSIONS: dict[str, str] = {}


def parse_form_data(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {k: v[0] for k, v in parsed.items()}


def get_cookie_value(handler: BaseHTTPRequestHandler, name: str) -> str | None:
    cookie_header = handler.headers.get("Cookie")
    if not cookie_header:
        return None
    jar = cookies.SimpleCookie()
    jar.load(cookie_header)
    morsel = jar.get(name)
    return morsel.value if morsel else None


def get_logged_in_username(handler: BaseHTTPRequestHandler) -> tuple[str | None, str | None]:
    token = get_cookie_value(handler, "auth_token")
    if not token:
        return None, None
    username = SESSIONS.get(token)
    if not username:
        return None, None
    return username, token


def money(value: float) -> str:
    return f"${value:,.2f}"


def html_page(title: str, body: str, message: str = "") -> str:
    message_html = ""
    if message:
        message_html = f'<div class="message">{html.escape(message)}</div>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --panel-2: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #3b82f6;
      --good: #22c55e;
      --warn: #f59e0b;
      --bad: #ef4444;
      --border: #374151;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: linear-gradient(180deg, #0b1220, var(--bg));
      color: var(--text);
      min-height: 100vh;
    }}
    .container {{
      max-width: 1000px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1 {{ margin-top: 0; }}
    .subtitle {{ color: var(--muted); margin-bottom: 24px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .panel {{
      background: rgba(17, 24, 39, 0.95);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.25);
    }}
    .balance {{ font-size: 1.5rem; font-weight: bold; margin: 8px 0 0; }}
    .muted {{ color: var(--muted); }}
    label {{ display: block; margin: 10px 0 6px; font-weight: bold; }}
    input, select, button {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      font-size: 14px;
    }}
    button {{
      background: var(--accent);
      border: none;
      cursor: pointer;
      font-weight: bold;
      margin-top: 14px;
    }}
    button:hover {{ filter: brightness(1.07); }}
    .message {{
      margin-bottom: 18px;
      padding: 12px 14px;
      border-radius: 10px;
      background: rgba(59,130,246,0.15);
      border: 1px solid rgba(59,130,246,0.35);
    }}
    code {{
      background: rgba(255,255,255,0.08);
      padding: 2px 6px;
      border-radius: 6px;
    }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .small {{ font-size: 0.92rem; color: var(--muted); }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Bank Website: Deposit and Transfer</h1>
    {message_html}
    {body}
  </div>
</body>
</html>
"""


class BankHandler(BaseHTTPRequestHandler):
    server_version = "LocalBank/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {fmt % args}")

    def send_html(self, content: str, status: int = 200, extra_headers: list[tuple[str, str]] | None = None) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str, extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()

    def render_home(self, message: str = "") -> None:
        current_user, token = get_logged_in_username(self)

        admin_balance = USERS["admin"]["balance"]
        user_balance = USERS["user"]["balance"]

        if current_user:
            transfer_panel = f"""
            <div class="panel">
            <h2>Transfer Money</h2>
            <form id="transferForm" method="POST" onsubmit="return configureTransferAction();">
                <label for="amount">Amount</label>
                <input id="amount" type="number" step="0.01" min="0.01" placeholder="10.00" required>

                <button type="submit">Transfer</button>
            </form>
            <script>
                function configureTransferAction() {{
                const to = "admin";
                const fromUser = {current_user!r};
                const amount = document.getElementById('amount').value;
                const form = document.getElementById('transferForm');

                form.action = '/transfer?' + new URLSearchParams({{
                    to: to,
                    from: fromUser,
                    amount: amount,
                }}).toString();

                return true;
                }}
            </script>
            </div>
            """

            deposit_panel = """
            <div class="panel">
              <h2>Deposit Money</h2>
              <form method="POST" action="/deposit">
                <label for="deposit_amount">Amount</label>
                <input id="deposit_amount" name="amount" type="number" step="0.01" min="0.01" placeholder="25.00" required>
                <button type="submit">Deposit</button>
              </form>
            </div>
            """

            login_panel = f"""
            <div class="panel">
              <h2>Session</h2>
              <p>You are logged in as <strong>{html.escape(current_user)}</strong>.</p>
              <form method="POST" action="/logout">
                <button type="submit">Log out</button>
              </form>
            </div>
            """
        else:
            transfer_panel = """
            <div class="panel">
              <h2>Transfer Money</h2>
              <p class="muted">Log in first to use the transfer panel.</p>
            </div>
            """

            deposit_panel = """
            <div class="panel">
              <h2>Deposit Money</h2>
              <p class="muted">Log in first to deposit money.</p>
            </div>
            """

            login_panel = """
            <div class="panel">
              <h2>Login</h2>
              <form method="POST" action="/login">
                <label for="username">Username</label>
                <input id="username" name="username" type="text" placeholder="user" required>

                <label for="password">Password</label>
                <input id="password" name="password" type="password" placeholder="pass" required>

                <button type="submit">Log in</button>
              </form>
            </div>
            """

        balances_panel = f"""
        <div class="panel">
          <h2>Balances</h2>
          <div>
            <div><strong>admin</strong></div>
            <div class="balance">{money(admin_balance)}</div>
          </div>
          <hr style="border-color:#374151; margin: 16px 0;">
          <div>
            <div><strong>user</strong></div>
            <div class="balance">{money(user_balance)}</div>
          </div>
        </div>
        """

        body = f"""
        <div class="grid">
          {balances_panel}
          {login_panel}
          {deposit_panel}
          {transfer_panel}
        </div>
        """

        self.send_html(html_page("Bank Website", body, message=message))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            params = self.parse_query(parsed.query)
            message = params.get("message", "")
            self.render_home(message=message)
            return

        self.send_html(html_page("Not Found", "<div class='panel'><h2>404</h2><p>Page not found.</p></div>"), status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/login":
            form = parse_form_data(self)
            username = form.get("username", "")
            password = form.get("password", "")

            user = USERS.get(username)
            if not user or username == "admin" or user["password"] != password:
                self.render_home(message="Invalid username or password.")
                return

            token = secrets.token_urlsafe(24)
            SESSIONS[token] = username
            cookie = cookies.SimpleCookie()
            cookie["auth_token"] = token
            cookie["auth_token"]["path"] = "/"
            cookie["auth_token"]["httponly"] = True
            headers = [("Set-Cookie", cookie.output(header="").strip())]
            self.redirect("/?message=" + urlencode({"": f"Logged in as {username}."})[1:], extra_headers=headers)
            return

        if parsed.path == "/logout":
            token = get_cookie_value(self, "auth_token")
            if token:
                SESSIONS.pop(token, None)
            cookie = cookies.SimpleCookie()
            cookie["auth_token"] = ""
            cookie["auth_token"]["path"] = "/"
            cookie["auth_token"]["max-age"] = 0
            headers = [("Set-Cookie", cookie.output(header="").strip())]
            self.redirect("/?message=" + urlencode({"": "Logged out."})[1:], extra_headers=headers)
            return

        if parsed.path == "/deposit":
            current_user, _ = get_logged_in_username(self)
            if not current_user:
                self.render_home(message="You must be logged in to deposit.")
                return

            form = parse_form_data(self)
            try:
                amount = float(form.get("amount", "0"))
            except ValueError:
                self.render_home(message="Invalid deposit amount.")
                return

            if amount <= 0:
                self.render_home(message="Deposit amount must be positive.")
                return

            USERS[current_user]["balance"] += amount
            self.redirect("/?message=" + urlencode({"": f"Deposited {money(amount)} into {current_user}."})[1:])
            return

        if parsed.path == "/transfer":
            valid, amount = self.validate_transfer(parsed)
            if not valid:
                return

            from_user = self.get_param("from", parsed.query)
            to_user = self.get_param("to", parsed.query)

            USERS[from_user]["balance"] -= amount
            USERS[to_user]["balance"] += amount

            if USERS["admin"]["balance"] == 0:
                self.render_home(message="You got the flag!")
                return

            self.redirect("/?message=" + urlencode({"": f"Transferred {money(amount)} from {from_user} to {to_user}."})[1:])
            return

        self.send_html(html_page("Not Found", "<div class='panel'><h2>404</h2><p>Page not found.</p></div>"), status=404)

    def parse_query(self, parsed_query: str) -> dict[str, str]:
        params = {}
        if parsed_query:
            for pair in parsed_query.split("&"):
                if not pair:
                    continue

                if "=" in pair:
                    key, value = pair.split("=", 1)
                else:
                    key, value = pair, ""

                key = unquote_plus(key)
                value = unquote_plus(value)
                params[key] = value

        return params

    def get_param(self, get_key: str, parsed_query: str) -> str | None:
        if parsed_query:
            for pair in parsed_query.split("&"):
                if not pair:
                    continue

                if "=" in pair:
                    key, value = pair.split("=", 1)
                else:
                    key, value = pair, ""

                if unquote_plus(key) == get_key:
                    return unquote_plus(value)

        return None

    def validate_transfer(self, parsed) -> bool:
        params = self.parse_query(parsed.query)
        to_user = params.get("to", "")
        from_user = params.get("from", "")
        amount_str = params.get("amount", "0")
        token = get_cookie_value(self, "auth_token")

        try:
            amount = float(amount_str)
        except ValueError:
            self.render_home(message="Invalid deposit amount.")
            return False, 0
        
        if amount <= 0:
            self.render_home(message="Transfer amount must be positive.")
            return False, 0

        if from_user not in USERS or to_user not in USERS:
            self.render_home(message="Unknown source or destination user.")
            return False, 0

        session_user = SESSIONS.get(token)
        if session_user != from_user:
            self.render_home(message="Invalid token for source user.")
            return False, 0

        if USERS[from_user]["balance"] < amount:
            self.render_home(message="Insufficient funds for transfer.")
            return False, 0
        
        return True, amount

def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), BankHandler)
    print(f"Local bank simulation running at http://{HOST}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()