#!/bin/bash
# MeteoAvg startup script

cd "$(dirname "$0")"

# Activate virtual environment if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "Virtual environment not found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
fi

# Run the app
python app.py
