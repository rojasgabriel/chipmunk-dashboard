# Changelog

## 1.0.0

First stable release of `chipmunk-dashboard` as both a standalone Dash app and a
native **Chipmunk** tab inside `labdata dashboard`.

### Highlights
- Register the bundled Chipmunk page with `chipmunk-dashboard install-labdata`
- Session settings lists every presented stimulus rate instead of a min–max range
- Labdata adapter prefers the checkout registered in `user_preferences.json`
- Install into the same environment that runs plain `labdata dashboard` (no uv required for labdata)

### Also since 0.2.0
- Collapsible sidebar and debug/fixture UI paths without a live database
- Streamlit presentation parity for the labdata Chipmunk tab
- Dependency and security upgrades, agent/contributor guidance

## 0.2.0

- Improve session-date related features
- Add training-time multi-session plot

## 0.1.0

- Initial release
