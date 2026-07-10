# AI Nonymauz Telegram Bot

Telegram frontend for the [ai-nonymauz-cloud](../ai-nonymauz-cloud) API. This bot contains
no AI logic itself — it receives Telegram messages, forwards them to ai-nonymauz-cloud,
and relays the response back to the user.

```
Telegram User -> @ai_nonymauz_bots -> Telegram Bot (this repo) -> ai-nonymauz-cloud -> LLM
```

## Status

**Phase 1**: core bot commands, text message handling, logging, error
handling, and a placeholder reply when `AI_NONYMAUZ_CLOUD_URL` is not yet configured.

**Phase 2** (current): `services/cloud_client.py` forwards messages to ai-nonymauz-cloud
once `AI_NONYMAUZ_CLOUD_URL` is set. Verified live against the deployed API:

```
POST {AI_NONYMAUZ_CLOUD_URL}/chat
     body: {"messages": [{"role": "user", "content": "<text>"}], "stream": false}
     response: OpenAI-style chat completion —
       {"choices": [{"message": {"content": "<reply>", ...}}], ...}

Auth: Authorization: Bearer <AI_NONYMAUZ_CLOUD_API_KEY>   (sent only if configured;
      not currently required by the deployed API)
```

The API is stateless per request — it has no session/reset endpoint, so `/reset`
currently only clears bot-side state. Multi-turn conversation history (sending the
full message transcript per request) is a Phase 3 item.

## Requirements

- Python 3.12+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set TELEGRAM_BOT_TOKEN
```

## Running

The bot automatically chooses its update mode based on environment variables — no
code changes needed to switch between them.

**Long polling (local development)** — leave `WEBHOOK_URL` unset:

```bash
python bot.py
```

**Webhook mode (deployed, e.g. Render free Web Service)** — set `WEBHOOK_URL` to your
service's public HTTPS URL (Render sets this automatically via `RENDER_EXTERNAL_URL`,
so no manual step is needed there). The bot binds an HTTP server on `$PORT` and
registers the webhook with Telegram on startup, listening at
`{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}`. Optionally set `WEBHOOK_SECRET_TOKEN` to a random
string — Telegram echoes it back on every request so you can verify requests aren't
spoofed.

## Commands

Configure these in BotFather (`/setcommands`):

```
start - Start the bot
help - View available commands
about - About AI Nonymauz
reset - Reset the conversation
jobs - Search for job vacancies now
watchjob - Save a job search to check later
myjobs - List your saved job watches
unwatchjob - Remove a saved job watch
```

`/jobs <role>` searches on demand. `/watchjob <role>` saves a search that the
bot re-checks on a schedule and messages you about when the results change
(see "Job-watch notifications" below).

## Job-watch notifications (agentic)

In webhook mode the bot runs its own FastAPI server (`server.py`) that serves
both the Telegram endpoint and a protected `POST /tasks/run-job-watches`
endpoint. Hitting that endpoint re-runs every saved watch, and for any whose
results changed since last time, pushes an update to the user's chat. Results
are deduplicated by a hash of the search output, so unchanged results don't
re-notify.

Because the free Render web service sleeps when idle (it can't run its own
timer), the schedule is driven externally by a **free GitHub Actions cron**
(`.github/workflows/job-watch-cron.yml`) that POSTs to the endpoint every few
hours. To enable it, add two repository secrets under
Settings → Secrets and variables → Actions:

- `BOT_URL` — the bot's public URL, e.g. `https://ai-nonymauz-bot.onrender.com`
- `CRON_SECRET` — must match the `CRON_SECRET` env var set on the Render service

The endpoint is a no-op returning 503 until `CRON_SECRET` is configured, and
rejects any request whose `X-Cron-Secret` header doesn't match.

> Notification quality is bounded by ai-nonymauz-cloud's web search, which
> currently returns mostly job-board landing pages rather than structured
> postings. The mechanism improves automatically as that search improves.

## Project structure

```
ai-nonymauz-bot/
├── bot.py               # Entry point; polling locally, FastAPI webhook when deployed
├── server.py            # FastAPI app: Telegram + /tasks/run-job-watches + /health
├── config.py            # Environment variable loading
├── handlers/
│   ├── commands.py      # /start /help /about /reset
│   ├── jobs.py          # /jobs /watchjob /unwatchjob /myjobs
│   ├── messages.py      # Plain text message handler (with conversation memory)
│   └── errors.py        # Global error handler
├── services/
│   ├── cloud_client.py       # HTTP client for ai-nonymauz-cloud
│   ├── storage.py            # SQLite: conversation history + job watches
│   ├── jobs_runner.py        # Scheduled watch runner (dedup + notify)
│   └── job_notifications.py  # Production search/notify wiring for the runner
├── utils/
│   └── formatting.py    # Markdown -> Telegram HTML conversion
├── .github/workflows/
│   └── job-watch-cron.yml    # Free cron that triggers the watch runner
├── requirements.txt
├── Dockerfile
└── render.yaml
```

## Docker

```bash
docker build -t ai-nonymauz-bot .
docker run --env-file .env ai-nonymauz-bot
```

## Deploying to Render

This repo includes a `render.yaml` for a **free Web Service** running in webhook mode
(no long-running worker plan required). In the Render dashboard: New → Blueprint →
select this repo → it detects `render.yaml` → set `TELEGRAM_BOT_TOKEN` (and
`AI_NONYMAUZ_CLOUD_URL` / `AI_NONYMAUZ_CLOUD_API_KEY` once ready) → Apply.

Render injects `PORT` and `RENDER_EXTERNAL_URL` automatically, which `config.py` picks
up, so no extra webhook configuration is needed. Note that free Web Services spin down
after periods of inactivity — the first message after idle time will have a cold-start
delay of a few seconds before the bot replies.

**Storage note**: job watches are stored in a local SQLite file (`DB_PATH`, default
`data/bot.db`). Render's free-tier filesystem is not guaranteed to survive a redeploy
(only plain restarts), so saved watches may be lost when you push a new version. Move
to a hosted database if that becomes a real problem.
