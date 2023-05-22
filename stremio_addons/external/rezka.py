import re
import time
import urllib.parse
from binascii import a2b_base64
from json import loads

import backoff
import lxml.html
from unidecode import unidecode
from yarl import URL

from stremio_addons.config import settings

FLAGS_MAPPING = {
    "ua": "🇺🇦",
    "ru": "🇷🇺",
    "kz": "🇰🇿",
    "*": "🏳️‍🌈",
}

_sub_trash = re.compile(
    "#h|//_//|I0A=|I0Ah|I0Aj|I0Ak|I0BA|I0Be|I14=|I14h|I14j|I14k|I15A|I15e|ISE=|ISEh|ISEj|ISEk|ISFA|ISFe|ISM=|ISMh"
    "|ISMj|ISMk|ISNA|ISNe|ISQ=|ISQh|ISQj|ISQk|ISRA|ISRe|IUA=|IUAh|IUAj|IUAk|IUBA|IUBe|IV4=|IV4h|IV4j|IV4k|IV5A|IV5e"
    "|IyE=|IyEh|IyEj|IyEk|IyFA|IyFe|IyM=|IyMh|IyMj|IyMk|IyNA|IyNe|IyQ=|IyQh|IyQj|IyQk|IyRA|IyRe|JCE=|JCEh|JCEj|JCEk"
    "|JCFA|JCFe|JCM=|JCMh|JCMj|JCMk|JCNA|JCNe|JCQ=|JCQh|JCQj|JCQk|JCRA|JCRe|JEA=|JEAh|JEAj|JEAk|JEBA|JEBe|JF4=|JF4h"
    "|JF4j|JF4k|JF5A|JF5e|QCE=|QCEh|QCEj|QCEk|QCFA|QCFe|QCM=|QCMh|QCMj|QCMk|QCNA|QCNe|QCQ=|QCQh|QCQj|QCQk|QCRA|QCRe"
    "|QEA=|QEAh|QEAj|QEAk|QEBA|QEBe|QF4=|QF4h|QF4j|QF4k|QF5A|QF5e|XiE=|XiEh|XiEj|XiEk|XiFA|XiFe|XiM=|XiMh|XiMj|XiMk"
    "|XiNA|XiNe|XiQ=|XiQh|XiQj|XiQk|XiRA|XiRe|XkA=|XkAh|XkAj|XkAk|XkBA|XkBe|Xl4=|Xl4h|Xl4j|Xl4k|Xl5A|Xl5e"
).sub


def clear_trash(trash_string: str) -> str:
    return a2b_base64(b"%b==" % _sub_trash("", trash_string).encode("ASCII")).decode(
        "ASCII"
    )


async def get_article_tree(http, imdb_id, name, year, stremio_type):
    search_url = f"https://{settings.REZKA_HOST}/engine/ajax/search.php"
    async with http.post(search_url, data={"q": name}) as response:
        content = await response.text()

    search_tree = lxml.html.fromstring(content)
    articles = search_tree.xpath("//li")
    for index, article in enumerate(articles):
        article_url_tag = article.xpath(".//a")[0]
        article_title = article_url_tag.text_content()
        article_url = article_url_tag.attrib["href"]
        article_type, article_id, article_year = re.match(
            r"https:\/\/\w+\.\w+\/(\w+)\/\w+\/(\d+).*-(\d{4})\.html",
            article_url,
        ).groups()
        if article_type == "films" and stremio_type != "movie":
            continue

        if year != article_year:
            continue

        article_name = None
        if article_type != "films":
            article_name = re.match(
                r".* \((.+), (сериал|мультфильм|аниме), \d{4}.*\).*",
                article_title,
            ).groups()

        if not article_name:
            article_name = re.match(
                r".+ \((.+), \d{4}\).+",
                article_title,
            ).groups()[0]
        else:
            article_name = article_name[0]

        article_name = unidecode(article_name.lower())
        if name not in article_name:
            continue

        async with http.get(article_url) as response:
            article_page = await response.text()
            article_tree = lxml.html.fromstring(article_page)

        imdb_url_tag = article_tree.xpath(
            '//div[@class="b-post__infotable_right"]//span[contains(@class, "imdb")]/a'
        )
        base64_imdb_url = imdb_url_tag[0].attrib["href"][6:-1]
        imdb_url = a2b_base64(base64_imdb_url).decode()
        imdb_url = urllib.parse.unquote(imdb_url)
        if imdb_id not in imdb_url:
            continue
        return article_id, article_tree
    return None, None


def get_article_translators(article_tree, language):
    name = article_tree.xpath('//h1[@itemprop="name"]/text()')[0]
    year = article_tree.xpath(
        '//table[@class="b-post__info"]//td/h2[contains(text(), "Дата")]/../../td/a/text()'
    )[0][:4]

    translators = {}
    translators_elements = article_tree.xpath('//ul[@id="translators-list"]/li')
    for element in translators_elements:
        title = element.attrib["title"].strip()
        flag_img = element.xpath("./img/@src")
        if flag_img:
            flag_code = flag_img[0][-6:-4]
        elif "Оригинал" in title:
            flag_code = "*"
        else:
            flag_code = "ru"

        if language != "all" and flag_code not in (language, "*"):
            continue

        translators[element.attrib["data-translator_id"]] = "\n".join(
            (
                name,
                year,
                element.attrib["title"].strip(),
                FLAGS_MAPPING[flag_code],
            )
        )

    return translators


def get_player_type(article_tree):
    return article_tree.xpath('//meta[@property="og:type"]')[0].attrib["content"]


async def get_article_streams(
    http,
    article_id,
    translators,
    stremio_type,
    season,
    episode,
):
    data = {
        "id": article_id,
    }
    if stremio_type == "series":
        data["action"] = "get_stream"
        data["season"] = (season,)
        data["episode"] = episode
    else:
        data["action"] = "get_movie"

    streams = []
    for translator, title in translators.items():
        data["translator_id"] = translator
        stream_url = await get_stream_url(http, data)
        if stream_url:
            streams.append({"url": stream_url, "title": title})
    return streams


@backoff.on_exception(backoff.expo, Exception)
async def get_stream_url(http, data):
    async with http.post(
        f"https://rezkify.com/ajax/get_cdn_series/?t={int(time.time() * 1000)}",
        data=data,
    ) as response:
        if response.status == 503:
            raise Exception("503")
        text = await response.text()
    json = loads(text)
    if not json["success"]:
        return
    best_quality_stream = clear_trash(json["url"]).split(",")[-1]
    stream_urls = re.findall(
        r"(?:https?:\/\/)?(?:(?i:[a-z]+\.)+)[^\s,]+",
        best_quality_stream,
    )

    for url in stream_urls:
        async with http.get(url, allow_redirects=False) as response:
            stream_url = None
            if location := response.headers.get("Location"):
                stream_url = location
            if response.status == 200:
                stream_url = url
            if stream_url:
                stream_url = URL(stream_url)
                stream_url = stream_url.update_query(host=url.host)
                stream_url = stream_url.with_host(settings.REZKA_PROXY_HOST)
                return str(stream_url)
