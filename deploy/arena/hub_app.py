"""Private, pinned GameServer metaverse router with no public REST surface."""
from fastapi import FastAPI
from gameserver.ws.router import ws_router
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(ws_router)
@app.get('/health')
async def health():
    return {'status': 'ok'}
