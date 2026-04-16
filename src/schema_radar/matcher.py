from __future__ import annotations

from .models import AuditResult


def match_offer(stage: str, platforms: list[str], issue_types: list[str], audit: AuditResult | None) -> tuple[str, str]:
    schema_types = {entry.lower() for entry in (audit.schema_types if audit else [])}
    platform_set = set(platforms)
    issue_set = set(issue_types)

    if audit and audit.site_kind == "ecommerce":
        if stage in {"hot", "warm"} and ("product_schema" in issue_set or "product" not in schema_types):
            return "AI Visibility Kit", "Offer a fast product-schema visibility fix or implementation shortcut."
        return "AI Generator", "Position it as repeatable schema generation for product and category pages."

    if audit and audit.site_kind == "local_service":
        return "AI Visibility Kit", "Pitch LocalBusiness/Service markup improvements for clearer search understanding."

    if "shopify" in platform_set or "woocommerce" in platform_set or "wordpress" in platform_set:
        if stage == "hot":
            return "Done-for-you / service", "Respond as hands-on implementation help for an active schema problem."
        return "AI Generator", "Position it as faster schema output for recurring implementation work."

    if stage == "hot":
        return "Done-for-you / service", "Treat this as a direct service lead first."

    return "AI Visibility Kit", "Lead with a lightweight, lower-friction offer."
