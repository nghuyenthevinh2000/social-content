#!/usr/bin/env bash
set -euo pipefail

exec docker exec -it aibrand-backend agy acp --login
