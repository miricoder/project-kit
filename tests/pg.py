"""A throwaway Postgres for the tests.

Uses DUMPIT_TEST_DATABASE_URL when it is set (CI, or your own server). Otherwise it starts a
private cluster from the local Postgres binaries in a temporary directory, on a free port,
and removes it afterwards. Running as root, the cluster runs as the `postgres` user, since
Postgres refuses to run as root.
"""
from __future__ import annotations

import glob
import os
import pwd
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from typing import Callable, Optional, Tuple


def _bin(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    candidates = sorted(glob.glob(f"/usr/lib/postgresql/*/bin/{name}")) + \
        sorted(glob.glob(f"/usr/local/opt/postgresql*/bin/{name}")) + \
        sorted(glob.glob(f"/opt/homebrew/opt/postgresql*/bin/{name}"))
    return candidates[-1] if candidates else None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start() -> Tuple[str, Callable[[], None]]:
    """(admin database URL, stop function)."""
    url = os.environ.get("DUMPIT_TEST_DATABASE_URL")
    if url:
        return url, lambda: None
    initdb, pg_ctl = _bin("initdb"), _bin("pg_ctl")
    if not initdb or not pg_ctl:
        raise RuntimeError("no Postgres for the tests: install Postgres (initdb, pg_ctl) or set "
                           "DUMPIT_TEST_DATABASE_URL to a server you can create databases on")
    base = tempfile.mkdtemp(prefix="dumpit-pg-")
    data = os.path.join(base, "data")
    run_as = None
    if os.geteuid() == 0:
        run_as = "postgres"
        info = pwd.getpwnam(run_as)
        os.chmod(base, 0o755)
        os.makedirs(data)
        os.chown(data, info.pw_uid, info.pw_gid)

    def call(args):
        if run_as:
            args = ["runuser", "-u", run_as, "--"] + args
        return subprocess.run(args, capture_output=True, text=True, timeout=120)

    port = _free_port()
    result = call([initdb, "-D", data, "-U", "postgres", "-A", "trust", "--no-sync"])
    if result.returncode:
        raise RuntimeError(f"initdb failed: {result.stderr[-500:]}")
    result = call([pg_ctl, "-D", data, "-w", "-l", os.path.join(data, "server.log"),
                   "-o", f"-p {port} -k {data} -c listen_addresses=127.0.0.1 -c fsync=off",
                   "start"])
    if result.returncode:
        raise RuntimeError(f"Postgres did not start: {result.stderr[-500:]}")

    def stop():
        call([pg_ctl, "-D", data, "-m", "immediate", "stop"])
        shutil.rmtree(base, ignore_errors=True)

    return f"postgresql://postgres@127.0.0.1:{port}/postgres", stop


def fresh_database(admin_url: str) -> str:
    """A new empty database on the server; returns its URL."""
    import psycopg

    name = "t_" + uuid.uuid4().hex[:12]
    for _ in range(50):
        try:
            with psycopg.connect(admin_url, autocommit=True) as conn:
                conn.execute(f"CREATE DATABASE {name}")
            break
        except psycopg.OperationalError:
            time.sleep(0.1)
    return admin_url.rsplit("/", 1)[0] + "/" + name
