# Changelog

## 0.4.1

- Fix: move state to `/data/state.json` so last processed commit and history survive addon restarts, updates, and HA reboots
- Auto-migrate existing state from legacy `/addon_configs/changelog_generator/state.json`

## 0.4.0

- Commit selection: checkboxes to include/exclude individual commits before generating
- Inline diff viewer: expand each commit to see its changes
- Token estimation: per-commit and total token count shown before generating
- Select all / deselect all control with token summary
- New `/api/commit-diff/<hash>` endpoint for single-commit diff + token estimate
- `/api/generate` now accepts `selected_commits` to generate from specific commits only

## 0.3.0

- Dynamic model selection: fetch available models from OpenAI API
- Model dropdown in settings panel (persists choice in browser)
- New `/api/models` endpoint
- Model override passed per-generation instead of config-only
- Config schema now accepts any model string (not hardcoded list)

## 0.2.3

- Fix pending commits heading not resetting after changelog generation

## 0.2.2

- Fix run.sh shebang for S6 overlay compatibility (`with-contenv bash`)
- Add CHANGELOG.md

## 0.2.1

- Add addon icon

## 0.2.0

- Remove settings from ingress (available in HA config)

## 0.1.1

- Add README
- Add data-ingress to HTML template

## 0.1.0

- Initial release
