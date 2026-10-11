import argparse
import uvicorn
from .app import create_app

def main():
    parser = argparse.ArgumentParser(description='StarBench Arena gateway (one application worker)')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8780)
    args = parser.parse_args()
    app = create_app()
    if app.state.arena.settings.development and args.host not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Development authentication may only bind to loopback')
    uvicorn.run(app, host=args.host, port=args.port, ws_max_size=1024 * 1024)

if __name__ == '__main__':
    main()
