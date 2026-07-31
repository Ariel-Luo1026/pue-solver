"""Generic report-section renderer.

This module turns structured report section payloads into HTML-ready data. It
does not know topology names or equipment families; rows are rendered from
their declared keys and values.
"""


def render_report_sections(report_sections):
    """Return normalized, HTML-ready report sections."""
    sections = []
    for section in _iter_sections(report_sections):
        rows = section.get("rows") if isinstance(section, dict) else []
        rows = rows or []
        normalized = {
            "id": str(section.get("id") or ""),
            "title": str(section.get("title") or section.get("id") or "Report Section"),
            "status": section.get("status"),
            "rows": [_normalize_row(row) for row in rows if row is not None],
        }
        sections.append(normalized)
    return {"sections": sections}


def _iter_sections(report_sections):
    if isinstance(report_sections, list):
        yield from (section for section in report_sections if isinstance(section, dict))
        return
    if not isinstance(report_sections, dict):
        return
    for key in ("common", "topology_specific"):
        value = report_sections.get(key)
        if isinstance(value, list):
            yield from (section for section in value if isinstance(section, dict))


def _normalize_row(row):
    if isinstance(row, dict):
        return {str(key): _normalize_value(value) for key, value in row.items()}
    if isinstance(row, (tuple, list)) and len(row) == 2:
        return {"label": _normalize_value(row[0]), "value": _normalize_value(row[1])}
    return {"value": _normalize_value(row)}


def _normalize_value(value):
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value
