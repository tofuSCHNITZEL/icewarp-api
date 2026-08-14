"""Mock IceWarp API server for manual end-to-end testing of this library.

Not part of the published package. Run it and point the CLI/library at it::

    python scripts/mock_server.py 32000
    icewarp-api --url http://127.0.0.1:32000/icewarpapi --email a@b.com --password x login
"""
import http.server
import socketserver
import sys

RESPONSES = {
    "authenticate": b"""<?xml version="1.0" encoding="UTF-8"?>
<iq sid="abc123sid" type="result">
  <query xmlns="admin:iq:rpc">
    <result>1</result>
  </query>
</iq>""",
    "getdomainsinfolist": b"""<?xml version="1.0" encoding="UTF-8"?>
<iq sid="abc123sid" type="result">
  <query xmlns="admin:iq:rpc">
    <result>
      <item>
        <name>example.com</name>
        <desc>Example domain</desc>
        <domaintype>0</domaintype>
        <accountcount>5</accountcount>
      </item>
      <item>
        <name>example.org</name>
        <desc>Another domain</desc>
        <domaintype>0</domaintype>
        <accountcount>2</accountcount>
      </item>
    </result>
  </query>
</iq>""",
    "getsessioninfo": b"""<?xml version="1.0" encoding="UTF-8"?>
<iq sid="abc123sid" type="result">
  <query xmlns="admin:iq:rpc">
    <result>
      <email>admin@example.com</email>
    </result>
  </query>
</iq>""",
    "getaccountsinfolist": b"""<?xml version="1.0" encoding="UTF-8"?>
<iq sid="abc123sid" type="result">
  <query xmlns="admin:iq:rpc">
    <result>
      <item>
        <email>user1@example.com</email>
        <fullname>User One</fullname>
      </item>
      <item>
        <email>user2@example.com</email>
        <fullname>User Two</fullname>
      </item>
    </result>
  </query>
</iq>""",
    "logout": b"""<?xml version="1.0" encoding="UTF-8"?>
<iq sid="abc123sid" type="result">
  <query xmlns="admin:iq:rpc">
    <result>1</result>
  </query>
</iq>""",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        command = self.path.rsplit("/", 1)[-1].lower()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        print(f"--- {command} ---\n{body.decode('utf-8')}\n", file=sys.stderr)
        response = RESPONSES.get(command)
        if response is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 32000
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"Mock IceWarp API listening on http://127.0.0.1:{port}")
        httpd.serve_forever()
