"""Temporary read-only MCP connectivity probe. No Arena, HUB or database access."""
import argparse
import json
import logging
from urllib.parse import urlsplit
from uuid import uuid4
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
import uvicorn


def create_probe(public_url):
    server = MCPServer('StarBench connectivity probe', instructions='Connectivity test only. No game controls.')
    logger = logging.getLogger('starbench.probe')
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
    async def connectivity_probe() -> dict:
        """Confirm that this client can call the self-hosted HTTPS MCP endpoint."""
        request_id = uuid4().hex
        logger.info(json.dumps({'event': 'connectivity_probe', 'receipt': request_id}))
        return {'service': 'starbench-connectivity-probe', 'receipt': request_id, 'game_connected': False}

    return server.streamable_http_app(stateless_http=True, json_response=True, host=urlsplit(public_url).hostname)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--port', type=int, default=8781)
    args = parser.parse_args()
    uvicorn.run(create_probe(args.public_url), host='127.0.0.1', port=args.port, proxy_headers=False)


if __name__ == '__main__':
    main()
