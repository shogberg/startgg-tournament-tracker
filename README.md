Half claude slop, half learning python

# Secret Labs Stats — API Reference

The API is served by `stats_api.py` (Flask). All endpoints return JSON.

**Base URL:** `http://localhost:5000` (or whatever host/port is configured)

See [SQL.md](SQL.md) for the underlying queries behind each endpoint.

---

## Configuration

The server is configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | *(empty)* | MySQL password |
| `DB_NAME` | `startgg` | MySQL database name |
| `PORT` | `5000` | Port the Flask server listens on |

---

## General Notes

### Tournament ordering

All endpoints that return results grouped by tournament sort tournaments by `start_at DESC` (most recent first). `start_at` is a Unix timestamp fetched from the start.gg API when a tournament is scraped. Tournaments scraped before this field was added will have `start_at = NULL` and sort to the end.

### Match ordering within a tournament

Matches within a tournament are sorted in bracket order:

1. **Winners side** — sequentially by round number (Round 1, Round 2 … Quarter-Final, Semi-Final, Final)
2. **Losers side** — sequentially by round number (Round 1, Round 2 … Quarter-Final, Semi-Final, Final)
3. **Grand Final**, then **Grand Final Reset**

---

## Endpoints

### `GET /`

Serves `stats.html` — the frontend.

---

### `GET /api/players`

Returns all players sorted alphabetically by gamertag. Used to populate autocomplete dropdowns.

**Response**

```json
[
  {
    "player_id": "4d08742f",
    "gamertag": "BigMacCombo98",
    "display_name": "BigMacCombo98"
  }
]
```

---

### `GET /api/player/<player_id>/stats`

Returns full stats for a single player.

**URL parameter:** `player_id` — the player's discriminator ID (hex string, e.g. `4d08742f`)

**Response**

```json
{
  "points": 42,
  "best_placement": 1,
  "top8": [
    {
      "placement": 1,
      "title": "Secret Labs AZ April 2026",
      "tournament_uuid": "...",
      "slug": "secret-labs-az-april-2026",
      "event_name": "SF6 Singles"
    }
  ],
  "match_wins": 27,
  "match_losses": 8,
  "set_wins": 12,
  "set_losses": 4,
  "top8_wins": 14,
  "top8_losses": 6,
  "top8_set_wins": 7,
  "top8_set_losses": 3
}
```

**Fields**

| Field | Description |
|---|---|
| `points` | Total career points from `players.points` |
| `best_placement` | Lowest (best) placement across all tournaments |
| `top8` | List of all top-8 finishes (placement ≤ 8) |
| `match_wins` | Sum of games won across all matches with recorded scores |
| `match_losses` | Sum of games lost across all matches with recorded scores |
| `set_wins` | Number of matches (sets) won |
| `set_losses` | Number of matches (sets) lost |
| `top8_wins` | Games won in top-8 matches only |
| `top8_losses` | Games lost in top-8 matches only |
| `top8_set_wins` | Matches won in top-8 matches only |
| `top8_set_losses` | Matches lost in top-8 matches only |

**Top-8 matches** are defined as any match where the loser's final placement was 7th or better (placement ≤ 7), meaning the match was contested while 8 or fewer players remained in the tournament.

**Match win %** is calculated as:
> `match_wins / (match_wins + match_losses)`
>
> Where wins = sum of the player's own score across all matches (games they won), and losses = sum of their opponent's score (games they lost). Only matches with recorded scores are included.
>
> Example: 3-1, 3-2, 1-3 → wins = 7, losses = 6, win % = 53.8%

**Set win %** is calculated as:
> `set_wins / (set_wins + set_losses)`
>
> A simple ratio of matches won vs matches played (all matches, including those without recorded scores).

**Top-8 match win %** uses the same game-score formula as Match win %, restricted to top-8 matches only.

**Top-8 set win %** uses the same match-count formula as Set win %, restricted to top-8 matches only.

---

### `GET /api/player/<player_id>/history`

Returns all matches for a single player across every tournament, grouped by tournament (most recent first). Includes each tournament's final placement and per-match W/L details. Used to power the Tournament History tab.

**URL parameter:** `player_id` — the player's discriminator ID (hex string, e.g. `4d08742f`)

