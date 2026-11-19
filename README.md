# Hermes Token Usage Plugin

Token usage analytics from the local Hermes database (`~/.hermes/state.db`)
directly in the TUI/CLI. No network, no auth, no Hermes Desktop required.

## What it shows

* **Lifetime totals** — sessions, input/output/cache-read/cache-write/reasoning
  tokens, grand total, API calls, estimated and actual cost (USD).
* **Per-model breakdown** — model, sessions, input/output/cache-read tokens,
  total tokens, share of grand total (%), API calls, estimated cost.
* **Per-session breakdown** — session ID, model, started/last activity,
  input/output/cache-read/reasoning tokens, total tokens, API calls, cost.
* **Configurable time windows** — `lifetime`, `7d`, `30d`, `90d`.
* **Profile filtering** and **archived-session toggle**.
* **Table** (TUI-safe plain text) or **JSON** output.

## Invocation

CLI:

```bash
hermes tokens [--window 7d|30d|90d|lifetime] [--model <model>] [--session <id>] [--format table|json] [--profile <profile>]
```

## Configuration

All configuration lives in `~/.hermes/config.yaml` under `token_plugin:`
(or environment variables prefixed `TOKEN_PLUGIN_*`):

| Config key | Env var | Default | Description |
|---|---|---|---|
| `token_plugin.db_path` | `TOKEN_PLUGIN_DB_PATH` | `~/.hermes/state.db` | Path to the Hermes state SQLite database. |
| `token_plugin.default_window` | `TOKEN_PLUGIN_DEFAULT_WINDOW` | `lifetime` | Default time window. |
| `token_plugin.include_archived` | `TOKEN_PLUGIN_INCLUDE_ARCHIVED` | `false` | Include archived sessions. |
| `token_plugin.output_format` | `TOKEN_PLUGIN_OUTPUT_FORMAT` | `table` | `table` or `json`. |
| `token_plugin.max_sessions` | `TOKEN_PLUGIN_MAX_SESSIONS` | `50` | Max sessions to list. |
| `token_plugin.profile` | `TOKEN_PLUGIN_PROFILE` | `` | Optional profile_name filter. |
| `token_plugin.currency_label` | `TOKEN_PLUGIN_CURRENCY_LABEL` | `USD` | Currency label for cost columns (USD only; no FX conversion, which would require network data). |

All user-facing labels and column headers are also config-driven under
`token_plugin.labels:*` — see `docs/configuration.md`.

## Installation

From the plugin folder:

```bash
hermes plugins install ./path/to/token-usage --enable
```

Or copy into the plugins directory and enable in `config.yaml`:

```bash
cp -r token-usage ~/.hermes/plugins/token-usage
```

Then add to `~/.hermes/config.yaml`:

```yaml
token_plugin:
  db_path: ~/.hermes/state.db
  default_window: lifetime
  include_archived: false
  output_format: table
  max_sessions: 50
  profile: ""

plugins:
  enabled:
    - agent-importers
    - token-stats
    - token-usage
```

## Database

Reads only from `~/.hermes/state.db` (read-only URI connection, `mode=ro`),
so the running gateway is never locked. Tables used: `sessions` and
`session_model_usage`. Never writes to the database.

## Docs

* `docs/configuration.md` — full configuration reference.
* `docs/queries.md` — SQL queries used by the plugin.
* `docs/verification.md` — verification steps and expected output.

## Requirements

* Python stdlib only (`sqlite3`, `argparse`, `json`).
* PyYAML is used when available (already a Hermes dependency); a small
  built-in fallback parser handles simple config files.
