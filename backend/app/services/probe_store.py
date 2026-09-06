from __future__ import annotations

import json
import time
from sqlite3 import Connection
from typing import Any


def create_probe_run(con: Connection, game_id: str, targets: list[dict[str, Any]], samples: int, created_by: int) -> int:
    cur = con.execute(
        """
        INSERT INTO node_probe_runs(game_id,targets_json,samples,created_by,started_at)
        VALUES(?,?,?,?,?)
        """,
        (game_id, json.dumps(targets, ensure_ascii=False), samples, created_by, int(time.time())),
    )
    return int(cur.lastrowid)


def finish_probe_run(con: Connection, run_id: int) -> None:
    con.execute("UPDATE node_probe_runs SET finished_at=? WHERE id=?", (int(time.time()), run_id))


def save_probe_result(con: Connection, run_id: int, node_id: str, summary: dict[str, Any]) -> None:
    con.execute(
        """
        INSERT INTO node_probe_results(run_id,node_id,ok,summary_json,error,rtt_ms,loss_percent,jitter_ms,target_count,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            node_id,
            1 if summary.get("ok") else 0,
            json.dumps(summary, ensure_ascii=False),
            summary.get("error"),
            summary.get("rtt_ms"),
            summary.get("loss_percent"),
            summary.get("jitter_ms"),
            summary.get("target_count"),
            int(time.time()),
        ),
    )


def latest_probe_measurements(con: Connection, game_id: str, max_age_seconds: int = 900) -> dict[str, dict[str, Any]]:
    min_created_at = int(time.time()) - max_age_seconds
    rows = con.execute(
        """
        SELECT npr.node_id,npr.summary_json,npr.created_at
        FROM node_probe_results npr
        JOIN node_probe_runs runs ON runs.id=npr.run_id
        JOIN (
            SELECT npr2.node_id, MAX(npr2.created_at) AS created_at
            FROM node_probe_results npr2
            JOIN node_probe_runs runs2 ON runs2.id=npr2.run_id
            WHERE runs2.game_id=? AND npr2.created_at>=?
            GROUP BY npr2.node_id
        ) latest ON latest.node_id=npr.node_id AND latest.created_at=npr.created_at
        WHERE runs.game_id=?
        """,
        (game_id, min_created_at, game_id),
    ).fetchall()

    results: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            results[row["node_id"]] = json.loads(row["summary_json"])
        except Exception:
            results[row["node_id"]] = {"ok": False, "error": "bad cached probe data"}
    return results


def latest_probe_rows(con: Connection, game_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = con.execute(
        """
        SELECT runs.id AS run_id,runs.game_id,runs.started_at,runs.finished_at,npr.node_id,npr.ok,npr.summary_json,
               npr.error,npr.rtt_ms,npr.loss_percent,npr.jitter_ms,npr.target_count,npr.created_at
        FROM node_probe_results npr
        JOIN node_probe_runs runs ON runs.id=npr.run_id
        WHERE runs.game_id=?
        ORDER BY npr.created_at DESC, npr.id DESC
        LIMIT ?
        """,
        (game_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def probe_scoreboard(con: Connection, game_id: str, max_age_seconds: int = 3600) -> list[dict[str, Any]]:
    min_created_at = int(time.time()) - max_age_seconds
    rows = con.execute(
        """
        SELECT npr.node_id,nodes.name,nodes.region,nodes.country,nodes.city,
               COUNT(*) AS samples,
               AVG(npr.rtt_ms) AS avg_rtt_ms,
               AVG(npr.loss_percent) AS avg_loss_percent,
               AVG(npr.jitter_ms) AS avg_jitter_ms,
               MAX(npr.created_at) AS last_probe_at
        FROM node_probe_results npr
        JOIN node_probe_runs runs ON runs.id=npr.run_id
        JOIN nodes ON nodes.id=npr.node_id
        WHERE runs.game_id=? AND npr.ok=1 AND npr.created_at>=?
        GROUP BY npr.node_id,nodes.name,nodes.region,nodes.country,nodes.city
        ORDER BY (AVG(npr.rtt_ms) + AVG(npr.loss_percent) * 40 + AVG(npr.jitter_ms) * 1.5) ASC
        """,
        (game_id, min_created_at),
    ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        rtt = float(item.get("avg_rtt_ms") or 999)
        loss = float(item.get("avg_loss_percent") or 100)
        jitter = float(item.get("avg_jitter_ms") or 0)
        item["score"] = round(rtt + loss * 40 + jitter * 1.5, 3)
        result.append(item)
    return result
