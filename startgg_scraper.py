#!/usr/bin/env python3
"""
start.gg Tournament Results Scraper
Pulls bracket matches and top-8 standings via the start.gg GraphQL API.

Usage:
    python startgg_scraper.py <bracket_url> [options]

Example:
    python startgg_scraper.py \
        "https://www.start.gg/tournament/secret-labs-az-april-2026/events/sf6-singles/brackets/2227887/3232842/matches" \
        --token YOUR_API_TOKEN \
        --host localhost --user root --password secret --database startgg

Get your API token at: https://start.gg/admin/profile/developer
You can also set environment variables instead of flags:
    STARTGG_TOKEN, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

import re
import json
import uuid
import argparse
import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    sys.exit("Missing dependency: pip install pymysql")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

START_GG_API = "https://api.start.gg/gql/alpha"

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

TOURNAMENT_QUERY = """
query TournamentInfo($tournamentSlug: String!) {
  tournament(slug: $tournamentSlug) {
    id
    name
    slug
  }
}
"""

EVENT_QUERY = """
query EventInfo($eventSlug: String!) {
  event(slug: $eventSlug) {
    id
    name
    slug
  }
}
"""

PHASE_GROUP_SETS_QUERY = """
query PhaseGroupSets($phaseGroupId: ID!, $page: Int!) {
  phaseGroup(id: $phaseGroupId) {
    id
    displayIdentifier
    sets(perPage: 20, page: $page, sortType: MAGIC) {
      pageInfo {
        total
        totalPages
      }
      nodes {
        id
        identifier
        fullRoundText
        winnerId
        displayScore
        slots {
          entrant {
            id
            name
            participants {
              player {
                id
                gamerTag
              }
              user {
                id
                discriminator
              }
            }
          }
          standing {
            stats {
              score {
                value
              }
            }
          }
        }
      }
    }
  }
}
"""

STANDINGS_QUERY = """
query EventStandings($eventId: ID!, $page: Int!) {
  event(id: $eventId) {
    standings(query: { perPage: 50, page: $page }) {
      pageInfo {
        total
        totalPages
      }
      nodes {
        placement
        entrant {
          id
          name
          participants {
            player {
              id
              gamerTag
            }
            user {
              id
              discriminator
            }
          }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def gql_query(token: str, query: str, variables: dict) -> dict:
    """Execute a GraphQL query against the start.gg API."""
    resp = requests.post(
        START_GG_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors:\n{json.dumps(data['errors'], indent=2)}")
    return data["data"]


def parse_bracket_url(url: str) -> dict:
    """
    Extract tournament slug, event slug, phase ID, and phase group ID from a
    start.gg bracket URL such as:
      https://www.start.gg/tournament/<slug>/events/<event>/brackets/<phaseId>/<pgId>/matches
    """
    url = url.strip().strip('"').strip("'")
    pattern = r"start\.gg/tournament/([^/]+)/events?/([^/]+)/brackets/(\d+)/(\d+)"
    m = re.search(pattern, url)
    if not m:
        raise ValueError(
            f"Could not parse start.gg bracket URL.\n"
            f"  Received : {repr(url)}\n"
            f"  Expected : https://www.start.gg/tournament/<slug>/events/<event>/brackets/<phaseId>/<pgId>/..."
        )
    return {
        "tournament_slug": m.group(1),
        "event_slug": m.group(2),
        "phase_id": int(m.group(3)),
        "phase_group_id": int(m.group(4)),
    }


def get_player_id(participant: dict) -> str:
    """
    Return the best available player identifier.
    Prefers discriminator (hex slug from user profile URL, e.g. '4d08742f'),
    falls back to the numeric player ID as a string.
    """
    user = participant.get("user") or {}
    disc = user.get("discriminator")
    if disc:
        return disc
    return str(participant["player"]["id"])


PLACEMENT_POINTS = {1: 10, 2: 8, 3: 7, 4: 6, 5: 5, 6: 5, 7: 4, 8: 4}

def placement_to_points(placement: int) -> int:
    return PLACEMENT_POINTS.get(placement, 1)


def extract_players(entrant: dict) -> list:
    """Return a list of player dicts from an entrant (handles teams too)."""
    players = []
    for p in entrant.get("participants") or []:
        players.append(
            {
                "player_id": get_player_id(p),
                "gamertag": p["player"]["gamerTag"],
                "display_name": entrant["name"],
            }
        )
    return players


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS tournaments (
        uuid        VARCHAR(36)  NOT NULL PRIMARY KEY,
        start_gg_id BIGINT,
        title       VARCHAR(255),
        slug        VARCHAR(255) UNIQUE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id              BIGINT       NOT NULL PRIMARY KEY,
        tournament_uuid VARCHAR(36)  NOT NULL,
        name            VARCHAR(255),
        slug            VARCHAR(255),
        FOREIGN KEY (tournament_uuid) REFERENCES tournaments(uuid)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS players (
        player_id    VARCHAR(64)  NOT NULL PRIMARY KEY,
        gamertag     VARCHAR(255),
        display_name VARCHAR(255),
        points       INT          NOT NULL DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS matches (
        match_id              VARCHAR(64)  NOT NULL UNIQUE,
        identifier            VARCHAR(16),
        tournament_uuid       VARCHAR(36)  NOT NULL,
        event_id              BIGINT       NOT NULL,
        phase_group_id        BIGINT       NOT NULL,
        round_name            VARCHAR(255),
        winner_player_id      VARCHAR(64),
        winner_player_score   INT,
        loser_player_id       VARCHAR(64),
        loser_player_score    INT,
        display_score         VARCHAR(255),
        FOREIGN KEY (tournament_uuid)  REFERENCES tournaments(uuid),
        FOREIGN KEY (winner_player_id) REFERENCES players(player_id),
        FOREIGN KEY (loser_player_id)  REFERENCES players(player_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS standings (
        id              INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
        tournament_uuid VARCHAR(36) NOT NULL,
        event_id        BIGINT      NOT NULL,
        placement       INT         NOT NULL,
        player_id       VARCHAR(64) NOT NULL,
        display_name    VARCHAR(255),
        points          INT,
        FOREIGN KEY (tournament_uuid) REFERENCES tournaments(uuid),
        FOREIGN KEY (player_id)       REFERENCES players(player_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def init_db(host: str, port: int, user: str, password: str, database: str):
    """Connect to MySQL, create the database if needed, apply schema, return connection."""
    # Connect without selecting a database first so we can CREATE it
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        charset="utf8mb4",
        autocommit=False,
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE `{database}`")
    conn.commit()

    # Reconnect with the database selected (simplifies subsequent queries)
    conn.close()
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )

    with conn.cursor() as cur:
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
    conn.commit()
    return conn


def db_fetchone(conn, sql: str, params: tuple = ()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def db_execute(conn, sql: str, params: tuple = ()):
    with conn.cursor() as cur:
        cur.execute(sql, params)


def upsert_player(conn, player_id: str, gamertag: str, display_name: str):
    db_execute(
        conn,
        """
        INSERT INTO players (player_id, gamertag, display_name)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            gamertag     = VALUES(gamertag),
            display_name = VALUES(display_name)
        """,
        (player_id, gamertag, display_name),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pull bracket results and top-8 standings from start.gg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="start.gg bracket URL (matches or standings page)")
    parser.add_argument(
        "--token",
        default=os.environ.get("STARTGG_TOKEN"),
        help="start.gg API token (or set STARTGG_TOKEN env var)",
    )
    # MySQL connection args
    parser.add_argument("--host",     default=os.environ.get("DB_HOST", "localhost"))
    parser.add_argument("--port",     default=int(os.environ.get("DB_PORT", 3306)), type=int)
    parser.add_argument("--user",     default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("DB_PASSWORD", ""))
    parser.add_argument("--database", default=os.environ.get("DB_NAME", "startgg"))
    parser.add_argument(
        "--json",
        default=None,
        metavar="PATH",
        help="Also export results as JSON to this path",
    )
    args = parser.parse_args()

    if not args.token:
        print(
            "ERROR: API token required.\n"
            "  Use --token YOUR_TOKEN  or  export STARTGG_TOKEN=YOUR_TOKEN\n"
            "  Generate a token at https://start.gg/admin/profile/developer"
        )
        sys.exit(1)

    # ---- Parse URL ----------------------------------------------------------
    print("Parsing URL …")
    parts = parse_bracket_url(args.url)
    print(f"  Tournament : {parts['tournament_slug']}")
    print(f"  Event      : {parts['event_slug']}")
    print(f"  Phase      : {parts['phase_id']}")
    print(f"  PhaseGroup : {parts['phase_group_id']}")

    # ---- Init DB ------------------------------------------------------------
    print(f"\nConnecting to MySQL at {args.host}:{args.port}/{args.database} …")
    conn = init_db(args.host, args.port, args.user, args.password, args.database)
    print("  Connected and schema ready.")

    # ---- Tournament ---------------------------------------------------------
    print("\nFetching tournament …")
    t_data = gql_query(args.token, TOURNAMENT_QUERY, {"tournamentSlug": parts["tournament_slug"]})
    tournament = t_data["tournament"]

    existing = db_fetchone(conn, "SELECT uuid FROM tournaments WHERE slug = %s", (tournament["slug"],))

    if existing:
        tournament_uuid = existing["uuid"]
        print(f"  Already in DB — uuid: {tournament_uuid}")
    else:
        tournament_uuid = str(uuid.uuid4())
        db_execute(
            conn,
            "INSERT INTO tournaments (uuid, start_gg_id, title, slug) VALUES (%s, %s, %s, %s)",
            (tournament_uuid, tournament["id"], tournament["name"], tournament["slug"]),
        )
        print(f"  {tournament['name']}")
        print(f"  uuid: {tournament_uuid}")

    # ---- Event --------------------------------------------------------------
    print("\nFetching event …")
    combined_event_slug = f"tournament/{parts['tournament_slug']}/event/{parts['event_slug']}"
    e_data = gql_query(args.token, EVENT_QUERY, {"eventSlug": combined_event_slug})
    event = e_data["event"]
    db_execute(
        conn,
        "INSERT IGNORE INTO events (id, tournament_uuid, name, slug) VALUES (%s, %s, %s, %s)",
        (event["id"], tournament_uuid, event["name"], event["slug"]),
    )
    print(f"  {event['name']} (id: {event['id']})")

    # ---- Sets / Matches -----------------------------------------------------
    print("\nFetching matches …")
    all_sets = []
    page = 1
    while True:
        data = gql_query(
            args.token,
            PHASE_GROUP_SETS_QUERY,
            {"phaseGroupId": parts["phase_group_id"], "page": page},
        )
        pg_sets = data["phaseGroup"]["sets"]
        nodes = pg_sets["nodes"]
        total_pages = pg_sets["pageInfo"]["totalPages"]
        total = pg_sets["pageInfo"]["total"]
        all_sets.extend(nodes)
        print(f"  Page {page}/{total_pages} — {len(all_sets)}/{total} sets fetched")
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.5)  # be polite to the API

    matches_out = []
    new_matches = 0
    skipped = 0

    for s in all_sets:
        # Skip incomplete / bye sets
        if not s.get("displayScore") or not s.get("slots"):
            skipped += 1
            continue

        # Skip already-stored matches
        if db_fetchone(conn, "SELECT 1 FROM matches WHERE match_id = %s", (str(s["id"]),)):
            skipped += 1
            continue

        slots = [sl for sl in s["slots"] if sl.get("entrant")]
        if len(slots) < 2:
            skipped += 1
            continue

        entrants = []
        for slot in slots:
            ent = slot["entrant"]
            score_val = None
            try:
                raw = slot["standing"]["stats"]["score"]["value"]
                score_val = int(raw) if raw is not None and raw >= 0 else None
            except (TypeError, KeyError):
                pass
            entrants.append(
                {
                    "entrant_id": ent["id"],
                    "entrant_name": ent["name"],
                    "players": extract_players(ent),
                    "score": score_val,
                }
            )

        # Split into winner and loser entrants
        winner_ent = next((e for e in entrants if e["entrant_id"] == s.get("winnerId")), None)
        loser_ent  = next((e for e in entrants if e["entrant_id"] != s.get("winnerId")), None)

        winner_player_id = winner_ent["players"][0]["player_id"] if winner_ent and winner_ent["players"] else None
        loser_player_id  = loser_ent["players"][0]["player_id"]  if loser_ent  and loser_ent["players"]  else None
        winner_score     = winner_ent["score"] if winner_ent else None
        loser_score      = loser_ent["score"]  if loser_ent  else None

        match_id = str(s["id"])

        # Upsert players
        for ent in entrants:
            for p in ent["players"]:
                upsert_player(conn, p["player_id"], p["gamertag"], p["display_name"])

        # Insert match
        db_execute(
            conn,
            """
            INSERT IGNORE INTO matches
                (match_id, identifier, tournament_uuid, event_id, phase_group_id,
                 round_name, winner_player_id, winner_player_score,
                 loser_player_id, loser_player_score, display_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                match_id,
                s.get("identifier") or "",
                tournament_uuid,
                event["id"],
                parts["phase_group_id"],
                s.get("fullRoundText") or "",
                winner_player_id,
                winner_score,
                loser_player_id,
                loser_score,
                s.get("displayScore") or "",
            ),
        )

        # Build record for JSON export
        matches_out.append(
            {
                "match_id":            match_id,
                "identifier":          s.get("identifier") or "",
                "round_name":          s.get("fullRoundText") or "",
                "display_score":       s.get("displayScore") or "",
                "winner_player_id":    winner_player_id,
                "winner_player_score": winner_score,
                "loser_player_id":     loser_player_id,
                "loser_player_score":  loser_score,
            }
        )
        new_matches += 1

    print(f"  Stored {new_matches} new matches  ({skipped} skipped/existing)")

    # ---- Standings (all placements) -----------------------------------------
    print("\nFetching standings …")
    all_standings = []
    page = 1
    while True:
        s_data = gql_query(args.token, STANDINGS_QUERY, {"eventId": event["id"], "page": page})
        s_page = s_data["event"]["standings"]
        all_standings.extend(s_page["nodes"])
        total_pages = s_page["pageInfo"]["totalPages"]
        total = s_page["pageInfo"]["total"]
        print(f"  Page {page}/{total_pages} — {len(all_standings)}/{total} standings fetched")
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.5)

    # Clear existing standings for this event so re-runs stay clean
    db_execute(
        conn,
        "DELETE FROM standings WHERE tournament_uuid = %s AND event_id = %s",
        (tournament_uuid, event["id"]),
    )

    standings_out = []
    for standing in sorted(all_standings, key=lambda x: x["placement"]):
        placement = standing["placement"]
        points    = placement_to_points(placement)
        ent = standing["entrant"]
        players = extract_players(ent)
        for p in players:
            upsert_player(conn, p["player_id"], p["gamertag"], p["display_name"])
            db_execute(
                conn,
                "INSERT INTO standings (tournament_uuid, event_id, placement, player_id, display_name, points)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (tournament_uuid, event["id"], placement, p["player_id"], ent["name"], points),
            )
        standings_out.append(
            {"placement": placement, "points": points, "display_name": ent["name"], "players": players}
        )
        print(f"  #{placement:2d}  {ent['name']}  ({points} pts)")

    conn.commit()

    # ---- JSON export --------------------------------------------------------
    if args.json:
        output = {
            "tournament": {
                "uuid": tournament_uuid,
                "title": tournament["name"],
                "slug": tournament["slug"],
                "event": event["name"],
            },
            "matches": matches_out,
            "standings": standings_out,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nJSON exported → {args.json}")

    # ---- Recalculate player points ------------------------------------------
    print("\nRecalculating player points …")
    db_execute(
        conn,
        """
        UPDATE players p
        JOIN (
            SELECT player_id, COALESCE(SUM(points), 0) AS total
            FROM   standings
            GROUP  BY player_id
        ) s ON s.player_id = p.player_id
        SET p.points = s.total
        """,
    )
    conn.commit()
    print("  Done.")

    conn.close()
    print(f"\n✓ Done!")
    print(f"  Tournament UUID : {tournament_uuid}")
    print(f"  Matches stored  : {new_matches}")
    print(f"  Standings stored: {len(standings_out)}")


if __name__ == "__main__":
    main()
