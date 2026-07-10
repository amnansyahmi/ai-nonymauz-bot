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
once `AI_NONYMAUZ_CLOUD_URL` is set. Assumed API contract (update `cloud_client.py` if
your real API differs):

```
POST   {AI_NONYMAUZ_CLOUD_URL}/api/v1/chat
       body: {"session_id": <telegram_chat_id>, "message": "<text>"}
       response: {"reply": "<text>"}

DELETE {AI_NONYMAUZ_CLOUD_URL}/api/v1/chat/{session_id}
       clears server-side conversation history (called by /reset)

Auth:  Authorization: Bearer <AI_NONYMAUZ_CLOUD_API_KEY>   (sent only if configured)
```

The Telegram chat_id is used as the session_id — ai-nonymauz-cloud is expected to own
conversation history, so the bot only ever sends the latest message, not a transcript.

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

## Running (development, long polling)

```bash
python bot.py
```

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
├── bot.py              # Entry point, builds the Application and runs polling
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

This repo includes a `render.yaml` for a background worker service. Push to GitHub,
connect the repo in Render, and set the `TELEGRAM_BOT_TOKEN` and `AI_NONYMAUZ_CLOUD_URL`
environment variables in the Render dashboard.
