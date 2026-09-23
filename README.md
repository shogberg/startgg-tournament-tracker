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
| `p1_match_win` | `true` if player1 won the match |
| `p2_match_win` | `true` if player2 won the match |
