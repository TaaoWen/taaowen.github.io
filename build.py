"""Build the public HTML and collaboration data from the site's source files."""
from collections import defaultdict
import codecs
from datetime import datetime
from itertools import combinations
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import unicodedata
from urllib.parse import quote, urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape
import latexcodec  # Registers the ulatex decoder.
from pybtex.database import BibliographyData, Entry, parse_file


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PAGES = (
    ("About Me", "", "home.html"),
    ("Publications", "publication/", "publications.html"),
    ("Projects", "projects/", "projects.html"),
    ("Awards", "awards/", "awards.html"),
    ("Talks", "talks/", "talks.html"),
    ("Services", "services/", "services.html"),
    ("Collaborators", "collab/", "collaborators.html"),
    ("Contact", "contact/", "contact.html"),
)
CITE_FIELDS = (
    "title", "journal", "booktitle", "year", "volume", "number", "pages",
    "publisher", "address", "doi", "url", "eprint", "archiveprefix",
)
WORKING = "Work in progress / under review"
TYPE_LABELS = {
    "article": "Journal article",
    "inproceedings": "Conference paper",
    "conference": "Conference paper",
    "incollection": "Book chapter",
    "inbook": "Book chapter",
    "book": "Book",
    "phdthesis": "Thesis",
    "mastersthesis": "Thesis",
}


def read_data(filename):
    return json.loads((DATA / filename).read_text(encoding="utf-8"))


def plain_text(value):
    decoded = codecs.decode(value, "ulatex")
    return " ".join(decoded.replace("{", "").replace("}", "").replace("~", " ").split())


def name_key(value):
    text = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in text if character.isalnum())


def slug(value):
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def person_name(person):
    words = (
        person.first_names + person.middle_names + person.prelast_names
        + person.last_names + person.lineage_names
    )
    return plain_text(" ".join(words))


def external_url(value):
    if not value:
        return ""
    url = urlsplit(value)
    return value if url.scheme in ("https", "http") and url.hostname else ""


def date_label(value):
    if len(value) == 4:
        return value
    if len(value) == 10:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y").lstrip("0")
    return datetime.strptime(value, "%Y-%m").strftime("%b %Y")


def matched_asset(filename):
    if filename:
        candidate = (ROOT / filename).resolve()
        if candidate.is_relative_to(ROOT / "assets") and candidate.is_file():
            return filename
    return ""


def cite_text(key, entry, doi):
    fields = {name: entry.fields[name] for name in CITE_FIELDS if name in entry.fields}
    if doi:
        fields["doi"] = doi
    cite_entry = Entry(entry.type, fields=fields, persons=entry.persons)
    return BibliographyData(entries={key: cite_entry}).to_string("bibtex").strip()


