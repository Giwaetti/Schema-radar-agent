from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from schema_radar.config import load_keywords, load_sources
from schema_radar.pipeline import SchemaRadarPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Schema Radar lead discovery pipeline.")
    parser.add_argument("--sources", default="sources.yaml", help="Path to sources YAML file")
    parser.add_argument("--keywords", default="keywords.yaml", help="Path to keywords YAML file")
    parser.add_argument("--out-dir", default="data", help="Directory for JSON and CSV output")
    parser.add_argument("--docs-dir", default="docs", help="Directory for static dashboard output")
    parser.add_argument("--skip-audit", action="store_true", help="Skip business-site audit requests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = load_sources(ROOT / args.sources)
    keywords = load_keywords(ROOT / args.keywords)
    pipeline = SchemaRadarPipeline(
        sources=sources,
        keyword_config=keywords,
        out_dir=ROOT / args.out_dir,
        docs_dir=ROOT / args.docs_dir,
        audit_sites=not args.skip_audit,
    )
    summary = pipeline.run()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
