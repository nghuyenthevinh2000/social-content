#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${DIR}/../.." && pwd)"
exec "${REPO_ROOT}/.agents/skills/beautiful-html-templates/scripts/export-pdf.sh" "${DIR}/slides.html" "${DIR}/zk-commercialization-slides.pdf" "$@"
