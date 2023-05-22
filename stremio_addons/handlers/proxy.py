from typing import Annotated

from aiohttp import ClientSession
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from yarl import URL

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
    return StreamingResponse(iterator(client_response))
