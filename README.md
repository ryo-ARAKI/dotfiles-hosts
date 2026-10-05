# dotfiles-hosts

DGX launch abbreviations select the managed `ollama-coding`, `ollama-research`,
and `ollama-fast` profiles explicitly.
For gpt-oss, use `codex --profile ollama-coding -m gpt-oss:120b`.
Deploy the corresponding private Ollama profiles as well as this host overlay.

The legacy `codex-dgx-refresh` generator is retired and removed from the
manifest, so reinstalling this overlay cannot recreate `ollama-launch`.
During migration, back up the deployed `~/.local/bin/codex-dgx-refresh`,
`~/.codex/ollama-launch.config.toml`, and `~/.codex/model.json`, verify the
backup contents and permissions, then remove them from their active locations.
The installer does not automatically delete targets removed from a manifest.
Keep those backups for rollback; do not run the retired generator again.
