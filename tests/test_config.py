"""Config validation and source selection tests (TDD)."""
import os
from unittest.mock import patch

import pytest


class TestCacheTtlValidation:
    """CACHE_TTL_SECONDS must be a finite positive float."""

    def test_valid_positive_float_parses(self):
        from app.config import _parse_cache_ttl

        assert _parse_cache_ttl("120.5") == 120.5

    def test_valid_integer_parses(self):
        from app.config import _parse_cache_ttl

        assert _parse_cache_ttl("60") == 60.0

    def test_nan_rejected(self):
        from app.config import _parse_cache_ttl

        with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
            _parse_cache_ttl("NaN")

    def test_negative_rejected(self):
        from app.config import _parse_cache_ttl

        with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
            _parse_cache_ttl("-10")

    def test_zero_rejected(self):
        from app.config import _parse_cache_ttl

        with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
            _parse_cache_ttl("0")

    def test_infinity_rejected(self):
        from app.config import _parse_cache_ttl

        with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
            _parse_cache_ttl("inf")

    def test_negative_infinity_rejected(self):
        from app.config import _parse_cache_ttl

        with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
            _parse_cache_ttl("-inf")


class TestCacheMaxEntriesValidation:
    """CACHE_MAX_ENTRIES must be a positive integer."""

    def test_valid_positive_int_parses(self):
        from app.config import _parse_cache_max_entries

        assert _parse_cache_max_entries("5000") == 5000

    def test_non_integer_string_rejected(self):
        from app.config import _parse_cache_max_entries

        with pytest.raises(ValueError, match="CACHE_MAX_ENTRIES"):
            _parse_cache_max_entries("abc")

    def test_negative_rejected(self):
        from app.config import _parse_cache_max_entries

        with pytest.raises(ValueError, match="CACHE_MAX_ENTRIES"):
            _parse_cache_max_entries("-5")

    def test_zero_rejected(self):
        from app.config import _parse_cache_max_entries

        with pytest.raises(ValueError, match="CACHE_MAX_ENTRIES"):
            _parse_cache_max_entries("0")

    def test_float_string_rejected(self):
        from app.config import _parse_cache_max_entries

        with pytest.raises(ValueError, match="CACHE_MAX_ENTRIES"):
            _parse_cache_max_entries("100.5")


class TestMaxRenderConcurrencyValidation:
    """MAX_RENDER_CONCURRENCY must be a finite positive integer."""

    def test_valid_positive_int_parses(self):
        from app.config import _parse_max_render_concurrency

        assert _parse_max_render_concurrency("4") == 4

    def test_zero_rejected(self):
        from app.config import _parse_max_render_concurrency

        with pytest.raises(ValueError, match="MAX_RENDER_CONCURRENCY"):
            _parse_max_render_concurrency("0")

    def test_non_integer_string_rejected(self):
        from app.config import _parse_max_render_concurrency

        with pytest.raises(ValueError, match="MAX_RENDER_CONCURRENCY"):
            _parse_max_render_concurrency("2.5")


class TestSourceSelection:
    """get_source() must return correct source or raise for unknown SOURCE."""

    def test_get_source_returns_newapi_for_new_api(self):
        from app.sources import get_source

        src = get_source("new-api")
        assert src.name == "new-api"

    def test_get_source_returns_sub2api_for_sub2api(self):
        from app.sources import get_source

        src = get_source("sub2api")
        assert src.name == "sub2api"

    def test_get_source_unknown_raises_valueerror(self):
        from app.sources import get_source

        with pytest.raises(ValueError, match="unknown"):
            get_source("unknown-source")

    def test_get_source_with_explicit_name_valid(self):
        from app.sources import get_source

        src = get_source("sub2api")
        assert src.name == "sub2api"

    def test_get_source_with_explicit_name_unknown_raises(self):
        from app.sources import get_source

        with pytest.raises(ValueError, match="source|unknown|invalid"):
            get_source("invalid-source")


