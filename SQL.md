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
