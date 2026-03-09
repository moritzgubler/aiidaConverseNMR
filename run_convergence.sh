#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <structure_file> [extra nmr-converse args...]"
    exit 1
fi

STRUCTURE="$1"
shift
EXTRA_ARGS=("$@")

PROTOCOLS=(fast moderate precise)
DEGAUSS=(0.01 0.001)
SMEARING=(gaussian fermi-dirac)

for protocol in "${PROTOCOLS[@]}"; do
    for smearing in "${SMEARING[@]}"; do
        for degauss in "${DEGAUSS[@]}"; do
            echo "--- protocol=$protocol smearing=$smearing degauss=$degauss ---"
            nmr-converse -i "$STRUCTURE" \
                --pseudo-family gipaw_PBEsol \
                -t 0 \
                -p "$protocol" \
                --smearing-type "$smearing" \
                --smearing-degauss "$degauss" \
                "${EXTRA_ARGS[@]}"
        done
    done
done
