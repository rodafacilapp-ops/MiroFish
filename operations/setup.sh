#!/usr/bin/env bash
# Reusable Codex Cloud setup; never starts services, simulations, or AI calls.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="${MIROFISH_RUNTIME_DIR:-$(dirname -- "$repo_root")/.mirofish-runtime/$(basename -- "$repo_root")}"
mkdir -p -- "$runtime_dir"
runtime_dir="$(cd -- "$runtime_dir" && pwd)"
export UV_CACHE_DIR="$runtime_dir/uv-cache"
export UV_PYTHON_INSTALL_DIR="$runtime_dir/python"
export UV_LINK_MODE=copy
export PYTHON_DOTENV_DISABLED=1
for tool in node npm uv python3; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
node -e 'const [major,minor]=process.versions.node.split(".").map(Number); if(!((major===20 && minor>=19)||(major===22 && minor>=12)||major>=24)) {console.error("Use Node 20.19+, 22.12+, or 24+ for Vite 7.");process.exit(1)}'
cd -- "$repo_root"

# A matching lockfile and Node runtime allow prepared dependencies to be reused.
install_node() {
  local target="$1" label="$2" fingerprint marker
  marker="$runtime_dir/$label.node-fingerprint"
  fingerprint="$(python3 - "$target/package-lock.json" <<'PY'
import hashlib, sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
) $(node --version) $(npm --version)"
  if [[ ! -d "$target/node_modules" || ! -f "$marker" || "$(cat -- "$marker")" != "$fingerprint" ]]; then
    npm ci --prefix "$target" --cache "$runtime_dir/npm-cache"
    printf '%s\n' "$fingerprint" > "$marker"
  else
    echo "Reusing prepared Node dependencies: $label"
  fi
}
install_node "$repo_root" root
install_node "$repo_root/frontend" frontend

# Store Python outside /tmp so a prepared environment snapshot can retain it.
uv python install --no-bin 3.11
python_path="$(uv python find --managed-python 3.11)"
cd backend
if [[ -x .venv/bin/python ]] && ! .venv/bin/python - "$UV_PYTHON_INSTALL_DIR" <<'PY'
import sys
from pathlib import Path
sys.exit(0 if Path(sys.base_prefix).resolve().is_relative_to(Path(sys.argv[1]).resolve()) else 1)
PY
then
  echo 'Recreating only the dependency .venv to use persistent managed Python.'
  uv venv --clear --python "$python_path" .venv
fi
uv sync --locked --python "$python_path"
.venv/bin/python - <<'PY'
import flask, openai, zep_cloud, httpx
from dotenv import load_dotenv
print('Backend dependency imports OK; no external API request made.')
PY
echo 'Setup complete. Start services separately with python3 operations/control.py start.'
