"""Shared PostgreSQL engine helper: builds connect_args with timeout and TLS."""
from __future__ import annotations

VALID_SSLMODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}


def _parse_sslmode(raw: str | None) -> str | None:
    """Return sslmode value or None if unset; raise ValueError for unknown values."""
    if raw is None:
        return None
    if raw not in VALID_SSLMODES:
        raise ValueError(f"Unknown sslmode {raw!r}; must be one of {sorted(VALID_SSLMODES)}")
    return raw


def _build_connect_args(
    timeout_ms: int,
    sslmode: str | None = None,
    sslrootcert: str | None = None,
) -> dict:
    """
    Build psycopg2/libpq connect_args dict.

    Always includes connect_timeout=5 and options with statement_timeout.
    Adds sslmode / sslrootcert when sslmode is set.
    Validates sslmode against VALID_SSLMODES if provided.
    """
    # Validate sslmode here so calling _build_connect_args directly still catches bad values.
    _parse_sslmode(sslmode)
    args: dict = {
        "connect_timeout": 5,
        "options": f"-c statement_timeout={timeout_ms}",
    }
    if sslmode is not None:
        args["sslmode"] = sslmode
        if sslrootcert is not None:
            args["sslrootcert"] = sslrootcert
    return args
