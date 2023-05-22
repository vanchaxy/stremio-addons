from pydantic import BaseSettings


class Settings(BaseSettings):
    ENEYIDA_PROXY: str = None
    REZKA_HOST: str = "rezkify.com"
    PROXY_HOST: str = "stremio.ivanchenko.io"


settings = Settings()
