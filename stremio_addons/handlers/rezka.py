from typing import Annotated

from aiohttp import ClientSession
from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse
from yarl import URL

from stremio_addons.dependencies import get_http_client
from stremio_addons.external.cinemeta import get_name_and_year
from stremio_addons.external.rezka import (
    get_article_streams,
    get_article_translators,
    get_article_tree,
)
from stremio_addons.models import StreamsResponse, StremioType

router = APIRouter(
    prefix="/rezka",
)


@router.get("/{language}/manifest.json")
async def manifest(
    language: Annotated[str, Path(title="language")],
):
    return {
        "id": f"io.ivanchenko.rezka_{language}",
        "version": "0.0.1",
        "description": f"Play movies and series from hdrezka [{language}]",
        "name": f"hdrezka [{language}]",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "catalogs": [],
    }


@router.get("/{language}/stream/{stremio_type}/{stremio_id}.json")
async def stream(
    language: Annotated[str, Path(title="language")],
    stremio_type: Annotated[StremioType, Path(title="Stremio type")],
    stremio_id: Annotated[str, Path(title="Stremio id")],
    http: Annotated[ClientSession, Depends(get_http_client)],
) -> StreamsResponse:
    if stremio_type == StremioType.series:
        imdb_id, season, episode = stremio_id.split(":")
    else:
        imdb_id, season, episode = stremio_id, None, None

    name, year = await get_name_and_year(http, stremio_type, imdb_id)

    article_id, article_tree = await get_article_tree(
        http, imdb_id, name, year, stremio_type
    )
    if article_tree is None:
        return StreamsResponse(streams=[])

    translators = get_article_translators(article_tree, language)
    streams = await get_article_streams(
        http,
        article_id,
        translators,
        stremio_type,
        season,
        episode,
    )

    return StreamsResponse(streams=streams)


async def iterator(client_response):
    async for chunk in client_response.content.iter_any():
        yield chunk
    client_response.close()


@router.get("/proxy/{host}/{real_path:path}")
async def path(
    http: Annotated[ClientSession, Depends(get_http_client)],
    host: str,
    real_path: str,
):
    url = URL.build(scheme="https", host=host, path="/" + real_path)
    client_response = await http.get(url)
    return StreamingResponse(iterator(client_response))
