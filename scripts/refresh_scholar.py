"""Refresh the public Google Scholar snapshot and retain any article rows omitted by the source."""
import argparse
from datetime import datetime
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data/profile.json"
SEED = ROOT / "data/scholar-citations.json"
SCHOLAR = "https://scholar.google.com"


def count(value):
    number = str(value).strip().replace(",", "").replace("\u00a0", "")
    if not re.fullmatch(r"[0-9]+", number):
        raise ValueError("The citation value is missing or malformed")
    return int(number)


def scholar_link(url):
    if not url:
        return ""
    absolute = urljoin(SCHOLAR, url)
    parsed = urlsplit(absolute)
    return absolute if parsed.scheme == "https" and parsed.netloc == "scholar.google.com" else ""


class ScholarProfile(HTMLParser):
    def __init__(self, profile_id):
        super().__init__()
        self.profile_id = profile_id
        self.name = ""
        self.total = None
        self.papers = {}
        self.row = None
        self.capture = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        classes = set(attrs.get("class", "").split())
        if attrs.get("id") == "gsc_prf_in":
            self.capture = (tag, "name", attrs, [])
        elif tag == "td" and "gsc_rsb_std" in classes and self.total is None:
            self.capture = (tag, "total", attrs, [])
        elif tag == "tr" and "gsc_a_tr" in classes:
            self.row = {}
        elif tag == "a" and self.row is not None:
            if "gsc_a_at" in classes:
                self.capture = (tag, "article", attrs, [])
            elif "gsc_a_ac" in classes:
                self.capture = (tag, "citations", attrs, [])

    def handle_data(self, data):
        if self.capture:
            self.capture[3].append(data)

    def handle_endtag(self, tag):
        if self.capture and self.capture[0] == tag:
            _, field, attrs, contents = self.capture
            self.capture = None
            text = " ".join("".join(contents).split())
            if field == "name":
                self.name = text
            elif field == "total":
                self.total = count(text)
            elif field == "article":
                link = scholar_link(attrs.get("href"))
                identifier = parse_qs(urlsplit(link).query).get("citation_for_view", [""])[0]
                if identifier.startswith(self.profile_id + ":"):
                    self.row.update(identifier=identifier, title=text, url=link, count=0)
            elif field == "citations" and text and self.row:
                self.row["count"] = count(text)
                self.row["url"] = scholar_link(attrs.get("href")) or self.row["url"]
        if tag == "tr" and self.row is not None:
            identifier = self.row.pop("identifier", None)
            if identifier:
                self.papers[identifier] = self.row
            self.row = None


def read_public_profile(profile_id):
    # The public user-first profile path is allowed by Google's robots.txt.
    # Pagination with cstart, retry loops and challenge bypasses are unnecessary.
    query = urlencode({"user": profile_id, "hl": "en", "pagesize": 100})
    request = Request(f"{SCHOLAR}/citations?{query}", headers={"User-Agent": "AcademicHomepageCitations/1.0"})
    with urlopen(request, timeout=15) as response:
        body = response.read(2_000_000).decode("utf-8")
    page = ScholarProfile(profile_id)
    page.feed(body)
    return page.name, page.total, page.papers


def read_author_api(profile_id, api_key):
    query = urlencode({
        "engine": "google_scholar_author", "author_id": profile_id,
        "num": 100, "hl": "en", "api_key": api_key,
    })
    with urlopen(f"https://serpapi.com/search.json?{query}", timeout=25) as response:
        data = json.load(response)
    stats = next(row["citations"] for row in data["cited_by"]["table"] if "citations" in row)
    works = {}
    for item in data["articles"]:
        identity = item["citation_id"]
        if not identity.startswith(profile_id + ":"):
            continue
        cited_by = item.get("cited_by") or {}
        link = scholar_link(cited_by.get("link") or item.get("link"))
        if not link:
            params = urlencode({"user": profile_id, "view_op": "view_citation", "citation_for_view": identity})
            link = f"{SCHOLAR}/citations?{params}"
        works[identity] = {"title": item["title"], "count": count(cited_by.get("value", 0)), "url": link}
    return data["author"]["name"], count(stats["all"]), works


def freshest_snapshot(path):
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    if not path.is_file():
        return seed
    cached = json.loads(path.read_text(encoding="utf-8"))
    return cached if cached["as_of"] >= seed["as_of"] else seed


def merge_snapshot(previous, total, papers, as_of):
    return {
        "as_of": as_of,
        "scope": "profile",
        "total": total,
        "papers": {
            **{key: {**item, "as_of": item.get("as_of", previous["as_of"])}
               for key, item in previous["papers"].items()},
            **{key: {**item, "as_of": as_of} for key, item in papers.items()},
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=SEED)
    arguments = parser.parse_args()
    path = arguments.output
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    try:
        api_key = os.getenv("SERPAPI_KEY")
        if api_key:
            name, total, papers = read_author_api(profile["scholar_id"], api_key)
        else:
            name, total, papers = read_public_profile(profile["scholar_id"])
        if not name.startswith(profile["name"]) or total is None or not papers:
            raise ValueError("No verified profile statistics were returned")
        previous = freshest_snapshot(path)
        day = datetime.now(ZoneInfo("Europe/London")).date().isoformat()
        updated = merge_snapshot(previous, total, papers, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix(".tmp")
        pending.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pending.replace(path)
    except HTTPError as error:
        print(f"Google Scholar update unavailable (HTTP {error.code}).", file=sys.stderr)
        return 1
    except (OSError, URLError, ValueError, KeyError, StopIteration, TypeError):
        print("Google Scholar update unavailable. Saved citations retained.", file=sys.stderr)
        return 1
    print(f"Updated the Google Scholar profile total and {len(papers)} article records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
