# Deploying MeteoAvg to cPanel

This guide covers multiple deployment options for your cPanel server.

## Option 1: cPanel "Setup Python App" (Recommended)

Most modern cPanel installations have a **"Setup Python App"** feature that makes deployment easy.

### Step 1: Access Python App Feature
1. Log into cPanel
2. Look for **"Setup Python App"** under the "Software" section
3. Click **"Create Application"**

### Step 2: Configure the Application
```
Python version:     3.10+ (choose the latest available)
Application root:   meteo-avg
Application URL:    yourdomain.com/meteo  (or a subdomain)
Application startup file: app.py
Application entry point: app (NOT app.app)
```

### Step 3: Upload Files
1. Use **File Manager** or **FTP** to upload `meteo-avg.zip`
2. Extract to your application root directory
3. Or upload via the cPanel Python App interface

### Step 4: Install Dependencies
In the Python App interface, click **"Run Pip Install"** and enter:
```
fastapi uvicorn httpx jinja2 pydantic
```

Or via terminal (if you have SSH):
```bash
cd ~/meteo-avg
pip install -r requirements.txt
```

### Step 5: Set Environment Variables (Optional)
If you want to use API keys for more providers, add them in the Python App interface:
```
OPENWEATHERMAP_API_KEY=your_key_here
WEATHERAPI_KEY=your_key_here
```

### Step 6: Restart the Application
Click **"Restart"** in the Python App interface

---

## Option 2: Manual Deployment via SSH

If you have SSH access, this gives you more control.

### Step 1: Upload Files
```bash
# Upload meteo-avg.zip via SCP or SFTP, then:
cd ~
unzip meteo-avg.zip
cd meteo-avg
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Create a Startup Script
Create `run.sh`:
```bash
#!/bin/bash
cd /home/YOUR_USERNAME/meteo-avg
source venv/bin/activate
nohup uvicorn web.server:app --host 127.0.0.1 --port 8000 > app.log 2>&1 &
echo $! > app.pid
```

### Step 4: Run the App
```bash
chmod +x run.sh
./run.sh
```

### Step 5: Configure Reverse Proxy

**For Apache** (add to `.htaccess` in your public_html):
```apache
RewriteEngine On
RewriteRule ^meteo/(.*)$ http://127.0.0.1:8000/$1 [P,L]
```

**Or for a subdomain**, edit the Apache vhost configuration to proxy to port 8000.

---

## Option 3: Systemd Service (Best for Production)

If you have root/sudo access, create a systemd service.

### Step 1: Create Service File
```bash
sudo nano /etc/systemd/system/meteoavg.service
```

Content:
```ini
[Unit]
Description=MeteoAvg Weather Dashboard
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/meteo-avg
Environment="PATH=/home/YOUR_USERNAME/meteo-avg/venv/bin"
ExecStart=/home/YOUR_USERNAME/meteo-avg/venv/bin/uvicorn web.server:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Step 2: Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable meteoavg
sudo systemctl start meteoavg
sudo systemctl status meteoavg
```

---

## Option 4: Simple Screen/Tmux (Quick & Dirty)

If you just want it running quickly:

```bash
cd ~/meteo-avg
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Using screen
screen -S meteoavg
uvicorn web.server:app --host 0.0.0.0 --port 8000
# Press Ctrl+A then D to detach

# Or using tmux
tmux new -s meteoavg
uvicorn web.server:app --host 0.0.0.0 --port 8000
# Press Ctrl+B then D to detach
```

---

## Setting the Default City

### Method 1: Edit app.py
Edit line in `app.py`:
```python
default_city = "Your City Name"
```

### Method 2: Use the Search Feature
Once deployed, use the search box in the UI to find and set your city.

---

## Troubleshooting

### Check if app is running:
```bash
ps aux | grep uvicorn
netstat -tlnp | grep 8000
```

### Check logs:
```bash
tail -f ~/meteo-avg/app.log
# Or for systemd:
journalctl -u meteoavg -f
```

### Common Issues:

1. **Port already in use**: Change the port number (8000 → 8001, etc.)

2. **Permission denied**: Check file permissions
   ```bash
   chmod +x start.sh
   chmod -R 755 ~/meteo-avg
   ```

3. **Module not found**: Make sure you're in the virtual environment
   ```bash
   source venv/bin/activate
   ```

4. **Can't access from browser**: Check if firewall allows the port, or use reverse proxy

---

## Quick Start Summary

```bash
# 1. Upload and extract
cd ~ && unzip meteo-avg.zip

# 2. Setup
cd meteo-avg
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Edit default city (optional)
nano app.py  # Change default_city

# 4. Run
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 5. Access
# Open http://your-server-ip:8000 in browser
```

---

## Need More Help?

Share your cPanel version and I can provide more specific instructions!
