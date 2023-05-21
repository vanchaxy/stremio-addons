import json
import re

import lxml.html
from asyncer import asyncify
from unidecode import unidecode

from stremio_addons.config import settings


async def get_article_tree(cloudflare, name, year):
    response = await asyncify(cloudflare.post)(
        "https://eneyida.tv/index.php?do=search",
        data={
            "do": "search",
            "subaction": "search",
            "search_start": 0,
            "full_search": 0,
            "result_from": 1,
            "story": name,
        },
    )

    result_tree = None
    search_tree = lxml.html.fromstring(response.text)
    articles = search_tree.xpath("//section[@class='section']//article")
    for index, article in enumerate(articles):
        subtitle = article.xpath(".//div[@class='short_subtitle']")[0]
        article_year, article_name = re.match(
            r"(\d{4}) • (.+)", subtitle.text_content()
        ).groups()

        if year == article_year or not index:
            article_url = article.xpath('.//a[@class="short_title"]')[0].attrib["href"]
            article_page = (await asyncify(cloudflare.get)(article_url)).text
            article_tree = lxml.html.fromstring(article_page)

        # will use the first search result if we don't find a better match
        if not index:
            result_tree = article_tree

        # release year mismatch, skip
        if year != article_year:
            continue

        # name match, most common case
        article_name = unidecode(article_name.lower())
        if article_name == name:
            result_tree = article_tree
            break

        # Some titles have different names on IMDb and Eneyida
        # e.g. 'Attack on Titan' -> 'Shingeki no Kyojin'
        # in such cases, try to match the titles using keywords
        keywords = article_tree.xpath('//meta[@name="keywords"]/@content')[0].lower()
        keywords = [unidecode(k.strip()) for k in keywords.split(",")]
        if name in keywords:
            result_tree = article_tree
            break

    return result_tree


def parse_article_tree(article_tree):
    source_url = article_tree.xpath('(//div[@class="tabs_box"]//iframe/@src)[1]')[0]
    ua_name = article_tree.xpath("//h1/text()")[0]
    year = article_tree.xpath(
        '//ul[@class="full_info"]/li/span[contains(text(), "Рік")]/../a/text()'
    )[0]
    return {
        "source_url": source_url,
        "ua_name": ua_name,
        "year": year,
    }


async def get_article_source(http, source_url):
    async with http.get(source_url, proxy=settings.ENEYIDA_PROXY) as response:
        content = await response.text()

    tree = lxml.html.fromstring(content)
    js_scripts = tree.xpath("//script[@type]")
    for script in js_scripts:
        text = script.text_content()
        if "Playerjs(" in text:
            return re.findall(r'file:[\'"](.+)[\'"],\n', text)[0]


def create_article_streams(source, name, year, stremio_type, season, episode):
    base_title = f"{name}\n{year}"

    if source.startswith("http"):
        return [{"url": source, "title": base_title}]
    else:
        streams = []
        source = json.loads(source)
        for dubbing in source:
            title = base_title + "\n" + dubbing["title"]
            folders = dubbing.get("folder")

            if not folders:
                streams.append(
                    {
                        "title": title,
                        "url": dubbing["file"],
                    }
                )

            if stremio_type != "series":
                continue

            for season_folder in folders:
                folder_title = season_folder["title"]
                folder_season = re.findall(r"\d+", folder_title)[0]
                if folder_season != season:
                    continue

                for episode_source in season_folder["folder"]:
                    episode_title = episode_source["title"]
                    episode_num = re.findall(r"\d+", episode_title)[0]
                    if episode == episode_num:
                        streams.append(
                            {
                                "title": title,
                                "url": episode_source["file"],
                            }
                        )
    return streams
