"""Shared fixtures: one throwaway Postgres server per test run, a fresh database per test."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import pg  # noqa: E402


@pytest.fixture(scope="session")
def pg_admin_url():
    url, stop = pg.start()
    yield url
    stop()


@pytest.fixture
def database_url(pg_admin_url):
    return pg.fresh_database(pg_admin_url)
