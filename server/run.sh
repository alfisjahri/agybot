#!/bin/bash
# AgyBot dev/run helper (service is the normal path)
cd "$(dirname "$0")"
exec ./venv/bin/python app.py
