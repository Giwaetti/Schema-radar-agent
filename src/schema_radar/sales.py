from __future__ import annotations

from typing import Any


def build_sales_plan(
    *,
    offer_fit: str,
    action_hint: str,
    source_type: str,
    source_name: str,
    title: str,
    summary: str,
    platforms: list[str],
    issue_types: list[str],
    business_name: str | None,
    business_url: str | None,
    offers_config: dict[str, Any],
) -> dict[str, Any]:
    contact_email = offers_config.get("contact_email", "")
    offer_key = _resolve_offer_key(offer_fit, offers_config)
    offer_entry = (offers_config.get("offers") or {}).get(offer_key, {})

    sales_route = _choose_route(source_type, offer_key, business_url)
    cta_destination = offer_entry.get("gumroad_url") or (f"mailto:{contact_email}" if contact_email else None)
    cta_label = offer_entry.get("cta_label") or ("Contact via email" if contact_email else "Review lead")
    reply_subject = _build_subject(offer_fit, title, business_name)
    reply_draft = _build_reply(
        offer_fit=offer_fit,
        offer_key=offer_key,
        sales_route=sales_route,
        action_hint=action_hint,
        title=title,
        summary=summary,
        platforms=platforms,
        issue_types=issue_types,
        business_name=business_name,
        business_url=business_url,
        contact_email=contact_email,
        cta_destination=cta_destination,
    )
    follow_up_draft = _build_follow_up(
        offer_fit=offer_fit,
        offer_key=offer_key,
        sales_route=sales_route,
        business_name=business_name,
        contact_email=contact_email,
        cta_destination=cta_destination,
    )
    return {
        "offer_key": offer_key,
        "sales_route": sales_route,
        "cta_label": cta_label,
        "cta_destination": cta_destination,
        "contact_email": contact_email or None,
        "reply_subject": reply_subject,
        "reply_draft": reply_draft,
        "follow_up_draft": follow_up_draft,
    }



def _resolve_offer_key(offer_fit: str, offers_config: dict[str, Any]) -> str:
    aliases = offers_config.get("aliases") or {}
    if offer_fit in aliases:
        return aliases[offer_fit]
    normalized = offer_fit.strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    if normalized in (offers_config.get("offers") or {}):
        return normalized
    fallback_map = {
        "ai_visibility_kit": "ai_visibility_kit",
        "ai_generator": "ai_generator",
        "done_for_you___service": "direct_service",
        "done_for_you_service": "direct_service",
    }
    return fallback_map.get(normalized, "direct_service")



def _choose_route(source_type: str, offer_key: str, business_url: str | None) -> str:
    if offer_key == "direct_service":
        return "email_contact"
    if source_type == "jobs":
        return "proposal_draft"
    if source_type == "forum":
        return "forum_reply"
    if business_url:
        return "direct_email"
    return "cta_message"



def _build_subject(offer_fit: str, title: str, business_name: str | None) -> str:
    if business_name:
        return f"Schema help for {business_name}"
    return f"Best fit for: {title[:60]}"



def _build_reply(
    *,
    offer_fit: str,
    offer_key: str,
    sales_route: str,
    action_hint: str,
    title: str,
    summary: str,
    platforms: list[str],
    issue_types: list[str],
    business_name: str | None,
    business_url: str | None,
    contact_email: str,
    cta_destination: str | None,
) -> str:
    platform_text = ", ".join(platforms) if platforms else "your stack"
    issue_text = ", ".join(issue_types) if issue_types else "structured data visibility"
    business_ref = business_name or "your site"

    if offer_key == "ai_visibility_kit":
        core = (
            f"It looks like the fastest fix here is a simple schema implementation path for {business_ref}. "
            f"If you want a no-code shortcut for {issue_text}, the AI Visibility Kit is the best fit."
        )
    elif offer_key == "ai_generator":
        core = (
            f"This looks like repeatable schema work on {platform_text}. "
            f"If you want faster JSON-LD output without filling templates manually, the AI Generator is the better fit."
        )
    else:
        core = (
            f"This looks more hands-on than a template-only fix. "
            f"If you want direct help with {issue_text}, email {contact_email}."
        )

    if sales_route == "forum_reply":
        opener = "You can solve this without overcomplicating the build."
    elif sales_route == "proposal_draft":
        opener = "I can help with this."
    elif sales_route == "direct_email":
        opener = f"Hi{f' {business_name}' if business_name else ''},"
    else:
        opener = "Here’s the fastest route I’d take."

    cta_line = _cta_line(offer_key, cta_destination, contact_email)
    note = action_hint.rstrip(".") + "." if action_hint else ""
    parts = [opener, core, note, cta_line]
    return "\n\n".join(part for part in parts if part)



def _build_follow_up(
    *,
    offer_fit: str,
    offer_key: str,
    sales_route: str,
    business_name: str | None,
    contact_email: str,
    cta_destination: str | None,
) -> str:
    name_ref = business_name or "your setup"
    if offer_key == "direct_service":
        return (
            f"Just following up in case you still want hands-on schema help for {name_ref}. "
            f"You can reach me at {contact_email}."
        )
    if sales_route == "proposal_draft":
        return (
            f"Following up in case you still need a clean schema workflow for {name_ref}. "
            f"Best fit: {cta_destination}"
        )
    return (
        f"Following up in case you still want the quickest route to get this live for {name_ref}. "
        f"Best fit: {cta_destination}"
    )



def _cta_line(offer_key: str, cta_destination: str | None, contact_email: str) -> str:
    if offer_key == "direct_service":
        return f"Best next step: email {contact_email} with the page URL and the exact issue."
    if cta_destination:
        return f"Best next step: {cta_destination}"
    if contact_email:
        return f"Best next step: email {contact_email}."
    return ""