**Response**

```json
[
  {
    "tournament_uuid": "...",
    "tournament_title": "Secret Labs AZ April 2026",
    "tournament_slug": "secret-labs-az-april-2026",
    "placement": 3,
    "matches": [
      {
        "match_id": "12345678",
        "round_name": "Winners Semi-Final",
        "identifier": "WF",
        "display_score": "BigMacCombo98 3 - PlayerX 1",
        "opponent_gamertag": "PlayerX",
        "opponent_id": "abcd1234",
        "won": true,
        "player_score": 3,
        "opponent_score": 1
      }
    ]
  }
]
```

**Fields — tournament group**

| Field | Description |
|---|---|
| `tournament_uuid` | Unique tournament identifier |
| `tournament_title` | Display name of the tournament |
| `tournament_slug` | URL slug for linking to start.gg |
| `placement` | Player's final placement in this tournament (`null` if not recorded) |
| `matches` | Matches sorted in bracket order (see Match ordering note above) |

**Fields — match**

| Field | Description |
|---|---|
| `round_name` | Round label (e.g. `Winners Semi-Final`) |
| `identifier` | Short bracket identifier (e.g. `WF`) |
| `display_score` | Raw score string from start.gg |
| `opponent_gamertag` | Gamertag of the opponent |
| `opponent_id` | Player ID of the opponent |
| `won` | `true` if the player won this match |
| `player_score` | Games won by this player in the match |
| `opponent_score` | Games won by the opponent in the match |

---

### `GET /api/top8`

Returns top-8 standings (placements 1–8) for every tournament, grouped by tournament and sorted most recent first. Within each tournament, standings are ordered by placement.

**Response**

```json
[
  {
    "tournament_uuid": "...",
    "tournament_title": "Secret Labs AZ April 2026",
    "tournament_slug": "secret-labs-az-april-2026",
    "event_name": "SF6 Singles",
    "standings": [
      {
        "placement": 1,
        "points": 10,
        "display_name": "BigMacCombo98",
        "gamertag": "BigMacCombo98"
      }
    ]
  }
]
```

---

### `GET /api/leaderboard`

Returns the top 25 players by career points.

**Response**

```json
[
  {
    "player_id": "4d08742f",
    "gamertag": "BigMacCombo98",
    "display_name": "BigMacCombo98",
    "points": 42
  }
]
```

---

### `GET /api/giant-slayers`

Returns all matches where one of the designated "giant" players lost to a non-giant, grouped by tournament (most recent first). Matches within each tournament are sorted in bracket order.

**Giants** (hardcoded in `GIANTS` tuple in `stats_api.py`): `300a2d8c`, `36513805`, `4d08742f`

**Response**

```json
[
  {
    "tournament_uuid": "...",
    "tournament_title": "Secret Labs AZ April 2026",
    "tournament_slug": "secret-labs-az-april-2026",
    "matches": [
      {
        "match_id": "12345678",
        "round_name": "Winners Semi-Final",
        "identifier": "WF",
        "display_score": "PlayerX 3 - Giant 1",
        "tournament_uuid": "...",
        "winner_player_id": "abcd1234",
        "winner_player_score": 3,
        "loser_player_id": "4d08742f",
        "loser_player_score": 1,
        "winner_gamertag": "PlayerX",
        "loser_gamertag": "Giant"
      }
    ]
  }
]
```

---

### `GET /api/h2h?player1=<id>&player2=<id>`

Returns all matches played between two specific players, grouped by tournament (most recent first). Matches within each tournament are sorted in bracket order.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `player1` | Yes | Player ID of the first player |
| `player2` | Yes | Player ID of the second player |

**Error responses**

| Status | Condition |
|---|---|
| `400` | Either `player1` or `player2` is missing |
| `400` | `player1` and `player2` are the same |

**Response**

```json
[
  {
    "tournament_uuid": "...",
    "tournament_title": "Secret Labs AZ April 2026",
    "tournament_slug": "secret-labs-az-april-2026",
    "matches": [
      {
        "match_id": "12345678",
        "round_name": "Grand Final",
        "identifier": "GF",
        "display_score": "BigMacCombo98 3 - C. YA 1",
        "tournament_uuid": "...",
        "winner_player_id": "4d08742f",
        "p1_score": 3,
        "p2_score": 1,
        "p1_match_win": true,
        "p2_match_win": false
      }
    ]
  }
]
```

