#!/usr/bin/env bash
# Download all wound & burn datasets from Kaggle into ~/WoundChrono/data/datasets/
set -euo pipefail

DEST=~/WoundChrono/data/datasets
mkdir -p "$DEST"

DATASETS=(
  "laithjj/diabetic-foot-ulcer-dfu"
  "ibrahimfateen/wound-classification"
  "yasinpratomo/wound-dataset"
  "leoscode/wound-segmentation-images"
  "shubhambaid/skin-burn-dataset"
)

for ds in "${DATASETS[@]}"; do
  name="${ds##*/}"
  if [ -d "$DEST/$name" ]; then
    echo "[SKIP] $name already exists"
    continue
  fi
  echo "[DOWNLOAD] $ds -> $DEST/$name"
  kaggle datasets download -d "$ds" -p "$DEST/$name" --unzip
  echo "[DONE] $name"
done

echo ""
echo "=== All datasets downloaded ==="
for d in "$DEST"/*/; do
  count=$(find "$d" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.bmp" \) 2>/dev/null | wc -l)
  echo "  $(basename "$d"): $count images"
done
