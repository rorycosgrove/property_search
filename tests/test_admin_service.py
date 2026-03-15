import subprocess
from types import SimpleNamespace

import pytest

from packages.admin.service import (
    MigrationCommandFailedError,
    MigrationCommandTimedOutError,
    get_migration_status,
    run_database_migrations,
)


class _FakeLogger:
    def __init__(self):
        self.info_calls = []
        self.error_calls = []

    def info(self, event, **kwargs):
        self.info_calls.append((event, kwargs))

    def error(self, event, **kwargs):
        self.error_calls.append((event, kwargs))


def test_run_database_migrations_success():
    logger = _FakeLogger()

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="upgraded\n", stderr="")

    payload = run_database_migrations(logger=logger, executable="python", runner=runner, timeout=5)

    assert payload == {"status": "ok", "output": "upgraded"}
    assert logger.info_calls[0][0] == "migration_success"


def test_run_database_migrations_raises_on_nonzero_exit():
    logger = _FakeLogger()

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    with pytest.raises(MigrationCommandFailedError, match="boom"):
        run_database_migrations(logger=logger, executable="python", runner=runner, timeout=5)

    assert logger.error_calls[0][0] == "migration_failed"


def test_run_database_migrations_raises_on_timeout():
    logger = _FakeLogger()

    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="alembic", timeout=5)

    with pytest.raises(MigrationCommandTimedOutError, match="Migration timed out"):
        run_database_migrations(logger=logger, executable="python", runner=runner, timeout=5)

    assert logger.error_calls[0][0] == "migration_timeout"


def test_get_migration_status_success():
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")

    payload = get_migration_status(executable="python", runner=runner, timeout=5)

    assert payload == {"revision": "abc123"}


def test_get_migration_status_raises_on_nonzero_exit():
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="bad status")

    with pytest.raises(MigrationCommandFailedError, match="bad status"):
        get_migration_status(executable="python", runner=runner, timeout=5)


def test_get_migration_status_raises_on_timeout():
    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="alembic", timeout=5)

    with pytest.raises(MigrationCommandTimedOutError, match="Status check timed out"):
        get_migration_status(executable="python", runner=runner, timeout=5)