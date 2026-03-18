"""Tests for account features fetch (private API; graceful failure when unavailable)."""

from __future__ import annotations

from unittest.mock import patch

from importer.client import ApiError, DbtCloudClient
from importer.config import Settings
from importer.fetcher import _fetch_account_features


def test_fetch_account_features_maps_provider_response() -> None:
    """When private API returns provider-style data, we map kebab-case to model."""
    settings = Settings(api_token="test", account_id=123, host="https://cloud.getdbt.com")
    client = DbtCloudClient(settings)

    # Provider/private API returns data with kebab-case and ai_features
    api_data = {
        "data": {
            "advanced-ci": True,
            "partial-parsing": False,
            "repo-caching": True,
            "ai_features": True,
            "catalog-ingestion": False,
            "explorer-account-ui": True,
            "fusion-migration-permissions": False,
        },
        "status": 200,
    }

    with patch.object(client, "get_at_api_root", return_value=api_data):
        result = _fetch_account_features(client, progress=None)

    assert result is not None
    assert result.advanced_ci is True
    assert result.partial_parsing is False
    assert result.repo_caching is True
    assert result.ai_features is True
    assert result.catalog_ingestion is False
    assert result.explorer_account_ui is True
    assert result.fusion_migration_permissions is False
    assert "advanced-ci" in result.metadata

    client.close()


def test_fetch_account_features_returns_none_on_failure() -> None:
    """When private API is unavailable (e.g. 403/404), we return None and do not raise."""
    settings = Settings(api_token="test", account_id=123, host="https://cloud.getdbt.com")
    client = DbtCloudClient(settings)

    with patch.object(client, "get_at_api_root", side_effect=ApiError(type("R", (), {"status_code": 403, "text": "Forbidden"})())):
        result = _fetch_account_features(client, progress=None)

    assert result is None
    client.close()


def test_fetch_account_features_calls_correct_path() -> None:
    """Fetcher uses get_at_api_root with /private/accounts/{id}/features/."""
    settings = Settings(api_token="test", account_id=456, host="https://cloud.getdbt.com")
    client = DbtCloudClient(settings)

    with patch.object(client, "get_at_api_root", return_value={"data": {}}) as mock_get:
        _fetch_account_features(client, progress=None)
        mock_get.assert_called_once_with("/private/accounts/456/features/")

    client.close()
