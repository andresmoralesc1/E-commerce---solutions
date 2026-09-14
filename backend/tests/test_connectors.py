"""Tests para connectors — Shopify + Woo parsing + Meta/Google SDK."""
import pytest

from app.connectors.shopify import VARIANT_UPDATE
from app.connectors.meta_ads import build_auth_url, json_dumps_range


class TestShopifyGraphQL:
    def test_variant_update_mutation_exists(self):
        assert "productVariantUpdate" in VARIANT_UPDATE
        assert "price" in VARIANT_UPDATE


class TestMetaAuthURL:
    def test_build_auth_url(self):
        url = build_auth_url("app_123", "https://example.com/cb", state="tid-abc")
        assert "client_id=app_123" in url
        assert "redirect_uri=" in url
        assert "state=tid-abc" in url
        assert "scope=ads_management" in url
        assert "facebook.com" in url


class TestMetaDateRange:
    def test_json_dumps_range(self):
        from datetime import date
        result = json_dumps_range(date(2026, 1, 1), date(2026, 1, 31))
        import json
        parsed = json.loads(result)
        assert parsed["since"] == "2026-01-01"
        assert parsed["until"] == "2026-01-31"


class TestSecurity:
    """Tests de auth/security."""

    def test_password_hash_and_verify(self):
        from app.core.security import hash_password, verify_password
        plain = "mysecretpassword123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_token_roundtrip(self):
        from uuid import uuid4
        from app.core.security import create_access_token, get_current_user
        from fastapi.security import OAuth2PasswordBearer
        # Test solo la creación del token (decode requiere DB)
        user_id = uuid4()
        token = create_access_token(user_id, "test@example.com", False)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3   # JWT structure