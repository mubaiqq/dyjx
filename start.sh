#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -d venv ]; then
  python3 -m venv venv
fi

venv/bin/pip install -r requirements.txt
exec venv/bin/python app.py
