#!/usr/bin/env bash
# Fetch the raw data into data/raw/ at the exact commits Phase 1 was built from,
# and make sure the SkillCorner tracking files are real files, not Git LFS pointers.
#
#   bash scripts/setup_data.sh
#
# Needs: git, git-lfs (macOS: brew install git-lfs), curl.
set -euo pipefail

SC_URL="https://github.com/SkillCorner/opendata.git"
SC_COMMIT="4340d274572876239c154c90bc507a9b3250a656"   # master on 2026-09-14
ME_URL="https://github.com/metrica-sports/sample-data.git"
ME_COMMIT="e706dd506b360d69d9d123d5b8026e7294b13996"   # 2021-04-15

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

clone_at() {  # url dir commit
  local url=$1 dir=$2 commit=$3
  if [ ! -d "$RAW/$dir/.git" ]; then
    echo ">> cloning $dir"
    GIT_LFS_SKIP_SMUDGE=1 git clone --quiet "$url" "$RAW/$dir"
  fi
  git -C "$RAW/$dir" -c advice.detachedHead=false checkout --quiet "$commit"
  echo ">> $dir at $(git -C "$RAW/$dir" rev-parse --short HEAD)"
}

command -v git-lfs >/dev/null || { echo "ERROR: git-lfs not installed (macOS: brew install git-lfs)"; exit 1; }
git lfs install --skip-repo >/dev/null

clone_at "$SC_URL" skillcorner_opendata "$SC_COMMIT"
clone_at "$ME_URL" metrica_sample_data "$ME_COMMIT"

cd "$RAW/skillcorner_opendata"
echo ">> pulling Git LFS objects (~1.8 GB)"
git lfs pull || echo "   git lfs pull failed - falling back to GitHub media URLs"

# Verify every LFS file: real content whose SHA-256 equals the pointer's oid.
fail=0
while IFS= read -r f; do
  oid=$(git show "HEAD:$f" | sed -n 's/^oid sha256://p')
  if head -c 40 "$f" | grep -q "git-lfs.github.com/spec"; then
    echo "   $f is still a pointer - downloading"
    curl -sSL --retry 3 -o "$f.download" "https://media.githubusercontent.com/media/SkillCorner/opendata/$SC_COMMIT/$f"
    mv "$f.download" "$f"
  fi
  got=$(sha256 "$f")
  if [ "$got" != "$oid" ]; then echo "   CHECKSUM MISMATCH: $f"; fail=1; fi
done < <(git lfs ls-files -n)
[ $fail -eq 0 ] || { echo "ERROR: some LFS files failed verification"; exit 1; }
echo ">> all $(git lfs ls-files -n | wc -l | tr -d ' ') LFS files verified against their pointer SHA-256"
