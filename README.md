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
```

## Project structure

```
ai-nonymauz-bot/
├── bot.py              # Entry point; runs polling locally, webhook when deployed
├── config.py            # Environment variable loading
├── handlers/
│   ├── commands.py      # /start /help /about /reset
│   ├── messages.py      # Plain text message handler
│   └── errors.py        # Global error handler
├── services/
│   └── cloud_client.py  # HTTP client for ai-nonymauz-cloud
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
