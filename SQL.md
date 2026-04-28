# Secret Labs Stats — SQL Reference

All queries are executed by `stats_api.py`. Parameters shown as `:param` for readability; the actual implementation uses `%s` placeholders with pymysql.

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
ORDER  BY s.placement, t.title
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

### Top-6 match win / loss

Same game-score formula as match win/loss, restricted to the seven top-6 rounds.

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
  AND  round_name IN (
    'Winners Semi-Final', 'Winners Final', 'Grand Final', 'Grand Final Reset',
    'Losers Quarter-Final', 'Losers Semi-Final', 'Losers Final'
  )
```

### Top-6 set win / loss

Count of matches won vs matches lost, restricted to the seven top-6 rounds.

```sql
SELECT
    SUM(winner_player_id = :p) AS wins,
    SUM(loser_player_id  = :p) AS losses
FROM  matches
WHERE (winner_player_id = :p OR loser_player_id = :p)
  AND  round_name IN (
    'Winners Semi-Final', 'Winners Final', 'Grand Final', 'Grand Final Reset',
    'Losers Quarter-Final', 'Losers Semi-Final', 'Losers Final'
  )
```

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
ORDER  BY t.title, m.round_name
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
ORDER  BY t.title, m.round_name
```
