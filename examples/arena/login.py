"""GitHub → Keycloak authorization-code + PKCE login for a native Harness.

uv run --extra arena python examples/arena/login.py https://auth.example.org
The local token file is private and never printed. No client secret is needed.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode, urlsplit, parse_qs
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('auth_origin')
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('token.json'))
    args = parser.parse_args()
    if not args.auth_origin.startswith('https://'):
        parser.error('Use the HTTPS auth origin')
    issuer = args.auth_origin.rstrip('/') + '/realms/starbench'
    discovery = json.load(urllib.request.urlopen(issuer + '/.well-known/openid-configuration', timeout=10))
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(32)
    reply = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            params = parse_qs(urlsplit(self.path).query)
            if urlsplit(self.path).path != '/callback' or not secrets.compare_digest(params.get('state',[''])[0], state):
                self.send_error(400); return
            reply.update({key: values[0] for key, values in params.items()})
            self.send_response(200); self.end_headers(); self.wfile.write(b'Login received. Return to your terminal.')
    redirect = 'http://127.0.0.1:8769/callback'
    url = discovery['authorization_endpoint'] + '?' + urlencode({'client_id':'starbench-harness',
        'response_type':'code','scope':'openid arena:play','redirect_uri':redirect,
        'code_challenge':challenge,'code_challenge_method':'S256','state':state})
    with HTTPServer(('127.0.0.1',8769), Callback) as server:
        server.timeout=1
        webbrowser.open(url)
        print('Complete GitHub login in the browser (five-minute window).')
        deadline=time.monotonic()+300
        while not reply and time.monotonic()<deadline:
            server.handle_request()
    if 'code' not in reply:
        raise SystemExit('Authorization was not completed')
    request=urllib.request.Request(discovery['token_endpoint'], data=urlencode({'grant_type':'authorization_code',
        'client_id':'starbench-harness','redirect_uri':redirect,'code':reply['code'],'code_verifier':verifier}).encode())
    with urllib.request.urlopen(request,timeout=10) as response:
        tokens=json.load(response)
    tokens.update(issuer=issuer, token_endpoint=discovery['token_endpoint'], expires_at=time.time()+tokens['expires_in'])
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as output: json.dump(tokens,output)
    os.chmod(args.output,0o600)
    print('Saved credentials to',args.output)
if __name__=='__main__': main()
