#!/bin/bash
cd "$(dirname "$0")"

# Ensure venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt
fi

echo "Starting Discord Premiumize Bot..."
venv/bin/python main.py
