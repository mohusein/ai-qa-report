#!/bin/bash
# deploy.sh — Run once on the Linux server to set everything up
# Usage: bash deploy.sh

set -e
echo "=== QA Report — Server Setup ==="

# --- 1. System packages ---
echo "[1/6] Installing system packages..."
if sudo -n true 2>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv curl ffmpeg
else
    echo "  No passwordless sudo — skipping apt. Run manually if needed:"
    echo "  sudo apt-get install -y python3 python3-pip python3-venv curl ffmpeg"
fi

# --- 2. Project folder ---
echo "[2/6] Ensuring project folder exists..."
mkdir -p ~/qa-report
cd ~/qa-report

# --- 3. Python virtual environment ---
echo "[3/6] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# --- 4. Ollama ---
echo "[4/6] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "  Ollama already installed."
fi

echo "  Pulling llama3.2 model..."
ollama pull llama3.2

# --- 5. Output folder ---
echo "[5/6] Creating output folder..."
mkdir -p ~/qa-report/output

# --- 6. Start the dashboard ---
echo "[6/6] Configuring and starting dashboard..."

# Find an available port starting at 8501
PORT=8501
while ss -tulnp 2>/dev/null | grep -q ":$PORT "; do
    echo "  Port $PORT in use, trying next..."
    PORT=$((PORT+1))
done
echo "  Using port $PORT"

# Write streamlit config
mkdir -p ~/qa-report/.streamlit
cat > ~/qa-report/.streamlit/config.toml << TOML
[server]
port = $PORT
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
TOML

# Try systemd first, fall back to nohup
if sudo -n true 2>/dev/null; then
    sudo tee /etc/systemd/system/qa-dashboard.service > /dev/null << SERVICE
[Unit]
Description=QA Command Center Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/qa-report
ExecStart=$HOME/qa-report/venv/bin/python -m streamlit run dashboard.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE
    sudo systemctl daemon-reload
    sudo systemctl enable qa-dashboard
    sudo systemctl restart qa-dashboard
    echo "  systemd service running."
else
    echo "  No sudo — using nohup to start dashboard..."
    pkill -f "streamlit run dashboard.py" 2>/dev/null || true
    sleep 1
    nohup ~/qa-report/venv/bin/python -m streamlit run ~/qa-report/dashboard.py \
        > ~/qa-report/dashboard.log 2>&1 &
    echo "  Dashboard started in background. Logs: ~/qa-report/dashboard.log"
fi

echo ""
echo "=== Setup Complete ==="
echo "  Dashboard: http://192.168.8.50:$PORT"
echo ""
echo "Useful commands:"
echo "  tail -f ~/qa-report/dashboard.log     # view logs"
echo "  pkill -f 'streamlit run dashboard'    # stop dashboard"
echo "  bash ~/qa-report/deploy.sh            # restart everything"
