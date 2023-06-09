from typing import Annotated

from aiohttp import ClientSession
from cloudscraper import CloudScraper
from fastapi import APIRouter, Depends, Path

from stremio_addons.dependencies import get_cloudflare_client, get_http_client
from stremio_addons.external.cinemeta import get_name_and_year
from stremio_addons.external.eneyida import (
    create_article_streams,
    get_article_source,
    get_article_tree,
    parse_article_tree,
)
from stremio_addons.models import StreamsResponse, StremioType

router = APIRouter(
    prefix="/eneyida",
)


@router.get("/{use_proxy}/manifest.json")
async def manifest(use_proxy: str):
    if use_proxy == "proxy":
        proxy = "[proxy] "
        addon_id = "io.ivanchenko.eneyida_proxy"
    else:
        proxy = ""
        addon_id = "io.ivanchenko.eneyida"
    return {
        "id": addon_id,
        "version": "0.0.1",
        "description": f"Play movies and series from eneyida {proxy}",
        "name": f"eneyida {proxy}",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "catalogs": [],
    }


@router.get("/{use_proxy}/stream/{stremio_type}/{stremio_id}.json")
async def stream(
    stremio_type: Annotated[StremioType, Path(title="Stremio type")],
    stremio_id: Annotated[str, Path(title="Stremio id")],
    use_proxy: str,
    http: Annotated[ClientSession, Depends(get_http_client)],
    cloudflare: Annotated[CloudScraper, Depends(get_cloudflare_client)],
) -> StreamsResponse:
    if stremio_type == StremioType.series:
        imdb_id, season, episode = stremio_id.split(":")
    else:
        imdb_id, season, episode = stremio_id, None, None

    name, year = await get_name_and_year(http, stremio_type, imdb_id)
    article_tree = await get_article_tree(cloudflare, name, year)
    if article_tree is None:
        return StreamsResponse(streams=[])

    article_data = parse_article_tree(article_tree)
    article_source = await get_article_source(http, article_data["source_url"])
    if not article_source:
        return StreamsResponse(streams=[])

    article_streams = create_article_streams(
        source=article_source,
        name=article_data["ua_name"],
        year=article_data["year"],
        stremio_type=stremio_type,
        season=season,
        episode=episode,
        use_proxy=use_proxy == "proxy",
    )
    return StreamsResponse(streams=article_streams)
