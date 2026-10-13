# Claude LinkedIn Manager

A Claude-powered toolkit that helps you manage your LinkedIn presence end to end:

- **Draft posts** — turn a topic + a few options into a polished, human-sounding post
- **Engage** — generate comments, replies, and connection-request notes
- **Optimize your profile** — get prioritized, recruiter-grade suggestions for your headline, About section, and experience bullets
- **Build a stunning CV** — produce a clean, ATS-friendly CV in Markdown from your background
- **Publish** — optionally post straight to LinkedIn via the official API (or run fully local with zero setup)

Everything is powered by the [Anthropic Claude API](https://docs.anthropic.com/). The content tools work with **no LinkedIn access required** — you only need LinkedIn credentials if you want the tool to auto-post for you.

## Install

```bash
git clone https://github.com/drtamar/claude-linkedin-manager-.git
cd claude-linkedin-manager-
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configure

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Your Anthropic API key |
| `LINKEDIN_MANAGER_MODEL` | — | Override the model (default `claude-opus-4-8`) |
| `LINKEDIN_MANAGER_OUTPUT_DIR` | — | Where drafts/CVs are saved (default `./output`) |
| `LINKEDIN_ACCESS_TOKEN` | — | OAuth token, only to auto-post |
| `LINKEDIN_AUTHOR_URN` | — | Your member URN, only to auto-post |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | — | LinkedIn app credentials, only for `auth` |
| `LINKEDIN_REDIRECT_URI` | — | OAuth redirect (default `http://localhost:8000/callback`) |

## Usage

The CLI has five subcommands. Text arguments can be **literal text**, a **file path**, or `-` to read from stdin.

```bash
# Draft a post
linkedin-manager post "lessons from scaling a team to 50 engineers" --tone thoughtful

# Draft a post with talking points from a file, then publish it
linkedin-manager post "our Series A" --notes notes.txt --publish

# Reply to someone's post (paste it via stdin)
pbpaste | linkedin-manager comment - --intent "add a contrarian but respectful take"

# Connection note
linkedin-manager connect "Jane Doe" --reason "we both spoke at PyCon" --about "I lead data eng at Acme"

# Optimize your profile (export/paste your profile text into profile.txt)
linkedin-manager profile profile.txt --role "Senior Product Manager"

# Generate a CV from your background
linkedin-manager cv resume_notes.txt --role "Staff Software Engineer"
```

Generated posts, profile suggestions, and CVs are also saved to the output directory.

You can also use it as a library:

```python
from linkedin_manager.config import Config
from linkedin_manager.claude_client import ClaudeClient
from linkedin_manager import content

client = ClaudeClient.from_config(Config.from_env())
print(content.draft_post(client, "why code review matters", tone="bold"))
```

## How posting works

`post --publish` uses LinkedIn's official UGC API, which needs an OAuth 2.0 token
with the `w_member_social` scope plus your member URN. **Without those credentials
the tool runs in "local-only" mode** — it still generates and saves everything, it
just doesn't send anything to LinkedIn. This keeps the default experience zero-setup
and within LinkedIn's Terms of Service.

### Getting a token with `auth`

Instead of copying the token and URN by hand, run the built-in OAuth flow:

```bash
# 1. Create a LinkedIn app and set LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET
#    in .env, and add http://localhost:8000/callback to the app's redirect URLs.
# 2. Run the flow — it opens your browser, then saves the credentials:
linkedin-manager auth --write-env .env
```

It opens LinkedIn's consent page, captures the redirect on a local server,
exchanges the code for an access token, derives your member URN via the
OpenID Connect userinfo endpoint, and writes both into `.env`. After that,
`linkedin-manager post "..." --publish` posts for real.

## Project layout

```
linkedin_manager/
  config.py          # env/.env loading
  claude_client.py   # thin Claude API wrapper (streaming)
  prompts.py         # all system prompts + prompt builders
  content.py         # post drafting
  engagement.py      # comments, replies, connection notes
  profile.py         # profile optimization
  cv.py              # CV generation
  linkedin.py        # publishing adapter (with local-only fallback)
  oauth.py           # LinkedIn OAuth 2.0 flow (token + member URN)
  cli.py             # command-line interface
tests/               # fast unit tests (no network, no API key needed)
```

## Develop & test

```bash
pip install -e ".[dev]"
pytest
```

The test suite stubs the Claude client, so it runs offline and needs no API key.

## License

MIT — see [LICENSE](LICENSE).
