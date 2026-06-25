#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Sermage/tinvest-mcp.git"
INSTALL_DIR="/opt/tinvest-mcp"
SERVICE="tinvest-mcp"
DATA_DIR="$INSTALL_DIR/data"

echo "=== tinvest-mcp deploy ==="

# 1. Install uv if missing
if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
export PATH="$HOME/.local/bin:$PATH"

# 2. Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating repo..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "Cloning repo..."
  git clone "$REPO" "$INSTALL_DIR"
fi

# 3. Install Python deps
echo "Installing dependencies..."
uv sync --project "$INSTALL_DIR" --no-dev

# 4. Create data dir
mkdir -p "$DATA_DIR"

# 5. Ensure .env exists (don't overwrite if already present)
if [ ! -f "$INSTALL_DIR/.env" ]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  echo ""
  echo "⚠️  Created $INSTALL_DIR/.env — fill in TINVEST_TOKEN and TINVEST_MCP_TOKEN before starting!"
  echo ""
fi

# 6. Install and (re)start systemd service
cp "$INSTALL_DIR/deploy/tinvest-mcp.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"

echo ""
echo "=== Done ==="
systemctl status "$SERVICE" --no-pager -l | head -20
