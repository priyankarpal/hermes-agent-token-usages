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

## Example output

Running `hermes tokens` (default `lifetime` window, `table` format):

```text
┌──────────┬───────────────────────────────┐
│ Key      │ Value                         │
├──────────┼───────────────────────────────┤
│ Database │ /home/ubuntu/.hermes/state.db │
│ Window   │ Lifetime                      │
│ Profile  │ —                             │
│ Format   │ table                         │
└──────────┴───────────────────────────────┘

Token Usage — Lifetime Totals

┌───────────────────┬────────────┐
│ Sessions          │ Value      │
├───────────────────┼────────────┤
│ Sessions          │ 34         │
│ Input Tokens      │ 15.5M      │
│ Output Tokens     │ 1.6M       │
│ Cache Read        │ 429.4M     │
│ Cache Write       │ 0          │
│ Reasoning         │ 632.9K     │
│ Total Tokens      │ 17.1M      │
│ API Calls         │ 2.3K       │
│ Est. Cost (USD)   │ USD 0.0000 │
│ Actual Cost (USD) │ USD 0.0000 │
└───────────────────┴────────────┘

Token Usage — Per-Model Breakdown

┌──────────────────────────┬──────────┬──────────────┬───────────────┬────────────┬──────────────┬─────────┬───────────┬─────────────────┐
│ Model                    │ Sessions │ Input Tokens │ Output Tokens │ Cache Read │ Total Tokens │ Share % │ API Calls │ Est. Cost (USD) │
├──────────────────────────┼──────────┼──────────────┼───────────────┼────────────┼──────────────┼─────────┼───────────┼─────────────────┤
│ nvidia/nemotron-3.5-sup… │ 24       │ 15.2M        │ 1.6M          │ 418.1M     │ 16.9M        │ 98.4    │ 2.2K      │ USD 0.0000      │
│ nvidia/nemotron-3-ultra… │ 7        │ 3.2M         │ 196.5K        │ 48.1M      │ 3.4M         │ 19.7    │ 420       │ USD 0.0000      │
│ private/nvidia/nemotron… │ 24       │ 149.1K       │ 13.1K         │ 0          │ 162.2K       │ 0.9     │ 94        │ USD 0.0000      │
│ stepfun/step-3.7-flash:… │ 1        │ 13.7K        │ 170           │ 1.7K       │ 13.9K        │ 0.1     │ 1         │ USD 0.0000      │
└──────────────────────────┴──────────┴──────────────┴───────────────┴────────────┴──────────────┴─────────┴───────────┴─────────────────┘

Token Usage — Per-Session Breakdown

┌──────────────────────────┬──────────────────────────┬──────────────────┬──────────────────┬──────────────┬───────────────┬────────────┬───────────┬──────────────┬───────────┬─────────────────┐
│ Session ID               │ Model                    │ Started At       │ Last Activity    │ Input Tokens │ Output Tokens │ Cache Read │ Reasoning │ Total Tokens │ API Calls │ Est. Cost (USD) │
├──────────────────────────┼──────────────────────────┼──────────────────┼──────────────────┼──────────────┼───────────────┼────────────┼───────────┼──────────────┼───────────┼─────────────────┤
│ local-e0431b53af21ff312… │ nvidia/nemotron-3.5-sup… │ 2026-11-08 13:58 │ 2026-11-08 17:02 │ 6.2M         │ 682.0K        │ 253.7M     │ 205.6K    │ 6.9M         │ 922       │ USD 0.0000      │
│ local-a12cc1362c85e6095… │ nvidia/nemotron-3.5-sup… │ 2026-11-19 12:17 │ 2026-11-19 12:45 │ 1.9M         │ 106.8K        │ 15.0M      │ 60.7K     │ 2.1M         │ 136       │ USD 0.0000      │
└──────────────────────────┴──────────────────────────┴──────────────────┴──────────────────┴──────────────┴───────────────┴────────────┴───────────┴──────────────┴───────────┴─────────────────┘
```
(Per-session table shows the top sessions by total token count, capped by `max_sessions`.)

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
