"""Application-only entrypoint; knows nothing about DNS, routers or deployment drivers."""
import argparse
import json
from pathlib import Path
import uvicorn
from .config import Settings


def create_from_config(path):
    data=json.loads(Path(path).read_text())
    attachment=data.pop('attachment',None)
    for key in ('allowed_subjects','boss_subjects'):
        data[key]=frozenset(data.get(key,[]))
    settings=Settings(**data).validate()
    if attachment:
        from .hosted import make_app
        return make_app(settings,attachment)
    from .app import create_app
    return create_app(settings)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8781)
    args=parser.parse_args()
    # Public URLs are explicitly configured; no untrusted forwarding headers needed.
    uvicorn.run(create_from_config(args.config),host=args.host,port=args.port,proxy_headers=False,ws_max_size=1024*1024)

if __name__=='__main__':main()
