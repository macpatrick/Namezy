# Namezy

Find a brand name you can actually own.

Namezy generates candidate product/company names from a plain-text description, then actually validates them — instead of just suggesting names and leaving you to check availability yourself, it checks `.com`/`.io`/`.app` domain availability and scores every candidate for brandability (length, pronounceability, domain availability) so you get a ranked, explorable shortlist instead of a flat list of guesses.

Runs entirely on your own machine, using your own Anthropic API key — nothing is hosted, nothing is shared, your key never leaves your computer.

## Features

- Describe your product in plain English, get ~150-200 real candidate names (invented words, compound names, and theme-derived names)
- Automatic near-duplicate removal (catches things like "Pikto" / "Picto")
- Live `.com` / `.io` / `.app` domain availability checks
- 0-100 brandability score per candidate, weighted toward domain availability
- Sortable results table, favorites, CSV export
- Optional web-conflict checking via a search API (see [Configuration](#configuration))

## Requirements

- Python 3.9+
- An [Anthropic API key](https://console.anthropic.com/) (this is what actually generates the names — the app will not run without one)

## Setup

```bash
git clone <this-repo-url>
cd Namezy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set:

```
ANTHROPIC_API_KEY=your-key-here
```

Then run it:

```bash
python3 app.py
```

Open `http://127.0.0.1:5000` in your browser.

**macOS note:** if you get a connection error or unexpected response on port 5000, macOS's AirPlay Receiver often binds that exact port. Either turn it off (System Settings → General → AirDrop & Handoff → AirPlay Receiver) or run on a different port: `python3 -c "import app; app.app.run(port=5050)"` and open `http://127.0.0.1:5050` instead.

## Configuration

All optional settings live in `.env` (see `.env.example` for the full list):

| Variable | Default | Purpose |
|---|---|---|
| `NAMEZY_CLAUDE_MODEL` | `claude-sonnet-5` | Which Claude model generates names. Bump to a larger model for higher-quality candidates, or a smaller one for lower cost. |
| `NAMEZY_CANDIDATE_COUNT` | `200` | How many candidate names to generate per run. |
| `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_CX` | unset | Optional web-conflict check via Google Custom Search. **Note:** as of mid-2026, Google's Custom Search JSON API is closed to new customers — a newly created API key will not work regardless of setup. If you have a pre-existing key from before the closure, it'll work fine; otherwise this check simply reports "not configured" and the rest of the app runs normally. If you want this feature, the cleanest path is swapping `check_web_conflict()` in `validation.py` to a provider that's still open to new signups (e.g. Serper.dev, Brave Search API). |

## How it works

1. **Brand Strategist** — one Claude call extracts personality traits, words to avoid, and seed keywords from your description.
2. **Name Generator** — a second Claude call generates candidate names based on that profile.
3. **Duplicate Eliminator** — collapses near-duplicate names.
4. **Validation** — checks domain availability (free DNS-based heuristic) and, if configured, web conflicts.
5. **Scoring** — combines everything into a 0-100 brandability score.
6. **Results** — a sortable table with favorites and CSV export.

## A note on results

Candidate names and domain/availability checks are generated heuristically and are **not** a substitute for a real trademark search or legal advice. Always independently verify a name — including a proper trademark search — before committing to it commercially.

## Roadmap ideas (not built)

- Real trademark search (would need a paid third-party API — see the note above on why free government APIs don't cover this)
- App Store / Play Store name search
- Social handle availability
- Iterative generation (learn from favorited names, bias the next batch toward what worked)

## Support

If you find Namezy helpful, consider supporting the project:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/macpatrick)

## License

MIT — see [LICENSE](LICENSE).
