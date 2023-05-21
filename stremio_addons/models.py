from enum import Enum

from pydantic import BaseModel


class StremioType(str, Enum):
    series = "series"
    movie = "movie"


class Stream(BaseModel):
    title: str
    url: str


class StreamsResponse(BaseModel):
    streams: list[Stream]
