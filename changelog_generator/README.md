# Changelog Generator — Documentation

## What it does

This addon generates human-readable changelogs from your Home Assistant `/config` git history using OpenAI. When triggered, it:

1. Reads recent git commits from `/config` (read-only)
2. Sends the diff to OpenAI for summarization
3. Stores the result as a Home Assistant sensor (`sensor.ha_changelog`)
4. Displays changelogs in the addon's ingress UI

## Prerequisites

- Your `/config` directory must be a git repository
- You need an OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Git commits should be made to `/config` (manually or via an automation)

## Setup

1. Install the addon
2. Go to **Configuration** tab and enter your OpenAI API key
3. Click **Start**
4. Open the addon's **Web UI** (or find "Changelog" in the sidebar)
5. Click **Generate Changelog**

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `openai_api_key` | (required) | Your OpenAI API key |
| `openai_model` | `gpt-4o-mini` | Model to use. Options: `gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`, `gpt-4.1-nano` |
| `system_prompt` | (built-in) | Custom AI prompt. Leave empty for the built-in default |
| `max_diff_chars` | `100000` | Max diff size sent to OpenAI (cost safety) |
| `excluded_paths` | `custom_components/` | Paths to exclude from the diff |
| `cooldown_seconds` | `60` | Minimum wait between generations |
| `history_count` | `20` | Number of past changelogs to keep |

## Dashboard Cards

### Simple Markdown Card

```yaml
type: markdown
title: "Changelog"
content: "{{ state_attr('sensor.ha_changelog', 'changelog') }}"
```

### Conditional Card (hides when unavailable)

```yaml
type: conditional
conditions:
  - entity: sensor.ha_changelog
    state_not: "unavailable"
card:
  type: markdown
  title: "Config Changelog"
  content: >
    {{ state_attr('sensor.ha_changelog', 'changelog') }}
    
    ---
    *Generated {{ state_attr('sensor.ha_changelog', 'generated_at') }} 
    from {{ state_attr('sensor.ha_changelog', 'commit_count') }} commit(s)*
```

### Button + Changelog Stack

```yaml
type: vertical-stack
cards:
  - type: button
    name: "Generate Changelog"
    tap_action:
      action: navigate
      navigation_path: /hassio/ingress/changelog_generator
  - type: markdown
    title: "Latest Changes"
    content: "{{ state_attr('sensor.ha_changelog', 'changelog') }}"
```

## How it works

**First run:** Diffs the entire git history (all commits).

**Subsequent runs:** Diffs from the last processed commit to current HEAD. The last processed commit hash is stored persistently. If the stored commit no longer exists (e.g., after a force push), falls back to diffing the full history.

## Custom System Prompt

You can fully replace the AI prompt via the `system_prompt` option. The prompt receives a git diff as user input and should instruct the model how to format the changelog. This is useful for:

- Writing changelogs in a different language
- Focusing on specific types of changes
- Changing the output format

## Safety

- `/config` is mounted **read-only** — the addon cannot modify your configuration
- Your API key is never logged or exposed in the UI
- Diff size is capped to prevent accidental cost spikes
- A cooldown prevents rapid repeated API calls

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Git is not initialized in /config" | Run `git init` in your `/config` directory and make at least one commit |
| "No new changes since last run" | Make and commit changes to `/config` first |
| "OpenAI API key is invalid" | Double-check your key in addon configuration |
| Sensor not appearing | Generate a changelog first — the sensor is created on first successful run |
| Changelog looks wrong | Try a different model or customize the system prompt |
