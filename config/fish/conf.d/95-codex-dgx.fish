if status --is-interactive
    abbr codex-dgx "codex --profile ollama-coding -C ."
    abbr codex-dgx-code "codex --profile ollama-coding -C ."
    abbr codex-dgx-research "codex --profile ollama-research -C ."
    abbr codex-dgx-fast "codex --profile ollama-fast -C ."
    abbr codex-dgx-connect "ssh -fN -o ClearAllForwardings=yes -L 11436:127.0.0.1:11434 -o ExitOnForwardFailure=yes spark-ollama-codex"
    abbr codex-dgx-status "curl -fsS http://127.0.0.1:11436/api/ps"
    abbr codex-dgx-check "codex-dgx-verify"
end
