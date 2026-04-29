# Secret Labs Stats — Points & Leaderboard

## Points Formula

Points are awarded per tournament placement and stored in the `standings` table. A player's total career points (stored in `players.points`) is the sum of all their placement points across every tournament.

| Placement | Points |
|---|---|
| 1st | 10 |
| 2nd | 8 |
| 3rd | 7 |
| 4th | 6 |
| 5th–6th | 5 |
| 7th–8th | 4 |
| 9th and below | 1 |

## Recalculation

Player points are recalculated at the end of every scraper run:

```sql
UPDATE players p
JOIN (
    SELECT player_id, COALESCE(SUM(points), 0) AS total
    FROM   standings
    GROUP  BY player_id
) s ON s.player_id = p.player_id
SET p.points = s.total
```

## Leaderboard

The leaderboard displays the top 25 players by career points. Only players with at least 1 point are shown. A points breakdown table is displayed beneath the leaderboard in the UI showing how points are awarded per placement. See [`API.md`](API.md) for the endpoint reference and [`SQL.md`](SQL.md) for the query.
