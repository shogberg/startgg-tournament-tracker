#!/usr/bin/env python3
"""
Secret Labs Stats — Flask API
Serves player stats and head-to-head data from the start.gg MySQL database.

Usage:
    python stats_api.py

Environment variables (same as startgg_scraper.py):
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    PORT  (default 5000)

Nginx proxy snippet:
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
    }
"""

import os
import sys

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError:
    sys.exit("Missing dependency: pip install flask")

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    sys.exit("Missing dependency: pip install pymysql")

app = Flask(__name__, static_folder=".")

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

def get_db():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "startgg"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(".", "stats.html")


@app.route("/api/players")
def players():
    """Return all players sorted by gamertag."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, gamertag, display_name FROM players ORDER BY gamertag"
            )
            return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.route("/api/player/<player_id>/stats")
def player_stats(player_id):
    """
    Return stats for a single player:
      - best_placement
      - top8 list
      - match win/loss counts
      - set win/loss counts
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:

            # Total points
            cur.execute(
                "SELECT points FROM players WHERE player_id = %s",
                (player_id,),
            )
            player_row = cur.fetchone()

            # Best ever placement
            cur.execute(
                "SELECT MIN(placement) AS best FROM standings WHERE player_id = %s",
                (player_id,),
            )
            best_row = cur.fetchone()

            # All top-8 appearances
            cur.execute(
                """
                SELECT s.placement, t.title, t.uuid AS tournament_uuid, t.slug,
                       e.name AS event_name
                FROM   standings s
                JOIN   events      e ON e.id        = s.event_id
                JOIN   tournaments t ON t.uuid      = s.tournament_uuid
                WHERE  s.player_id = %s AND s.placement <= 8
                ORDER  BY s.placement, t.title
                """,
                (player_id,),
            )
            top8 = cur.fetchall()

            # Match win % = games won by this player (their score across all matches)
            #               divided by total games played (all scores from both sides).
            # e.g. 3-1, 3-2, 1-3 → wins=7, losses=6, total=13
            cur.execute(
                """
                SELECT
                    -- Player's own score in every match (games they won)
                    COALESCE(SUM(CASE WHEN winner_player_id = %s THEN winner_player_score ELSE 0 END), 0)
                  + COALESCE(SUM(CASE WHEN loser_player_id  = %s THEN loser_player_score  ELSE 0 END), 0) AS wins,
                    -- Opponent's score in every match (games the player lost)
                    COALESCE(SUM(CASE WHEN winner_player_id = %s THEN loser_player_score  ELSE 0 END), 0)
                  + COALESCE(SUM(CASE WHEN loser_player_id  = %s THEN winner_player_score ELSE 0 END), 0) AS losses
                FROM   matches
                WHERE  (winner_player_id = %s OR loser_player_id = %s)
                  AND  winner_player_score IS NOT NULL
                  AND  loser_player_score  IS NOT NULL
                """,
                (player_id, player_id, player_id, player_id, player_id, player_id),
            )
            match_row = cur.fetchone()

            # Set win % = matches won / total matches played
            cur.execute(
                """
                SELECT
                    SUM(winner_player_id = %s) AS wins,
                    SUM(loser_player_id  = %s) AS losses
                FROM  matches
                WHERE winner_player_id = %s OR loser_player_id = %s
                """,
                (player_id, player_id, player_id, player_id),
            )
            set_row = cur.fetchone()

            # Top 6 match win % — same game-score ratio but only in top-6 rounds
            TOP6_ROUNDS = (
                "Winners Semi-Final",
                "Winners Final",
                "Grand Final",
                "Grand Final Reset",
                "Losers Quarter-Final",
                "Losers Semi-Final",
                "Losers Final",
            )
            placeholders = ", ".join(["%s"] * len(TOP6_ROUNDS))
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN winner_player_id = %s THEN winner_player_score ELSE 0 END), 0)
                  + COALESCE(SUM(CASE WHEN loser_player_id  = %s THEN loser_player_score  ELSE 0 END), 0) AS wins,
                    COALESCE(SUM(CASE WHEN winner_player_id = %s THEN loser_player_score  ELSE 0 END), 0)
                  + COALESCE(SUM(CASE WHEN loser_player_id  = %s THEN winner_player_score ELSE 0 END), 0) AS losses
                FROM   matches
                WHERE  (winner_player_id = %s OR loser_player_id = %s)
                  AND  winner_player_score IS NOT NULL
                  AND  loser_player_score  IS NOT NULL
                  AND  round_name IN ({placeholders})
                """,
                (player_id, player_id, player_id, player_id, player_id, player_id, *TOP6_ROUNDS),
            )
            top6_row = cur.fetchone()

            # Top 6 set win % — match win/loss ratio restricted to the same seven rounds
            cur.execute(
                f"""
                SELECT
                    SUM(winner_player_id = %s) AS wins,
                    SUM(loser_player_id  = %s) AS losses
                FROM  matches
                WHERE (winner_player_id = %s OR loser_player_id = %s)
                  AND  round_name IN ({placeholders})
                """,
                (player_id, player_id, player_id, player_id, *TOP6_ROUNDS),
            )
            top6_set_row = cur.fetchone()

        return jsonify(
            {
                "points":         int(player_row["points"] or 0) if player_row else 0,
                "best_placement": best_row["best"],
                "top8": top8,
                "match_wins":   int(match_row["wins"]   or 0),
                "match_losses": int(match_row["losses"] or 0),
                "set_wins":     int(set_row["wins"]     or 0),
                "set_losses":   int(set_row["losses"]   or 0),
                "top6_wins":        int(top6_row["wins"]        or 0),
                "top6_losses":      int(top6_row["losses"]      or 0),
                "top6_set_wins":    int(top6_set_row["wins"]    or 0),
                "top6_set_losses":  int(top6_set_row["losses"]  or 0),
            }
        )
    finally:
        conn.close()


@app.route("/api/leaderboard")
def leaderboard():
    """Return the top 25 players by points."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT player_id, gamertag, display_name, points
                FROM   players
                WHERE  points > 0
                ORDER  BY points DESC
                LIMIT  25
                """
            )
            return jsonify(cur.fetchall())
    finally:
        conn.close()


GIANTS = ("300a2d8c", "36513805", "4d08742f")

@app.route("/api/giant-slayers")
def giant_slayers():
    """Return all matches where a giant was beaten by a non-giant."""
    conn = get_db()
    try:
        ph = ", ".join(["%s"] * len(GIANTS))
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT m.match_id,
                       m.round_name,
                       m.identifier,
                       m.display_score,
                       m.tournament_uuid,
                       m.winner_player_id,
                       m.winner_player_score,
                       m.loser_player_id,
                       m.loser_player_score,
                       t.title  AS tournament_title,
                       t.slug   AS tournament_slug,
                       pw.gamertag AS winner_gamertag,
                       pl.gamertag AS loser_gamertag
                FROM   matches     m
                JOIN   tournaments t  ON t.uuid      = m.tournament_uuid
                JOIN   players     pw ON pw.player_id = m.winner_player_id
                JOIN   players     pl ON pl.player_id = m.loser_player_id
                WHERE  m.loser_player_id   IN ({ph})
                  AND  m.winner_player_id  NOT IN ({ph})
                ORDER  BY t.title, m.round_name
                """,
                (*GIANTS, *GIANTS),
            )
            rows = cur.fetchall()

        # Group by tournament
        seen = {}
        groups = []
        for r in rows:
            uuid = r["tournament_uuid"]
            if uuid not in seen:
                seen[uuid] = {
                    "tournament_uuid":  uuid,
                    "tournament_title": r["tournament_title"],
                    "tournament_slug":  r["tournament_slug"],
                    "matches": [],
                }
                groups.append(seen[uuid])
            seen[uuid]["matches"].append(r)

        return jsonify(groups)
    finally:
        conn.close()


