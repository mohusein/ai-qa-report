#!/bin/bash
# deploy.sh — Run once on the Linux server to set everything up
# Usage: bash deploy.sh

set -e
echo "=== QA Report — Server Setup ==="

# --- 1. System packages ---
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv curl ffmpeg

# --- 2. Project folder ---
echo "[2/6] Creating project folder..."
mkdir -p ~/qa-report
cd ~/qa-report

# --- 3. Python virtual environment ---
echo "[3/6] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# --- 4. Ollama ---
echo "[4/6] Installing Ollama..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "  Ollama already installed, skipping."
fi

echo "[4/6] Pulling llama3.2 model (this may take a few minutes)..."
ollama pull llama3.2

# --- 5. output folder ---
echo "[5/6] Creating output folder for transcripts..."
mkdir -p ~/qa-report/output

# --- 6. systemd service for Streamlit ---
echo "[6/6] Creating systemd service..."

# Find an available port starting at 8501
PORT=8501
while ss -tulnp | grep -q ":$PORT "; do
    echo "  Port $PORT is in use, trying $((PORT+1))..."
    PORT=$((PORT+1))
done
echo "  Using port $PORT"

# Write the port into the streamlit config
mkdir -p ~/qa-report/.streamlit
cat > ~/qa-report/.streamlit/config.toml <<EOF
[server]
port = $PORT
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
EOF
sudo tee /etc/systemd/system/qa-dashboard.service > /dev/null <<EOF
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
EOF

sudo systemctl daemon-reload
sudo systemctl enable qa-dashboard
sudo systemctl start qa-dashboard

echo ""
echo "=== Setup Complete ==="
echo "Dashboard running at: http://192.168.11.68:$PORT"
echo ""
echo "Next steps:"
echo "  1. Copy your api_key.txt and deepgram_key.txt to ~/qa-report/"
echo "  2. Visit http://192.168.11.68:$PORT in your browser"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status qa-dashboard   # check status"
echo "  sudo systemctl restart qa-dashboard  # restart"
echo "  journalctl -u qa-dashboard -f        # view live logs"