def publications(profile, people, scholar):
    details = read_data("publication-details.json")
    affiliations = read_data("work-affiliations.json")
    citations_by_title = {name_key(item["title"]): item for item in scholar["papers"].values()}
    venues = {name.casefold(): label for name, label in read_data("venues.json").items()}
    aliases = {
        name_key(alias): name
        for name, info in people.items()
        for alias in [name, *info.get("aliases", [])]
    }
    own_names = {name_key(name) for name in profile["bibtex_names"]}
    students = {name_key(name) for name in profile.get("supervised_authors", [])}
    bibliography = parse_file(DATA / "publications.bib", bib_format="bibtex")
    seen = set()
    papers = []
    for key, record in bibliography.entries.items():
        fields = record.fields
        doi = re.sub(r"^(https?://(?:dx\.)?doi\.org/|doi:\s*)", "", fields.get("doi", ""), flags=re.I).strip()
        work_id = doi.lower() or name_key(plain_text(fields["title"]))
        if work_id in seen:
            continue
        seen.add(work_id)
        metadata = details.get(work_id, {})
        title = plain_text(fields["title"])
        venue = plain_text(fields.get("journal") or fields.get("booktitle") or fields.get("publisher", ""))
        year_digits = re.search(r"\b[12]\d{3}\b", fields.get("year", ""))
        year = int(year_digits[0]) if year_digits else None
        kind = TYPE_LABELS.get(record.type, "Other")
        arxiv = fields.get("eprint") and fields.get("archiveprefix", "arXiv").lower() == "arxiv"
        if "arxiv" in venue.casefold() or (arxiv and not venue):
            kind = "Preprint"
        elif record.type == "unpublished":
            kind = WORKING
        kind = metadata.get("type", kind)
        status = plain_text(fields.get("status", "Work in progress")) if kind == WORKING else ""
        cited = scholar["papers"].get(metadata.get("scholar_id") or fields.get("scholar_id"))
        if cited is None:
            cited = citations_by_title.get(name_key(title), {})
        paper_affiliations = {
            name_key(name): institutions for name, institutions in affiliations.get(work_id, {}).items()
        }
        authors = []
        for person in record.persons.get("author", []):
            original_name = person_name(person)
            if original_name.casefold() in ("others", "et al."):
                continue
            own = name_key(original_name) in own_names
            author_name = profile["name"] if own else aliases.get(name_key(original_name), original_name)
            authors.append({
                "name": author_name,
                "own": own,
                "equal": author_name in metadata.get("equal_authors", []),
                "corresponding": author_name in metadata.get("corresponding_authors", []),
                "supervised": name_key(author_name) in students,
                "affiliations": paper_affiliations.get(
                    name_key(author_name), paper_affiliations.get(name_key(original_name), [])
                ),
            })
        doi_url = f"https://doi.org/{quote(doi, safe='/')}" if doi else ""
        link = doi_url or external_url(fields.get("url"))
        press = external_url(metadata.get("press") or fields.get("press"))
        pdf = external_url(metadata.get("pdf") or fields.get("pdf"))
        eprint = fields.get("eprint", "")
        if not pdf and eprint and fields.get("archiveprefix", "arXiv").lower() == "arxiv":
            pdf = f"https://arxiv.org/pdf/{quote(eprint, safe='/')}"
        uploaded_images = (f"assets/media/papers/{key}.{extension}"
                           for extension in ("webp", "png", "jpg", "jpeg"))
        figure = next(filter(None, map(matched_asset, uploaded_images)), "")
        figure = figure or matched_asset(metadata.get("figure"))
        papers.append({
            "id": f"paper-{slug(doi.lower() or key)}",
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "short_venue": metadata.get("venue_short") or venues.get(venue.casefold()) or venue or status or kind,
            "type": kind,
            "status": status,
            "published_date": metadata.get("published_date") or (f"{year}-01-01" if year else ""),
            "theme": metadata.get("theme", "networks"),
            "cited": cited.get("count", 0) if kind != WORKING else 0,
            "scholar_url": external_url(cited.get("url")),
            "scholar_date": cited.get("as_of", scholar["as_of"]),
            "url": link,
            "doi": doi_url,
            "pdf": pdf,
            "code": external_url(metadata.get("code") or fields.get("code")),
            "press": press,
            "figure": figure,
            "figure_alt": metadata.get("figure_alt") or f"Figure for {title}",
            "abstract_tag": metadata.get("topic", ""),
            "selected": metadata.get("selected"),
            "citation": cite_text(key, record, doi),
        })
    return sorted(
        papers,
        key=lambda paper: (paper["year"] or 0, paper["published_date"], paper["title"].casefold()),
        reverse=True,
    )


