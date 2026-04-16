# Schema Radar Agent

Schema Radar Agent is a live lead-finding agent for schema and structured-data offers.
It pulls fresh items from public forums, support boards, and job pages, scores them,
audits linked sites for schema opportunity, and publishes a static dashboard you can host with GitHub Pages.

## What this build does live

- Pulls live items from public RSS feeds and public HTML pages
- Supports these source kinds:
  - `rss`
  - `html_list`
  - `html_links`
- Extracts titles, snippets, thread/job URLs, dates when available, and likely external business URLs
- Scores each item for:
  - schema relevance
  - buying intent
  - freshness
- Detects likely platforms such as Shopify, WooCommerce, WordPress, Wix, Webflow, and Squarespace
- Audits linked external sites for:
  - JSON-LD presence
  - schema types found
  - CMS hints
  - ecommerce vs local-service signals
  - common gaps such as missing Product or LocalBusiness/Service schema
- Matches each lead to one of three offers:
  - **AI Visibility Kit**
  - **AI Generator**
  - **Done-for-you / service**
- Saves output to:
  - `data/leads.json`
  - `data/leads.csv`
  - `data/summary.json`
  - `docs/index.html`
- Runs manually or on a schedule with GitHub Actions

## Live source pack included

The default `sources.yaml` is already set up for live public sources:

- Reddit `/r/SEO` RSS
- Reddit `/r/shopify` RSS
- Reddit `/r/woocommerce` RSS
- Reddit `/r/TechSEO` RSS
- Shopify Community SEO forum
- WordPress support board for **Schema & Structured Data for WP & AMP**
- Google Search Central Community thread page
- Upwork Schema Markup jobs page

## Project structure

```text
schema-radar-agent/
├── .github/workflows/schema-radar.yml
├── data/
├── docs/
├── src/schema_radar/
│   ├── audit.py
│   ├── config.py
│   ├── dashboard.py
│   ├── fetch.py
│   ├── matcher.py
│   ├── models.py
│   ├── parsers.py
│   ├── pipeline.py
│   ├── scoring.py
│   └── utils.py
├── keywords.yaml
├── requirements.txt
├── run.py
├── sources.yaml
└── tests/
```

## Quick start

### 1) Local test run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py --sources sources.yaml --keywords keywords.yaml --out-dir data --docs-dir docs
```

That will create a fresh live snapshot from the enabled public sources.

### 2) Open the dashboard

After the run finishes, open:

- `docs/index.html`

### 3) Check the raw lead file

- `data/leads.json`
- `data/leads.csv`

## Cloud run with no local terminal dependency

This repo is already wired for GitHub Actions.

### Deploy steps

1. Create a GitHub repo
2. Upload the project files
3. Commit and push to your default branch
4. In GitHub, open **Settings → Pages** and publish from the `docs/` folder on the default branch
5. Open **Actions** and run the `Schema Radar` workflow manually once
6. After that, it will also run on the schedule inside `.github/workflows/schema-radar.yml`

## How the pipeline works

1. Load live source definitions from `sources.yaml`
2. Pull RSS and public HTML pages
3. Parse candidate threads/jobs/posts
4. Deduplicate items
5. Score for relevance and buying intent
6. Extract likely external business URLs where available
7. Audit external sites for schema opportunity
8. Match the lead to the best offer
9. Save JSON, CSV, summary, and dashboard output

## Live-testing notes

- `rss` sources are the fastest and cleanest to test first
- `html_links` is designed for public community/job pages where RSS is missing or incomplete
- relative times such as `2 hours ago` are converted into UTC timestamps for scoring
- site audits only run when the item contains an external business URL
- job-board items can still be valuable even when no external business URL is present

## Source configuration

### RSS source

```yaml
- id: reddit-seo
  name: Reddit /r/SEO
  kind: rss
  enabled: true
  url: https://www.reddit.com/r/SEO/new.rss
  source_type: forum
```

### HTML list source

```yaml
- id: wp-support-schema
  name: WordPress support - schema plugin
  kind: html_list
  enabled: true
  url: https://wordpress.org/support/plugin/schema-and-structured-data-for-wp/
  base_url: https://wordpress.org
  source_type: forum
  selectors:
    item: 'tr, li, .topic'
    title: 'a'
    link: 'a'
    snippet: '.topic-excerpt, .bbp-topic-content, .excerpt'
    published: 'time'
```

### HTML links source

Use this when the page is public but the structure is easier to harvest by filtering links than by fixed row selectors.

```yaml
- id: shopify-seo-forum
  name: Shopify Community SEO Forum
  kind: html_links
  enabled: true
  url: https://community.shopify.com/c/seo/288
  base_url: https://community.shopify.com
  source_type: forum
  include_patterns:
    - /t/
  exclude_patterns:
    - /latest
    - /top
  max_items: 40
```

## Output fields

Each lead record includes:

- source and source id
- source type
- thread/job URL
- title and summary
- published date if available
- stage and score
- score breakdown
- detected platforms
- detected issue types
- business name and business URL when found
- audit summary
- matched offer
- action hint

## Useful next edits

- add more sources to `sources.yaml`
- tune `keywords.yaml` to sharpen scoring
- lower or raise hot/warm/watch thresholds
- add new blocked domains in `pipeline.py` if a source starts polluting URL extraction
- add outreach generation once lead quality looks right

## Commands you will actually use

Run live scan:

```bash
python run.py
```

Run without auditing external sites:

```bash
python run.py --skip-audit
```

## What changed from the earlier MVP

- removed reliance on bundled output files for showing value
- enabled live public sources by default
- added `html_links` parsing for public pages without stable RSS
- added relative-time parsing like `2 hours ago`
- kept the project cloud-runnable through GitHub Actions