**Fields**

| Field | Description |
|---|---|
| `p1_score` | Games won by player1 in this match |
| `p2_score` | Games won by player2 in this match |

# Secret Labs Stats — SQL Reference

All queries are executed by `stats_api.py`. Parameters shown as `:param` for readability; the actual implementation uses `%s` placeholders with pymysql.

> **Note on LIKE patterns:** Because pymysql uses `%` for parameter substitution, any `%` wildcard in a `LIKE` pattern must be written as `%%` in the Python source. The queries below show the intended SQL (single `%`) for clarity.

---

## Database Schema

Managed by `startgg_scraper.py`. Tables are created with `CREATE TABLE IF NOT EXISTS` on every run; the migration function adds columns to existing tables by checking `information_schema.COLUMNS` before issuing `ALTER TABLE`.

```sql
CREATE TABLE tournaments (
    uuid        VARCHAR(36)  NOT NULL PRIMARY KEY,
    start_gg_id BIGINT,
    title       VARCHAR(255),
    slug        VARCHAR(255) UNIQUE,
    start_at    INT                        -- Unix timestamp from start.gg API
);

CREATE TABLE events (
    id              BIGINT       NOT NULL PRIMARY KEY,
    tournament_uuid VARCHAR(36)  NOT NULL REFERENCES tournaments(uuid),
    name            VARCHAR(255),
    slug            VARCHAR(255)
);

CREATE TABLE players (
    player_id    VARCHAR(64)  NOT NULL PRIMARY KEY,
    gamertag     VARCHAR(255),
    display_name VARCHAR(255),
    points       INT          NOT NULL DEFAULT 0
);

CREATE TABLE matches (
    match_id              VARCHAR(64)  NOT NULL UNIQUE,
    identifier            VARCHAR(16),
    tournament_uuid       VARCHAR(36)  NOT NULL REFERENCES tournaments(uuid),
    event_id              BIGINT       NOT NULL,
    phase_group_id        BIGINT       NOT NULL,
    round_name            VARCHAR(255),
    winner_player_id      VARCHAR(64)  REFERENCES players(player_id),
    winner_player_score   INT,
    loser_player_id       VARCHAR(64)  REFERENCES players(player_id),
    loser_player_score    INT,
    display_score         VARCHAR(255)
);

CREATE TABLE standings (
    id              INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tournament_uuid VARCHAR(36) NOT NULL REFERENCES tournaments(uuid),
    event_id        BIGINT      NOT NULL,
    placement       INT         NOT NULL,
    player_id       VARCHAR(64) NOT NULL REFERENCES players(player_id),
    display_name    VARCHAR(255),
    points          INT
);
```

---

## `GET /api/players`

```sql
SELECT player_id, gamertag, display_name
FROM   players
ORDER  BY gamertag
```

---

## `GET /api/player/<player_id>/stats`

### Points

```sql
SELECT points
FROM   players
WHERE  player_id = :player_id
```

### Best placement

```sql
SELECT MIN(placement) AS best
FROM   standings
WHERE  player_id = :player_id
```

### Top-8 appearances

```sql
SELECT s.placement, t.title, t.uuid AS tournament_uuid, t.slug, e.name AS event_name
FROM   standings   s
JOIN   events      e ON e.id   = s.event_id
JOIN   tournaments t ON t.uuid = s.tournament_uuid
WHERE  s.player_id = :player_id
  AND  s.placement <= 8
ORDER  BY s.placement, t.start_at IS NULL, t.start_at DESC
```

### Match win / loss

Games won = player's own score across all matches. Games lost = opponent's score across all matches. Only matches with recorded scores are included.

```sql
SELECT
    COALESCE(SUM(CASE WHEN winner_player_id = :p THEN winner_player_score ELSE 0 END), 0)
  + COALESCE(SUM(CASE WHEN loser_player_id  = :p THEN loser_player_score  ELSE 0 END), 0) AS wins,
    COALESCE(SUM(CASE WHEN winner_player_id = :p THEN loser_player_score  ELSE 0 END), 0)
  + COALESCE(SUM(CASE WHEN loser_player_id  = :p THEN winner_player_score ELSE 0 END), 0) AS losses
FROM   matches
WHERE  (winner_player_id = :p OR loser_player_id = :p)
  AND  winner_player_score IS NOT NULL
  AND  loser_player_score  IS NOT NULL
```

