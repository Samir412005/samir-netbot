import json
import urllib.request
import urllib.error

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer credential to another host.

class Http:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, url, headers=None, body=None, timeout=20):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method,
            headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with self.opener.open(req, timeout=timeout) as response:
                code, raw = response.status, response.read(1_048_577)
        except urllib.error.HTTPError as error:
            code, raw = error.code, error.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError('Response too large')
        try:
            obj = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            obj = {}
        return code, obj