def collaboration_graph(profile, papers, collaborations):
    root = name_key(profile["name"])
    people = collaborations["people"]
    groups = collaborations["groups"]
    group_ids = {group["id"] for group in groups}
    group_rank = {group["id"]: index for index, group in enumerate(groups)}
    aliases = {
        name_key(alias): name
        for name, info in people.items()
        for alias in [name, *info.get("aliases", [])]
    }
    group_anchors = {
        group["id"]: {
            name_key(aliases.get(name_key(anchor), anchor)) for anchor in group["anchors"]
        }
        for group in groups
    }
    nodes = {}
    edges = defaultdict(lambda: {"coauthor": 0, "project": 0})

    def node(name):
        canonical = aliases.get(name_key(name), name)
        identity = name_key(canonical)
        if identity not in nodes:
            details = people.get(canonical, {})
            nodes[identity] = {
                "id": identity,
                "name": canonical,
                "url": external_url(details.get("url")),
                "affiliations": [],
                "affiliation_source": "",
                "papers": [],
                "projects": [],
                "group_scores": defaultdict(float),
            }
        return nodes[identity]

    def connect(ids, relation):
        for source, target in combinations(sorted(set(ids)), 2):
            edges[source, target][relation] += 1

    def score_groups(ids, weight):
        member_ids = set(ids)
        for group_id, anchors in group_anchors.items():
            if member_ids & anchors:
                for identity in member_ids - {root}:
                    nodes[identity]["group_scores"][group_id] += weight

    node(profile["name"])
    published = sorted(papers, key=lambda paper: paper["published_date"], reverse=True)
    for paper in published:
        if not any(author["own"] for author in paper["authors"]):
            continue
        ids = []
        for author in paper["authors"]:
            member = node(author["name"])
            member["papers"].append(paper["id"])
            if not member["affiliations"] and author["affiliations"]:
                member["affiliations"] = author["affiliations"]
                member["affiliation_source"] = f'{paper["title"]} ({paper["year"]})'
            ids.append(member["id"])
        connect(ids, "coauthor")
        score_groups(ids, 1.0)

    projects = sorted(collaborations["projects"], key=lambda project: -project["year"])
    for index, project in enumerate(projects):
        ids = {root}
        for name in project["participants"]:
            member = node(name)
            member["projects"].append(index)
            ids.add(member["id"])
        nodes[root]["projects"].append(index)
        connect(ids, "project")
        score_groups(ids, 0.6)

    for member in nodes.values():
        if not member["affiliations"]:
            affiliation = people.get(member["name"], {}).get("project_affiliation")
            if affiliation:
                member["affiliations"] = [affiliation]
                member["affiliation_source"] = "Institutional project affiliation"
        scores = member.pop("group_scores")
        override = people.get(member["name"], {}).get("group")
        if override in group_ids:
            member["group"] = override
        elif scores and max(scores.values()) > 0:
            member["group"] = max(
                scores,
                key=lambda group_id: (scores[group_id], -group_rank[group_id]),
            )
        else:
            member["group"] = "unassigned"

    return {
        "root": root,
        "groups": groups,
        "nodes": sorted(nodes.values(), key=lambda item: (item["id"] != root, item["name"].casefold())),
        "links": [
            {"source": a, "target": b, "coauthor": edge["coauthor"], "project": edge["project"]}
            for (a, b), edge in edges.items()
        ],
        "papers": {item["id"]: {"title": item["title"], "year": item["year"]} for item in papers},
        "projects": projects,
    }


def review_list(by_year):
    years = defaultdict(set)
    for year, names in by_year.items():
        for name in names:
            years[name].add(year)
    return [
        {"name": name, "dates": ", ".join(sorted(years[name], reverse=True))}
        for name in sorted(years, key=lambda name: re.sub(r"^the ", "", name.casefold()))
    ]


def build():
    profile = read_data("profile.json")
    career = read_data("career.json")
    collaborations = read_data("collaborations.json")
    scholar = read_data("scholar-citations.json")
    papers = publications(profile, collaborations["people"], scholar)
    selected = sorted(
        (paper for paper in papers if paper["selected"] is not None),
        key=lambda paper: paper["selected"],
    )
    for key in ("news", "talks"):
        career[key].sort(key=lambda item: item["date"], reverse=True)
    for key in ("awards", "editorial", "chairing"):
        career[key].sort(key=lambda item: item["year"], reverse=True)
    for record in career["experience"] + career["education"]:
        record["image"] = matched_asset(f"assets/media/{record['logo']}-logo.webp")
    career["journals"] = review_list(career["journal_review"])
    career["conferences"] = review_list(career["committees"])
    graph = collaboration_graph(profile, papers, collaborations)
    templates = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    templates.filters["date_label"] = date_label
    templates.filters["count_format"] = lambda value: format(value, ",d")

    with TemporaryDirectory(prefix="build-", dir=ROOT) as directory:
        output = Path(directory) / "site"
        shutil.copytree(ROOT / "assets", output / "assets")
        (output / ".nojekyll").touch()
        for label, route, filename in PAGES:
            page_directory = output / route
            page_directory.mkdir(parents=True, exist_ok=True)
            html = templates.get_template(filename).render(
                profile=profile, career=career, publications=papers, selected=selected,
                graph=graph, pages=PAGES, route=route, label=label,
                scholar=scholar, work_in_progress=WORKING,
                years=sorted({work["year"] for work in papers if work["year"]}, reverse=True),
                types=sorted({WORKING, *(work["type"] for work in papers)}),
                base="../" if route else "./",
            )
            (page_directory / "index.html").write_text(html, encoding="utf-8")
        destination = ROOT / "dist"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(output, destination)
    print(f"Built {len(PAGES)} pages with {len(papers)} publications, {len(selected)} selected works "
          f"and {len(graph['nodes']) - 1} collaborators.")


if __name__ == "__main__":
    build()
