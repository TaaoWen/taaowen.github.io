# Tao Wen Academic Homepage

Eight pages are built as static HTML. Publication search, citation copying, the collaboration graph and the contact map run in the browser.

## Publications and cover images

Add or update entries in [data/publications.bib](data/publications.bib). The site uses this file for Publications and for co-authorship in the collaboration graph. Use full author names and a DOI where available. For arXiv, set the `eprint`, `archiveprefix` and `url` fields. An `@unpublished` entry appears under **Work in progress / under review**. Set `status = {Under review}` if appropriate. Draft entries are excluded from the public co-authorship graph.

Place an original image in `assets/media/papers/`, using the BibTeX key as the filename. For example, `wen2022lifespan.png` replaces the image for that paper. The page overlays the blue journal abbreviation. Supported extensions are `.webp`, `.png`, `.jpg` and `.jpeg`. Abbreviations are in [data/venues.json](data/venues.json).

Optional paper details are stored by lowercase DOI in [data/publication-details.json](data/publication-details.json). Set a numeric `selected` value to order a work on About Me. The same record can contain `figure_alt`, `pdf`, `code`, `press`, `theme`, `equal_authors` and `corresponding_authors`. The Publications legend explains † for co-first authors, * for corresponding authors and ‡ for supervised students. Update `supervised_authors` in [data/profile.json](data/profile.json).

## Citation counts

[data/scholar-citations.json](data/scholar-citations.json) contains the 17 November 2026 snapshot imported from the supplied 44-work list. Its total sums citations across those entries. The website shows a paper’s citation count when it exceeds 100.

The GitHub Pages workflow attempts a refresh once a day. It fetches the public author profile with the `user` query first, as permitted by [Google Scholar’s robots.txt](https://scholar.google.com/robots.txt). If Google Scholar limits or fails the request, the scheduled run keeps the previously published snapshot. A successful refresh uses the profile total and keeps the prior counts for papers omitted by the response.

Alternatively, configure a `SERPAPI_KEY` repository Actions secret to use the [SerpApi Google Scholar Author API](https://serpapi.com/google-scholar-author-api). Store credentials only as repository secrets. The provider path and the public-profile path both update the same snapshot format.

To refresh manually, run `python scripts/refresh_scholar.py` and rebuild. If the public profile is unavailable, values can also be updated in the snapshot file. For a manual total summed from the listed works, use `scope = "supplied"` in the JSON data.

## Projects, collaborators and profile

[data/collaborations.json](data/collaborations.json) powers Projects and adds project relationships to the collaboration graph. Each project has an ID, a funding programme, an amount, a role, a year and named participants. The same file can display collaborator profile links and merge name variants with `aliases`.

The collaborator’s display institution is taken from the most recent joint work with verified author-affiliation metadata in [data/work-affiliations.json](data/work-affiliations.json). The affiliation’s tooltip identifies its source paper. The graph assigns colours from three collaboration groups centred on Kang Hao Cheong, Yu-wang Chen / Tahir Abbas Syed, and Yong Deng / Wen Jiang. Assignment is based on the number of shared papers with each group’s anchor authors; project relationships contribute a smaller score. Set `group` for any person in `data/collaborations.json` to override the automatic result manually.

Use [data/profile.json](data/profile.json) for About Me, the sidebar and the Contact address and coordinates. Appointments and activities are in [data/career.json](data/career.json). Replace `assets/media/portrait.webp` and `assets/TaoWen_CV.pdf` to update the portrait and CV.

## Preview locally

From the repository directory, run

```sh
python -m pip install -r requirements.txt
python build.py
python -m http.server 8000 --directory dist
```

Open [http://localhost:8000](http://localhost:8000). Run `python build.py` again after making a change.

## Publish on GitHub Pages

Create the `taaowen.github.io` repository and put these source files at the root of its `main` branch. Choose **GitHub Actions** under **Settings → Pages → Build and deployment → Source**. The included workflow builds and publishes the site when `main` changes. You can also start the workflow from the Actions tab.

The generated website is in `dist/`. You can serve those files on another static host.

## Media credits

Institutional and service logos identify affiliations and links. Google Scholar and GitHub icons are from their official favicons. The ORCID iD mark is from ORCID. The LinkedIn brand mark is sourced from Wikimedia Commons. The envelope icon is from [Font Awesome](https://fontawesome.com/license/free) under CC BY 4.0.

Credited paper figures are listed in [assets/figure-credits.txt](assets/figure-credits.txt). Inter, Noto Sans SC, D3 and Leaflet redistribution notices are included with those assets. Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
