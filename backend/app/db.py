from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from .settings import DATABASE_PATH
from .security import hash_password


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DATABASE_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                plan TEXT NOT NULL DEFAULT 'trial',
                plan_expires_at INTEGER NOT NULL DEFAULT 0,
                disabled INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT NOT NULL,
                public_endpoint TEXT NOT NULL,
                wg_port INTEGER NOT NULL,
                wg_public_key TEXT NOT NULL,
                vpn_prefix TEXT NOT NULL,
                mtu INTEGER NOT NULL DEFAULT 1280,
                agent_url TEXT NOT NULL,
                agent_secret TEXT NOT NULL,
                health_url TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 500,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_health_json TEXT,
                last_health_at INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leases (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                game_id TEXT NOT NULL,
                client_public_key TEXT NOT NULL,
                client_vpn_ip TEXT NOT NULL,
                allowed_ips_json TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                stopped_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS latency_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                rtt_ms REAL,
                loss_percent REAL,
                jitter_ms REAL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS route_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                game_id TEXT NOT NULL,
                requested_mode TEXT NOT NULL,
                resolved_mode TEXT NOT NULL,
                selected_node_id TEXT REFERENCES nodes(id) ON DELETE SET NULL,
                selected_score REAL,
                measurements_json TEXT NOT NULL,
                direct_measurement_json TEXT NOT NULL DEFAULT '{}',
                agent_measurements_json TEXT NOT NULL DEFAULT '{}',
                targets_json TEXT NOT NULL,
                decision_reason TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS node_probe_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                targets_json TEXT NOT NULL,
                samples INTEGER NOT NULL,
                created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                started_at INTEGER NOT NULL,
                finished_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS node_probe_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES node_probe_runs(id) ON DELETE CASCADE,
                node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                ok INTEGER NOT NULL,
                summary_json TEXT NOT NULL,
                error TEXT,
                rtt_ms REAL,
                loss_percent REAL,
                jitter_ms REAL,
                target_count INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_node_probe_results_game_node_time
            ON node_probe_results(node_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_node_probe_runs_game_time
            ON node_probe_runs(game_id, started_at);
            """
        )
        ensure_column(con, "route_metrics", "direct_measurement_json", "TEXT NOT NULL DEFAULT '{}'")
        ensure_column(con, "route_metrics", "agent_measurements_json", "TEXT NOT NULL DEFAULT '{}'")


def ensure_column(con: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_demo() -> None:
    now = int(time.time())
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?", ("demo@example.com",)).fetchone() is None:
            con.execute(
                "INSERT INTO users(email,password_hash,role,plan,plan_expires_at,created_at) VALUES(?,?,?,?,?,?)",
                ("demo@example.com", hash_password("demo123456"), "user", "trial", now + 60 * 60 * 24 * 30, now),
            )
        if con.execute("SELECT 1 FROM users WHERE email=?", ("admin@example.com",)).fetchone() is None:
            con.execute(
                "INSERT INTO users(email,password_hash,role,plan,plan_expires_at,created_at) VALUES(?,?,?,?,?,?)",
                ("admin@example.com", hash_password("change-this-admin-password"), "admin", "internal", now + 60 * 60 * 24 * 365, now),
            )
