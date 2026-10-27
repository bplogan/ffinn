#!/bin/sh
# Runs inside a throwaway node container (see ai-agent-staging.yml) with the feature branch's frontend at /src.
set -eu
cd /src
node --version
npm ci
npx tsc --noEmit
npm test -- --passWithNoTests
