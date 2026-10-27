#!/bin/sh
# Runs inside a throwaway python container (see ai-agent-staging.yml) with the feature branch's backend at /src.
set -eu
cd /src
python --version
pip install -q -r requirements-dev.txt
ruff check app/ --select E,W,F --ignore E501
pytest tests/ -x -q --tb=short