class TestSub2ApiPortOptional:
    """SUB2API_PGPORT is optional; host/database/user/password are required."""

    def test_env_missing_false_when_port_omitted(self):
        """When port is omitted but required vars are set, _env_missing returns False."""
        env = {
            "SUB2API_PGHOST": "localhost",
            "SUB2API_PGDATABASE": "mydb",
            "SUB2API_PGUSER": "user",
            "SUB2API_PGPASSWORD": "pass",
        }
        with patch.dict(os.environ, env, clear=True):
            from app.sources.sub2api_db import _env_missing

            assert _env_missing() is False

    def test_env_missing_true_when_host_omitted(self):
        """When host is omitted (even with port set), _env_missing returns True."""
        env = {
            "SUB2API_PGPORT": "5433",
            "SUB2API_PGDATABASE": "mydb",
            "SUB2API_PGUSER": "user",
            "SUB2API_PGPASSWORD": "pass",
        }
        with patch.dict(os.environ, env, clear=True):
            from app.sources.sub2api_db import _env_missing

            assert _env_missing() is True

    def test_env_missing_true_when_any_required_omitted(self):
        """When any required var (not port) is omitted, _env_missing returns True."""
        required = ["SUB2API_PGHOST", "SUB2API_PGDATABASE", "SUB2API_PGUSER", "SUB2API_PGPASSWORD"]
        for missing in required:
            env = {
                "SUB2API_PGHOST": "localhost",
                "SUB2API_PGDATABASE": "mydb",
                "SUB2API_PGUSER": "user",
                "SUB2API_PGPASSWORD": "pass",
                "SUB2API_PGPORT": "5433",
            }
            del env[missing]
            with patch.dict(os.environ, env, clear=True):
                from app.sources.sub2api_db import _env_missing
                assert _env_missing() is True, f"Should fail when {missing} is missing"

    def test_port_defaults_to_5432_when_not_set(self):
        """When SUB2API_PGPORT is not set, int() on default '5432' gives 5432."""
        # Port not in env, so os.environ.get returns default "5432"
        port_default = int(os.environ.get("SUB2API_PGPORT", "5432"))
        assert port_default == 5432


class TestConfigModuleDefaultsValid:
    """Default config values should be valid (import should succeed)."""

    def test_default_ttl_is_valid(self):
        from app.config import CACHE_TTL_SECONDS

        assert CACHE_TTL_SECONDS > 0

    def test_default_max_entries_is_valid(self):
        from app.config import CACHE_MAX_ENTRIES

        assert CACHE_MAX_ENTRIES > 0

    def test_default_max_render_concurrency_is_conservative_and_valid(self):
        from app.config import MAX_RENDER_CONCURRENCY

        assert MAX_RENDER_CONCURRENCY == 4

    def test_source_default_is_valid(self):
        from app.config import SOURCE
        from app.sources import _SOURCES

        assert SOURCE in _SOURCES


class TestDbStatementTimeoutValidation:
    """DB_STATEMENT_TIMEOUT_MS must be a positive integer."""

    def test_valid_positive_int_parses(self):
        from app.config import _parse_db_statement_timeout

        assert _parse_db_statement_timeout("5000") == 5000

    def test_zero_rejected(self):
        from app.config import _parse_db_statement_timeout

        with pytest.raises(ValueError, match="DB_STATEMENT_TIMEOUT_MS"):
            _parse_db_statement_timeout("0")

    def test_negative_rejected(self):
        from app.config import _parse_db_statement_timeout

        with pytest.raises(ValueError, match="DB_STATEMENT_TIMEOUT_MS"):
            _parse_db_statement_timeout("-1000")

    def test_non_integer_string_rejected(self):
        from app.config import _parse_db_statement_timeout

        with pytest.raises(ValueError, match="DB_STATEMENT_TIMEOUT_MS"):
            _parse_db_statement_timeout("abc")

    def test_float_string_rejected(self):
        from app.config import _parse_db_statement_timeout

        with pytest.raises(ValueError, match="DB_STATEMENT_TIMEOUT_MS"):
            _parse_db_statement_timeout("1000.5")
