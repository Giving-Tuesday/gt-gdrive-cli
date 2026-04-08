# Credentials and authentication

`gdrive-unified` talks to Google Drive and Google Docs via OAuth 2.0. There are two files involved:

| File | Purpose | Source |
|---|---|---|
| `gdrive-unified-credentials.json` | OAuth **client** config (the "app" identity) | Obtained once, per team or per user |
| `gdrive-unified-token.pickle` | Your **user** token, issued after consenting | Auto-generated on first run |

The filenames are namespaced so they don't collide with other Google tools (`gspread`, the Google API Python Client quickstart samples, and several MCP servers all default to a generic `credentials.json` in `~/.google/`). The legacy generic names (`credentials.json`, `token.pickle`) still work as a fallback for existing installs.

## Two paths to getting credentials

### Path A — use the team's shared OAuth client

If you're on the Giving Tuesday Data Team (or another group that ships its own OAuth client), ask the maintainer for `gdrive-unified-credentials.json`. Drop it into one of the locations in the [Where to put the file](#where-to-put-the-file) section below and run:

```bash
gdrive init
```

This opens a browser window, asks *you* to sign in with your Google account, and writes your personal token locally. The shared client JSON is *not* a secret in the cryptographic sense — Google's Desktop OAuth flow explicitly assumes the client secret can be extracted from the binary. What is personal is the **token**, which is issued to your Google account and stays on your machine.

Caveats your maintainer should already have sorted, but worth checking:

- The OAuth consent screen must be **Published** (or the maintainer must have added you as a Test User). Unpublished apps in Testing mode are limited to 100 test users and tokens expire every 7 days.
- If the scopes change, old tokens won't work — delete your token file and re-run `gdrive init`.

### Path B — create your own Google Cloud project

Use this if you don't trust the bundled client, your org forbids third-party OAuth apps, or you're developing `gdrive-unified` itself.

1. Go to <https://console.cloud.google.com/> and create a new project (or pick an existing one).
2. **APIs & Services → Library**, enable:
   - **Google Drive API**
   - **Google Docs API** (required for `gdrive upload` and `gdrive write-tab`)
3. **APIs & Services → OAuth consent screen**:
   - Choose **External** (unless you're on Google Workspace and want Internal).
   - Fill in the required fields.
   - Under **Test users**, add your own Google account email.
   - You do not need to publish the app for personal use.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - Download the JSON.
5. Rename the downloaded file to `gdrive-unified-credentials.json` (or leave it as `credentials.json` — both work).
6. Place it in one of the locations below.
7. Run `gdrive init`. Click through the "unverified app" warning — expected for apps in Testing mode.

## Where to put the file

`gdrive` searches for credentials in this order. Drop your file into **any one** of these:

1. **`$GDRIVE_CREDENTIALS_PATH`** — environment variable, either a file path or a directory containing one of the known filenames. Highest priority. Best for CI and one-off overrides.
2. **Current working directory** — useful during development (`gdrive-unified-credentials.json` or `credentials.json`). Usually gitignored.
3. **Platform config directory** — the canonical "install once, use anywhere" location:
   - macOS: `~/Library/Application Support/gdrive-unified/`
   - Linux: `$XDG_CONFIG_HOME/gdrive-unified/` or `~/.config/gdrive-unified/`
   - Windows: `%APPDATA%\gdrive-unified\`
4. **`~/.google/`** — convenience location shared with other Google tools. Works identically on all OSes (`C:\Users\<you>\.google\` on Windows). Use the namespaced filename here to avoid collisions with those tools.
5. **Bundled with the package** — if the maintainer shipped a `src/gdrive_unified/data/credentials.json` inside the install, it's used as the last-resort fallback. You can see whether you're using the bundled client by running `gdrive status`.

**Recommended for most users**: put the file at `~/.google/gdrive-unified-credentials.json`. It's cross-platform, doesn't require knowing the XDG spec, and doesn't get deleted when `uv tool upgrade` reinstalls the package.

## Token storage

Tokens are written next to the credentials file by default (except when using bundled credentials, where they go to the platform config dir so the package install stays read-only). The canonical token name is `gdrive-unified-token.pickle`; the legacy `token.pickle` name is honored if one already exists in the target directory so existing installs aren't silently forked.

On first successful auth, expect to see:

```
~/.google/
├── gdrive-unified-credentials.json
└── gdrive-unified-token.pickle
```

## Troubleshooting

Run `gdrive status` for a snapshot of what the tool thinks it's using — credentials path, token path, validity, whether you're on bundled creds, and any env var override.

### `Could not find credentials.json`

You haven't placed the file in any of the five search locations. Quickest fix:

```bash
mkdir -p ~/.google
mv ~/Downloads/client_secret_*.json ~/.google/gdrive-unified-credentials.json
gdrive init
```

### `Token has been expired or revoked` / `RefreshError`

The refresh token is no longer accepted by Google. Common reasons:

- You're on an **unpublished** OAuth consent screen (Testing mode) and the 7-day refresh window elapsed. Publish the app, or add yourself as a Test User and re-consent.
- You **revoked access** in your Google Account security settings.
- The **scopes changed** between versions.
- You signed in with a **different Google account** than the token was issued to.

As of this version, `gdrive` auto-detects this, prints the offending token path, deletes it, and re-runs the OAuth flow. If you'd rather reset manually:

```bash
# Find the path
gdrive status
# Delete the file it printed
rm '<token path>'
# Re-auth
gdrive init
```

### `unverified app` warning

Expected when your OAuth app is in Testing mode. Click **Advanced → Go to <app name> (unsafe)**. Only do this for OAuth clients you trust (your own, or one from your team).

### `ModuleNotFoundError` during install

Not a credentials problem — you probably skipped the `[conversion]` extra. Reinstall with:

```bash
uv tool install --reinstall 'gdrive-unified[conversion]' \
  --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git
```

## A note on scopes

The default scopes are broad:

```
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/documents
```

These grant access to all files in your Drive. For most `gdrive-unified` use cases (searching across the whole Drive, downloading arbitrary folders) this is load-bearing. If your workflow only touches files the tool itself creates or opens, narrower scopes (`drive.file`, `documents` alone) would avoid Google's verification gauntlet entirely — but changing scopes invalidates existing tokens. See `src/gdrive_unified/credentials.py` if you want to experiment.
