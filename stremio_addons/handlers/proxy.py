from typing import Annotated

from aiohttp import ClientSession
from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from yarl import URL

from stremio_addons.config import settings
from stremio_addons.dependencies import get_http_client

router = APIRouter(
    prefix="/proxy",
)


async def iterator(client_response):
    async for chunk in client_response.content.iter_any():
        yield chunk
    client_response.close()


@router.get("/{host}/{real_path:path}")
async def path(
    http: Annotated[ClientSession, Depends(get_http_client)],
    host: str,
    real_path: str,
):
    url = URL.build(scheme="https", host=host, path="/" + real_path)
    client_response = await http.get(url)

    if real_path.endswith("hls/index.m3u8"):
        context = await client_response.text()
        proxy_prefix = URL.build(
            scheme="https", host=settings.PROXY_HOST, path="/proxy/"
        )
        return Response(context.replace("https://", str(proxy_prefix)))

    return StreamingResponse(iterator(client_response))
