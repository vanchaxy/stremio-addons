from unidecode import unidecode


async def get_name_and_year(client, stremio_type, imdb_id):
    async with client.get(
        f"https://v3-cinemeta.strem.io/meta/{stremio_type}/{imdb_id}.json",
    ) as response:
        json = await response.json()
        name = unidecode(json["meta"]["name"]).lower()
        year = json["meta"]["year"].split("–")[0]
        return name, year