@app.route("/api/h2h")
def h2h():
    """
    Return all matches between two players, grouped by tournament.
    Query params: player1=<id>, player2=<id>
    """
    p1 = request.args.get("player1")
    p2 = request.args.get("player2")
    if not p1 or not p2:
        return jsonify({"error": "Both player1 and player2 are required"}), 400
    if p1 == p2:
        return jsonify({"error": "player1 and player2 must be different"}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.match_id,
                       m.round_name,
                       m.identifier,
                       m.display_score,
                       m.tournament_uuid,
                       m.winner_player_id,
                       t.title AS tournament_title,
                       t.slug  AS tournament_slug,
                       CASE WHEN m.winner_player_id = %s
                            THEN m.winner_player_score
                            ELSE m.loser_player_score END AS p1_score,
                       CASE WHEN m.winner_player_id = %s
                            THEN m.winner_player_score
                            ELSE m.loser_player_score END AS p2_score
                FROM   matches     m
                JOIN   tournaments t ON t.uuid = m.tournament_uuid
                WHERE  (m.winner_player_id = %s AND m.loser_player_id = %s)
                    OR (m.winner_player_id = %s AND m.loser_player_id = %s)
                ORDER  BY t.title, m.round_name
                """,
                (p1, p2, p1, p2, p2, p1),
            )
            rows = cur.fetchall()

        # Derive per-player flags from winner_player_id
        for r in rows:
            r["p1_match_win"] = r["winner_player_id"] == p1
            r["p2_match_win"] = r["winner_player_id"] == p2

        # Group by tournament
        seen = {}
        groups = []
        for r in rows:
            uuid = r["tournament_uuid"]
            if uuid not in seen:
                seen[uuid] = {
                    "tournament_uuid":  uuid,
                    "tournament_title": r["tournament_title"],
                    "tournament_slug":  r["tournament_slug"],
                    "matches": [],
                }
                groups.append(seen[uuid])
            seen[uuid]["matches"].append(r)

        return jsonify(groups)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Secret Labs Stats API on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
