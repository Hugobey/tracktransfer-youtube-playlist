# TrackTransfer — YouTube Music

Move a Spotify playlist to YouTube Music from the CSV exported by the TrackTransfer browser extension.

Upload the CSV, review the matches, then create the playlist. There is no account on this app and no browser extension in this repository.

## CSV

The parser accepts only the exporter schema. Columns, in order:

```text
position, track_name, artist, artists, album, duration, duration_ms, date_added, spotify_track_id, spotify_url, explicit
```

Files are UTF-8. A leading BOM is ignored. The delimiter is a comma, or a semicolon when the header contains more semicolons than commas. Playlist order is kept, including the same song twice and rows with missing title, artist, or duration. A sample file is in `samples/`.

The default playlist title is `{CSV filename} — TrackTransfer`.

## Run

Python 3.12 and Node 22 are what this copy was built with. The system `python3` on this machine is 3.9, so use the backend virtualenv.

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The Next.js app proxies `/api/*` to `http://127.0.0.1:8000`. Override that with `TRACKTRANSFER_API_ORIGIN`.

Copy `.env.example` to `backend/.env` or the repository root when you want playlist creation. Search does not need those variables.

## YouTube Music

Search uses [ytmusicapi](https://ytmusicapi.readthedocs.io/en/stable/). It is an unofficial client. Google does not endorse it, and YouTube's developer policies prohibit undocumented API use without permission. This integration is an experimental prototype. It does not rotate accounts, change headers to look like another client, or collect browser cookies, passwords, or session headers.

Song search is unauthenticated. Playlist creation uses the library's device OAuth flow:

1. In Google Cloud, enable the YouTube Data API.
2. Create an OAuth client of type **TVs and Limited Input devices**.
3. Set `YTMUSIC_CLIENT_ID` and `YTMUSIC_CLIENT_SECRET` on the server.

The browser receives a user code and a Google verification URL. Access and refresh tokens are written under `backend/data/sessions/` with mode `0600`. They are not returned to the client and are not stored in `localStorage`. If the client is missing, search and review still work. Playlist endpoints return `auth_not_configured`.

A playlist is created once. If adding tracks fails partway, retry uses the same playlist id. A failed item stops the rest of that chunk so later tracks are not inserted ahead of the gap. **Skip failed and continue** leaves that row out and keeps the remaining order. The same video can appear twice when the CSV contains it twice. Success is shown only when the job status is `complete`.

## Matching

Weights: artist 30%, title 30%, version 25%, duration 10%, other metadata 5%.

A result is selected automatically only at high confidence (score at least 0.84, with artist, title, and version each above their own floors). The first result is not accepted for being first. Likely matches stay unselected. A strong version mismatch cannot become high or likely. Extended, radio, remix, and live versions are not treated as the same recording. `Original Mix` is close to a plain title. Queries do not append `Original Mix` or `Official Audio` unless the source title already says that.

The live check is `backend/scripts/evaluate_matching.py`. It searches the public catalog for the labelled list (more than 100 real DJ tracks, plus four titles that should not resolve). Labels use artist overlap, base-title similarity, and version compatibility. They do not reuse the ranker weights. The script does not retry, and it stops the remaining waves if a whole wave of ten searches fails.

```bash
cd backend
.venv/bin/python scripts/evaluate_matching.py --output ../reports/matching-eval.json
```

A run on 20 November 2026 scored all 105 labels with no search errors. Results are in `reports/matching-eval.json`.

| Measure | Count |
|---|---:|
| Labelled tracks | 105 |
| Right recording ranked first | 73 |
| Right recording somewhere in the top three | 73 |
| Different version ranked first | 7 |
| No acceptable candidate returned | 32 |
| High confidence on a wrong top result | 0 |

The 73 right recordings were also the only auto-selected rows. Whenever the song search returned an acceptable recording, it was ranked first. The 32 misses are tracks the song search did not return an acceptable candidate for: most are extended mixes, radio edits, remixes, or live versions, plus the four planted titles. Those rows stayed in review. A different remix of the same song, such as a Sasha remix where the CSV asked for What So Not, scored highly on artist and title and was still left unselected because the version did not match. Weights were not changed after this run. Changing them would not create a candidate the search did not return.

## API

```text
GET  /api/health
POST /api/csv/parse
POST /api/search
POST /api/search/batch
GET  /api/auth/status
POST /api/auth/start
POST /api/auth/poll
POST /api/playlist/create
POST /api/playlist/add-tracks
GET  /api/playlist/status/{job_id}
```

Batch search accepts at most 40 tracks. The page sends about 20 at a time, with three searches in flight on the server. The browser session is an httpOnly cookie named `tt_session`. Imported tracks, matches, selections, skips, and the playlist job id are stored in `localStorage` under `tracktransfer.youtube.v1`. The raw CSV and OAuth tokens are not.

## Tests

```bash
cd backend && .venv/bin/pytest
cd frontend && npx tsc --noEmit && npm run lint
```

Backend tests cover the exporter CSV (including 10, 50, 100, and 300 rows), version-aware matching, playlist order, partial add failure, retry without duplicate positions, and the HTTP API with a fake catalog. They do not call YouTube Music.
