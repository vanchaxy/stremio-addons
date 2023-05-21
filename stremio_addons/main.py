from contextlib import asynccontextmanager

import aiohttp
from cloudscraper import create_scraper, user_agent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stremio_addons.handlers import eneyida_router, rezka_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    headers = user_agent.User_Agent().headers

    http_client = aiohttp.ClientSession(headers=headers)
    cloudflare_client = create_scraper()

    yield {
        "http_client": http_client,
        "cloudflare_client": cloudflare_client,
    }

    await http_client.close()
    cloudflare_client.close()


app = FastAPI(
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rezka_router)
app.include_router(eneyida_router)
