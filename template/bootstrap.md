# Digital Twin Bootstrap

1. Clone this repository.
2. Copy `template/config.yaml` to `config.yaml` and replace placeholders.
3. Copy `template/.env.example` to `.env` and set local secrets.
4. Run `python3 -m framework.cli init --config config.yaml`.
5. Verify `data/users/<username>/dimensions-public.json` and `data/users/registry.json` exist.
6. Push insights with `python3 -m framework.pipeline --config config.yaml --push` once your Worker API is configured.

Security rules:
- Keep `dimensions.json`, `.env`, and API keys out of git.
- Commit only `dimensions-public.json` and `registry.json`.
- Public pages must never render raw insight text.
