# Website architecture
- Keep the GitHub Pages product in `docs/` as standalone browser scripts; `backend/` and `frontend/` are a separate parked product.
- Implement visitor preferences and generated audio locally in browser feature scripts, without runtime services, so static hosting remains sufficient.
- Keep theme overrides in the shared stylesheet and ambient preferences in `docs/lounge.js`; audio starts only from explicit user interaction.
- Test browser-safe feature rules with Node's built-in test runner alongside the Python crawler tests before publishing changes.