### Set win / loss

Count of matches won vs matches lost (all matches, including those without recorded scores).

```sql
SELECT
    SUM(winner_player_id = :p) AS wins,
    SUM(loser_player_id  = :p) AS losses
FROM  matches
WHERE winner_player_id = :p OR loser_player_id = :p
```

### Top-8 match win / loss

Same game-score formula as match win/loss, restricted to matches where the loser's final placement was 7th or better (i.e. the match was played while 8 or fewer players remained).

```sql
SELECT
    COALESCE(SUM(CASE WHEN m.winner_player_id = :p THEN m.winner_player_score ELSE 0 END), 0)
  + COALESCE(SUM(CASE WHEN m.loser_player_id  = :p THEN m.loser_player_score  ELSE 0 END), 0) AS wins,
    COALESCE(SUM(CASE WHEN m.winner_player_id = :p THEN m.loser_player_score  ELSE 0 END), 0)
  + COALESCE(SUM(CASE WHEN m.loser_player_id  = :p THEN m.winner_player_score ELSE 0 END), 0) AS losses
FROM   matches m
JOIN   standings s ON s.player_id      = m.loser_player_id
                  AND s.tournament_uuid = m.tournament_uuid
                  AND s.event_id        = m.event_id
WHERE  (m.winner_player_id = :p OR m.loser_player_id = :p)
  AND  m.winner_player_score IS NOT NULL
  AND  m.loser_player_score  IS NOT NULL
  AND  s.placement <= 7
```

### Top-8 set win / loss

Count of matches won vs matches lost, restricted to the same top-8 matches.

```sql
SELECT
    SUM(m.winner_player_id = :p) AS wins,
    SUM(m.loser_player_id  = :p) AS losses
FROM  matches m
JOIN  standings s ON s.player_id      = m.loser_player_id
                 AND s.tournament_uuid = m.tournament_uuid
                 AND s.event_id        = m.event_id
WHERE (m.winner_player_id = :p OR m.loser_player_id = :p)
  AND s.placement <= 7
```

---

## `GET /api/player/<player_id>/history`

### Matches (grouped by tournament)

Retrieves all matches for the player with opponent info resolved via `CASE WHEN`. Results are grouped into tournaments by the application layer.

```sql
SELECT m.match_id,
       m.round_name,
       m.identifier,
       m.display_score,
       m.tournament_uuid,
       m.winner_player_id,
       m.winner_player_score,
       m.loser_player_score,
       t.title AS tournament_title,
       t.slug  AS tournament_slug,
       CASE WHEN m.winner_player_id = :player_id
            THEN pl.gamertag
            ELSE pw.gamertag END AS opponent_gamertag,
       CASE WHEN m.winner_player_id = :player_id
            THEN m.loser_player_id
            ELSE m.winner_player_id END AS opponent_id
FROM   matches     m
JOIN   tournaments t  ON t.uuid       = m.tournament_uuid
JOIN   players     pw ON pw.player_id  = m.winner_player_id
JOIN   players     pl ON pl.player_id  = m.loser_player_id
WHERE  m.winner_player_id = :player_id OR m.loser_player_id = :player_id
ORDER  BY t.start_at IS NULL,
          t.start_at DESC,
          CASE
            WHEN round_name LIKE 'Grand Final%' THEN 2
            WHEN round_name LIKE 'Losers%'      THEN 1
            ELSE 0
          END,
          CASE
            WHEN round_name = 'Grand Final'        THEN 0
            WHEN round_name = 'Grand Final Reset'  THEN 1
            WHEN round_name LIKE '%Round %'
              THEN CAST(SUBSTRING(round_name, LOCATE('Round ', round_name) + 6) AS UNSIGNED)
            WHEN round_name LIKE '%Quarter-Final'  THEN 900
            WHEN round_name LIKE '%Semi-Final'     THEN 950
            WHEN round_name LIKE '% Final'         THEN 990
            ELSE 500
          END
```

