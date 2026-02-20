"""Unit tests for Match query pagination model."""

from importer.web.components.match_grid import (
    MATCH_DEFAULT_PAGE_SIZE,
    apply_match_query,
)


def _rows(count: int, source_type: str = "PRJ") -> list[dict]:
    return [
        {
            "source_key": f"{source_type.lower()}_{i}",
            "source_type": source_type,
            "source_name": f"{source_type}-{i}",
        }
        for i in range(count)
    ]


def test_apply_match_query_defaults_to_200_rows_per_page() -> None:
    rows = _rows(250)
    result = apply_match_query(rows)
    assert result["page_size"] == MATCH_DEFAULT_PAGE_SIZE
    assert result["page"] == 1
    assert result["total_pages"] == 2
    assert len(result["page_rows"]) == 200


def test_apply_match_query_supports_type_filter() -> None:
    rows = _rows(4, "PRJ") + _rows(3, "ENV")
    result = apply_match_query(rows, type_filter="ENV")
    assert result["total_filtered"] == 3
    assert all(r["source_type"] == "ENV" for r in result["page_rows"])


def test_apply_match_query_clamps_requested_page() -> None:
    rows = _rows(30)
    result = apply_match_query(rows, page=9, page_size=10)
    assert result["total_pages"] == 3
    assert result["page"] == 3
    assert len(result["page_rows"]) == 10

