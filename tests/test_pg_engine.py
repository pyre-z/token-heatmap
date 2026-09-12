"""Engine connect_args injection tests — timeout and TLS (TDD)."""
import os
from unittest.mock import MagicMock, patch

import pytest


class TestNewApiEngineConnectArgs:
    """newapi._get_engine() passes statement_timeout and TLS options via connect_args."""

    def _make_fake_engine(self):
        fake_engine = MagicMock(name="fake_engine")
        return fake_engine

    def _capture_connect_args(self, url, **kwargs):
        self._captured_url = url
        self._captured_connect_args = kwargs.get("connect_args", {})
        return self._make_fake_engine()

    def _reset(self):
        self._captured_url = None
        self._captured_connect_args = None

    @pytest.fixture(autouse=True)
    def setup(self):
        self._reset()
        # Reset the module-level engine cache before and after each test
        import app.sources.newapi as newapi

        newapi._engine = None
        yield
        newapi._engine = None

    def test_default_timeout_and_no_tls(self):
        """Without TLS env vars, connect_args has statement_timeout but no ssl keys."""
        import app.sources.newapi as newapi

        env = {
            "PGUSER": "u",
            "PGPASSWORD": "p",
            "PGHOST": "h",
            "PGDATABASE": "d",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(newapi, "create_engine", self._capture_connect_args):
                newapi._get_engine()
                assert "connect_timeout" in self._captured_connect_args
                assert self._captured_connect_args["connect_timeout"] == 5
                assert "options" in self._captured_connect_args
                assert "statement_timeout" in self._captured_connect_args["options"]
                # No TLS keys when env vars are absent
                assert "sslmode" not in self._captured_connect_args
                assert "sslrootcert" not in self._captured_connect_args

    def test_sslmode_require_produces_sslmode_key(self):
        """PGSSLMODE=require adds sslmode=require to connect_args."""
        import app.sources.newapi as newapi

        env = {
            "PGUSER": "u",
            "PGPASSWORD": "p",
            "PGHOST": "h",
            "PGDATABASE": "d",
            "PGSSLMODE": "require",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(newapi, "create_engine", self._capture_connect_args):
                newapi._get_engine()
                assert self._captured_connect_args.get("sslmode") == "require"
                assert "sslrootcert" not in self._captured_connect_args

    def test_sslmode_verify_full_with_rootcert(self):
        """PGSSLMODE=verify-full + PGSSLROOTCERT adds both ssl keys."""
        import app.sources.newapi as newapi

        env = {
            "PGUSER": "u",
            "PGPASSWORD": "p",
            "PGHOST": "h",
            "PGDATABASE": "d",
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": "/path/to/ca.crt",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(newapi, "create_engine", self._capture_connect_args):
                newapi._get_engine()
                assert self._captured_connect_args.get("sslmode") == "verify-full"
                assert self._captured_connect_args.get("sslrootcert") == "/path/to/ca.crt"

    def test_unknown_sslmode_raises_valueerror(self):
        """PGSSLMODE=invalid raises ValueError naming the bad value."""
        import app.sources.newapi as newapi

        env = {
            "PGUSER": "u",
            "PGPASSWORD": "p",
            "PGHOST": "h",
            "PGDATABASE": "d",
            "PGSSLMODE": "invalid-mode",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="sslmode"):
                newapi._get_engine()


class TestSub2ApiEngineConnectArgs:
    """sub2api_db._get_engine() passes statement_timeout and TLS via connect_args."""

    def _make_fake_engine(self):
        fake_engine = MagicMock(name="fake_engine")
        return fake_engine

    def _capture_connect_args(self, url, **kwargs):
        self._captured_url = url
        self._captured_connect_args = kwargs.get("connect_args", {})
        return self._make_fake_engine()

    def _reset(self):
        self._captured_url = None
        self._captured_connect_args = None

    @pytest.fixture(autouse=True)
    def setup(self):
        self._reset()
        import app.sources.sub2api_db as sub2api_db

        sub2api_db._engine = None
        yield
        sub2api_db._engine = None

    def test_default_timeout_and_no_tls(self):
        """Without TLS env vars, connect_args has statement_timeout but no ssl keys."""
        import app.sources.sub2api_db as sub2api_db

        env = {
            "SUB2API_PGUSER": "u",
            "SUB2API_PGPASSWORD": "p",
            "SUB2API_PGHOST": "h",
            "SUB2API_PGDATABASE": "d",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(sub2api_db, "create_engine", self._capture_connect_args):
                sub2api_db._get_engine()
                assert "connect_timeout" in self._captured_connect_args
                assert self._captured_connect_args["connect_timeout"] == 5
                assert "options" in self._captured_connect_args
                assert "statement_timeout" in self._captured_connect_args["options"]
                assert "sslmode" not in self._captured_connect_args
                assert "sslrootcert" not in self._captured_connect_args

    def test_sslmode_prefer_produces_sslmode_key(self):
        """SUB2API_PGSSLMODE=prefer adds sslmode=prefer to connect_args."""
        import app.sources.sub2api_db as sub2api_db

        env = {
            "SUB2API_PGUSER": "u",
            "SUB2API_PGPASSWORD": "p",
            "SUB2API_PGHOST": "h",
            "SUB2API_PGDATABASE": "d",
            "SUB2API_PGSSLMODE": "prefer",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(sub2api_db, "create_engine", self._capture_connect_args):
                sub2api_db._get_engine()
                assert self._captured_connect_args.get("sslmode") == "prefer"

    def test_sslmode_verify_ca_with_rootcert(self):
        """SUB2API_PGSSLMODE=verify-ca + SUB2API_PGSSLROOTCERT adds both ssl keys."""
        import app.sources.sub2api_db as sub2api_db

        env = {
            "SUB2API_PGUSER": "u",
            "SUB2API_PGPASSWORD": "p",
            "SUB2API_PGHOST": "h",
            "SUB2API_PGDATABASE": "d",
            "SUB2API_PGSSLMODE": "verify-ca",
            "SUB2API_PGSSLROOTCERT": "/path/to/sub2api-ca.crt",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(sub2api_db, "create_engine", self._capture_connect_args):
                sub2api_db._get_engine()
                assert self._captured_connect_args.get("sslmode") == "verify-ca"
                assert self._captured_connect_args.get("sslrootcert") == "/path/to/sub2api-ca.crt"

    def test_unknown_sslmode_raises_valueerror(self):
        """SUB2API_PGSSLMODE=bad raises ValueError naming the bad value."""
        import app.sources.sub2api_db as sub2api_db

        env = {
            "SUB2API_PGUSER": "u",
            "SUB2API_PGPASSWORD": "p",
            "SUB2API_PGHOST": "h",
            "SUB2API_PGDATABASE": "d",
            "SUB2API_PGSSLMODE": "bad",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="sslmode"):
                sub2api_db._get_engine()


class TestPgHelperBuildConnectArgs:
    """Unit tests for the shared pg helper building connect_args dict."""

    def test_timeout_in_options(self):
        """_build_connect_args produces options string with statement_timeout."""
        from app.sources.pg import _build_connect_args

        args = _build_connect_args(timeout_ms=5000)
        assert args["connect_timeout"] == 5
        assert args["options"] == "-c statement_timeout=5000"

    def test_custom_timeout(self):
        """Custom DB_STATEMENT_TIMEOUT_MS is reflected in options string."""
        from app.sources.pg import _build_connect_args

        args = _build_connect_args(timeout_ms=10000)
        assert args["connect_timeout"] == 5
        assert "statement_timeout=10000" in args["options"]

    def test_sslmode_disable_produces_sslmode(self):
        """sslmode=disable is passed through."""
        from app.sources.pg import _build_connect_args

        args = _build_connect_args(timeout_ms=5000, sslmode="disable")
        assert args["sslmode"] == "disable"

    def test_sslmode_require_produces_sslmode(self):
        """sslmode=require is passed through."""
        from app.sources.pg import _build_connect_args

        args = _build_connect_args(timeout_ms=5000, sslmode="require")
        assert args["sslmode"] == "require"

    def test_sslmode_with_sslrootcert(self):
        """Both sslmode and sslrootcert appear when sslrootcert is set."""
        from app.sources.pg import _build_connect_args

        args = _build_connect_args(timeout_ms=5000, sslmode="verify-full", sslrootcert="/path/ca.crt")
        assert args["sslmode"] == "verify-full"
        assert args["sslrootcert"] == "/path/ca.crt"

    def test_unknown_sslmode_raises_valueerror(self):
        """An unknown sslmode raises ValueError naming the bad value."""
        from app.sources.pg import _build_connect_args

        with pytest.raises(ValueError, match="sslmode"):
            _build_connect_args(timeout_ms=5000, sslmode="not-valid")