### Placements per tournament

Fetched separately and merged into tournament groups by the application layer.

```sql
SELECT tournament_uuid, placement
FROM   standings
WHERE  player_id = :player_id
```

---

## `GET /api/top8`

```sql
SELECT t.uuid  AS tournament_uuid,
       t.title AS tournament_title,
       t.slug  AS tournament_slug,
       e.name  AS event_name,
       s.placement,
       s.points,
       s.display_name,
       p.gamertag
FROM   standings   s
JOIN   tournaments t ON t.uuid      = s.tournament_uuid
JOIN   events      e ON e.id        = s.event_id
JOIN   players     p ON p.player_id = s.player_id
WHERE  s.placement <= 8
ORDER  BY t.start_at IS NULL, t.start_at DESC, s.placement
```

Results are grouped by tournament UUID in the application layer.

---

## `GET /api/leaderboard`

```sql
SELECT player_id, gamertag, display_name, points
FROM   players
WHERE  points > 0
ORDER  BY points DESC
LIMIT  25
```

---

## `GET /api/giant-slayers`

Giants are defined as player IDs `300a2d8c`, `36513805`, and `4d08742f`.

```sql
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
JOIN   tournaments t  ON t.uuid       = m.tournament_uuid
JOIN   players     pw ON pw.player_id = m.winner_player_id
JOIN   players     pl ON pl.player_id = m.loser_player_id
WHERE  m.loser_player_id  IN ('300a2d8c', '36513805', '4d08742f')
  AND  m.winner_player_id NOT IN ('300a2d8c', '36513805', '4d08742f')
ORDER  BY t.start_at IS NULL,
          t.start_at DESC,
          CASE
            WHEN round_name LIKE 'Grand Final%' THEN 2
            WHEN round_name LIKE 'Losers%'      THEN 1
            ELSE 0
          END,
          CASE
            WHEN round_name = 'Grand Final'        THEN 0
            WHEN round_name = 'Grand Final Reset'  THEN 1
            WHEN round_name LIKE '%Round %'
              THEN CAST(SUBSTRING(round_name, LOCATE('Round ', round_name) + 6) AS UNSIGNED)
            WHEN round_name LIKE '%Quarter-Final'  THEN 900
            WHEN round_name LIKE '%Semi-Final'     THEN 950
            WHEN round_name LIKE '% Final'         THEN 990
            ELSE 500
          END
```

---

## `GET /api/h2h`

`:p1` and `:p2` are the two player IDs passed as query parameters.

```sql
SELECT m.match_id,
       m.round_name,
       m.identifier,
       m.display_score,
       m.tournament_uuid,
       m.winner_player_id,
       t.title AS tournament_title,
       t.slug  AS tournament_slug,
       CASE WHEN m.winner_player_id = :p1
            THEN m.winner_player_score
            ELSE m.loser_player_score END AS p1_score,
       CASE WHEN m.winner_player_id = :p2
            THEN m.winner_player_score
            ELSE m.loser_player_score END AS p2_score
FROM   matches     m
JOIN   tournaments t ON t.uuid = m.tournament_uuid
WHERE  (m.winner_player_id = :p1 AND m.loser_player_id = :p2)
    OR (m.winner_player_id = :p2 AND m.loser_player_id = :p1)
ORDER  BY t.start_at IS NULL,
          t.start_at DESC,
          CASE
            WHEN round_name LIKE 'Grand Final%' THEN 2
            WHEN round_name LIKE 'Losers%'      THEN 1
            ELSE 0
          END,
          CASE
            WHEN round_name = 'Grand Final'        THEN 0
            WHEN round_name = 'Grand Final Reset'  THEN 1
            WHEN round_name LIKE '%Round %'
              THEN CAST(SUBSTRING(round_name, LOCATE('Round ', round_name) + 6) AS UNSIGNED)
            WHEN round_name LIKE '%Quarter-Final'  THEN 900
            WHEN round_name LIKE '%Semi-Final'     THEN 950
            WHEN round_name LIKE '% Final'         THEN 990
            ELSE 500
          END
```

| `p1_match_win` | `true` if player1 won the match |
| `p2_match_win` | `true` if player2 won the match |
