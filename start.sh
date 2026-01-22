#!/bin/bash
cd "$(dirname "$0")"

if [ -f config.json ]; then
    python3 sync.py
else
    echo "Configuration not found. Starting setup..."
    python3 sync.py --setup
fi
