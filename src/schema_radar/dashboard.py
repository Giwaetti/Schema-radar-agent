from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HTML_TEMPLATE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Schema Radar</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; margin: 0; background: #0b1020; color: #ecf1ff; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    .muted {{ color: #adc0ff; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0 24px; }}
    .card {{ background: #121933; border: 1px solid #22315f; border-radius: 16px; padding: 16px; }}
    .card .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #90a4e0; }}
    .card .value {{ font-size: 28px; margin-top: 6px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: #121933; border-radius: 16px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 14px 12px; border-bottom: 1px solid #22315f; vertical-align: top; }}
    th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #9eb2eb; }}
    tr:hover {{ background: #172044; }}
    a {{ color: #84b4ff; }}
    .pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .hot {{ background: #4f1224; color: #ffb9c8; }}
    .warm {{ background: #4c3513; color: #ffd9a1; }}
    .watch {{ background: #173955; color: #b6e2ff; }}
    .noise {{ background: #29314d; color: #cfd8ff; }}
    .small {{ font-size: 13px; color: #b8c7f7; }}
    .stack > div {{ margin-bottom: 4px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>Schema Radar</h1>
    <div class=\"muted\">Generated {generated_at}</div>
    <div class=\"cards\">
      <div class=\"card\"><div class=\"label\">Total leads</div><div class=\"value\">{total}</div></div>
      <div class=\"card\"><div class=\"label\">Hot</div><div class=\"value\">{hot}</div></div>
      <div class=\"card\"><div class=\"label\">Warm</div><div class=\"value\">{warm}</div></div>
      <div class=\"card\"><div class=\"label\">Watch</div><div class=\"value\">{watch}</div></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Lead</th>
          <th>Source</th>
          <th>Stage</th>
          <th>Offer fit</th>
          <th>Audit</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def generate_dashboard(leads: list[dict[str, Any]], output_path: str | Path) -> None:
    counter = Counter(lead["stage"] for lead in leads)
    rows = "\n".join(_row_html(lead) for lead in leads)
    rendered = HTML_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total=len(leads),
        hot=counter.get("hot", 0),
        warm=counter.get("warm", 0),
        watch=counter.get("watch", 0),
        rows=rows,
    )
    Path(output_path).write_text(rendered, encoding="utf-8")


def build_summary(leads: list[dict[str, Any]]) -> dict[str, Any]:
    counter = Counter(lead["stage"] for lead in leads)
    offer_counter = Counter(lead["offer_fit"] for lead in leads)
    source_counter = Counter(lead["source"] for lead in leads)
    return {
        "total": len(leads),
        "by_stage": dict(counter),
        "by_offer": dict(offer_counter),
        "by_source": dict(source_counter),
    }


def _row_html(lead: dict[str, Any]) -> str:
    title = html.escape(lead["title"])
    summary = html.escape((lead.get("summary") or "")[:220])
    source = html.escape(lead["source"])
    source_url = html.escape(lead["source_url"])
    offer = html.escape(lead["offer_fit"])
    action = html.escape(lead["action_hint"])
    stage = html.escape(lead["stage"])
    business_url = lead.get("business_url")
    audit = lead.get("audit") or {}
    audit_bits = []
    if business_url:
        audit_bits.append(f'<div><a href="{html.escape(business_url)}" target="_blank">Business site</a></div>')
    if audit.get("cms"):
        audit_bits.append(f'<div>CMS: {html.escape(str(audit["cms"]))}</div>')
    if audit.get("site_kind"):
        audit_bits.append(f'<div>Site: {html.escape(str(audit["site_kind"]))}</div>')
    gaps = audit.get("opportunity_gaps") or []
    if gaps:
        audit_bits.append(f'<div>Gap: {html.escape(str(gaps[0]))}</div>')
    platforms = ", ".join(lead.get("platforms") or []) or "—"
    issue_types = ", ".join(lead.get("issue_types") or []) or "—"
    return f"""
    <tr>
      <td>
        <div class=\"stack\">
          <div><a href=\"{html.escape(lead['source_url'])}\" target=\"_blank\">{title}</a></div>
          <div class=\"small\">{summary}</div>
          <div class=\"small\">Platforms: {html.escape(platforms)}</div>
          <div class=\"small\">Issues: {html.escape(issue_types)}</div>
        </div>
      </td>
      <td><a href=\"{source_url}\" target=\"_blank\">{source}</a></td>
      <td><span class=\"pill {stage}\">{stage} · {lead['score']}</span></td>
      <td>
        <div class=\"stack\">
          <div>{offer}</div>
          <div class=\"small\">{action}</div>
        </div>
      </td>
      <td><div class=\"stack\">{''.join(audit_bits) or '—'}</div></td>
    </tr>
    """
