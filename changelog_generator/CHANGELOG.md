# Changelog

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
