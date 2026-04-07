# Telegram Job Board Bot

A simple Telegram bot that lets members of a channel post jobs. Posts appear in the channel as a short notification (title + short description), and anyone can tap **View Full Details** to expand the full listing inline. Admins can delete any job.

## How it works

1. Member DMs the bot → `/post`
2. Bot walks them through: **title → short description → full details → contact**
3. Bot shows a preview and asks them to confirm
4. On confirm, the bot posts to your channel:
   ```
   💼 Job Title
   Short description line here.
   [📋 View Full Details]
   ```
5. Anyone tapping **View Full Details** sees the whole listing inline. Tapping **Collapse** shrinks it back.
6. Admins can run `/delete <job_id>` in DM to remove a job from the channel and the database.

## Setup

### 1. Create the bot
- Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts → copy the **token**.
- Send `/setprivacy` → choose your bot → **Disable** (so it can read group messages if needed).

### 2. Add bot to your channel
- Open your channel → **Administrators** → **Add Admin** → search for your bot → grant:
  - ✅ Post messages
  - ✅ Edit messages of others
  - ✅ Delete messages

### 3. Get your channel ID
- Forward any message from the channel to [@userinfobot](https://t.me/userinfobot).
- You'll see `Forwarded from chat: -1001234567890`. That's your `CHANNEL_ID`.

### 4. Get admin IDs
- Each admin sends `/start` to [@userinfobot](https://t.me/userinfobot) → copy the ID.
- Put them comma-separated in `ADMIN_IDS`.

## Deploy to Railway

1. Push this folder to a new GitHub repo.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → pick the repo.
3. In the service → **Variables** tab → add:
   - `BOT_TOKEN`
   - `CHANNEL_ID`
   - `ADMIN_IDS`
   - `DB_PATH=/data/jobs.db`
4. In the service → **Settings** → **Volumes** → **New Volume** → mount path `/data`. This keeps your DB alive across redeploys.
5. Deploy. Check logs — you should see `Bot starting...`.
6. Test: DM the bot `/start`, then `/post`.

## Run locally (optional)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
export $(cat .env | xargs)
export DB_PATH=./jobs.db
python bot.py
```

## Commands

| Command | Who | What |
|---|---|---|
| `/start` | Anyone | Welcome + help |
| `/post` | Anyone (in DM) | Start the job posting flow |
| `/myjobs` | Anyone | List your own posted jobs with IDs |
| `/cancel` | Anyone | Abort the current `/post` flow |
| `/delete <id>` | Admins only | Delete a job (from channel + DB) |

## Monthly cost on Railway

| Item | Cost |
|---|---|
| Hobby plan subscription | **$5/mo** (includes $5 usage credit) |
| Bot process (512 MB RAM, near-idle CPU) | ~$3–5/mo of usage |
| Volume (1 GB, SQLite DB) | ~$0.25/mo |
| **Total** | **~$5/mo** — the included credit usually covers everything |

For 250 members this will never come close to the limits. If you ever outgrow Hobby (unlikely), Pro is $20/mo.

## Extending it

Easy upgrades you can add later:
- **Categories/tags** — add a step in the conversation for category, filter by hashtag in the channel
- **Expiry** — auto-delete jobs after N days via a scheduled job
- **Reactions/bookmarks** — let users save jobs to their DMs
- **Mini App** — a proper browsable UI (filter, search, saved jobs) launched from a button on each channel post
