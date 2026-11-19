# Hermes Token Usage Plugin

Token usage analytics from the local Hermes database (`~/.hermes/state.db`)
directly in the CLI. No network, no auth, no Hermes Desktop required.

## What it shows

* **Lifetime totals** — sessions, input/output/cache-read/cache-write/reasoning
  tokens, grand total, API calls, estimated and actual cost (USD).
* **Per-model breakdown** — model, sessions, input/output/cache-read tokens,
  total tokens, share of grand total (%), API calls, estimated cost.
* **Per-session breakdown** — session ID, model, started/last activity,
  input/output/cache-read/reasoning tokens, total tokens, API calls, cost.
* **Configurable time windows** — `lifetime`, `7d`, `30d`, `90d`.
* **Profile filtering** and **archived-session toggle**.
* **Table** (plain text) or **JSON** output.

## Installation

```bash
hermes plugins install priyankarpal/hermes-agent-token-usages --enable
```

## Invocation

CLI (`hermes tokens`):

```bash
hermes tokens [--window 7d|30d|90d|lifetime] [--model <model>] [--session <id>] [--format table|json] [--profile <profile>]
```

Options:

| Option | Meaning |
|--------|---------|
| `--window` | Time window: `lifetime`, `7d`, `30d`, `90d` |
| `--model` | Filter to a specific model |
| `--session` | Drill down into a specific session ID |
| `--profile` | Filter to a specific `profile_name` |
| `--format` | Output format: `table` or `json` |

## Configuration

All configuration lives in `~/.hermes/config.yaml` under `token_plugin:`
(or environment variables prefixed `TOKEN_PLUGIN_*`):

| Config key | Env var | Default | Description |
|------------|---------|---------|-------------|
| `token_plugin.db_path` | `TOKEN_PLUGIN_DB_PATH` | `~/.hermes/state.db` | Path to the Hermes state SQLite database (read-only). |
| `token_plugin.default_window` | `TOKEN_PLUGIN_DEFAULT_WINDOW` | `lifetime` | Default time window. |
| `token_plugin.include_archived` | `TOKEN_PLUGIN_INCLUDE_ARCHIVED` | `false` | Include archived sessions in totals. |
| `token_plugin.output_format` | `TOKEN_PLUGIN_OUTPUT_FORMAT` | `table` | `table` or `json`. |
| `token_plugin.max_sessions` | `TOKEN_PLUGIN_MAX_SESSIONS` | `50` | Max sessions to list in the per-session breakdown. |
| `token_plugin.profile` | `TOKEN_PLUGIN_PROFILE` | `` | Optional `profile_name` filter applied to all queries. |
| `token_plugin.currency_label` | `TOKEN_PLUGIN_CURRENCY_LABEL` | `USD` | Currency label for cost columns (USD only; no FX conversion). |

All user-facing labels and column headers are config-driven under
`token_plugin.labels:*` — unset labels fall back to the key itself.

## Database

Reads only from `~/.hermes/state.db` via a read-only URI connection
(`mode=ro`), so the running Hermes gateway is never locked. Tables used:
`sessions` and `session_model_usage`. Never writes to the database.

## Requirements

* Python stdlib only (`sqlite3`, `argparse`, `json`).
* PyYAML is used when available (already a Hermes dependency); a small
  built-in fallback parser handles simple config files.
