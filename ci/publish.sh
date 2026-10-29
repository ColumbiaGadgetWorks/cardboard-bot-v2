#!/bin/bash
# Publish one firmware build (and, from main, the flasher site) to the gh-pages branch.
#   ci/publish.sh <fw dir> <ref name> <ref type: branch|tag>
set -euo pipefail
FW=$1 REF=$2 TYPE=$3
NAME=$(echo "$REF" | sed 's/[^A-Za-z0-9._-]/-/g')
SRC=$(pwd)
WORK=$(mktemp -d)

git config --global user.name "github-actions[bot]"
git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
if git ls-remote --exit-code --heads origin gh-pages >/dev/null; then
  git clone --quiet --depth 1 --branch gh-pages "$(git remote get-url origin)" "$WORK/pages"
else
  mkdir -p "$WORK/pages" && cd "$WORK/pages" && git init --quiet -b gh-pages && git remote add origin "$(cd "$SRC" && git remote get-url origin)" && cd "$SRC"
fi
cd "$WORK/pages"

put() { rm -rf "fw/$1"; mkdir -p "fw/$1"; cp "$FW"/* "fw/$1/"; }
put "$NAME"
if [ "$TYPE" = branch ] && [ "$REF" = main ]; then
  # the flasher site itself comes from main
  find . -mindepth 1 -maxdepth 1 ! -name fw ! -name .git -exec rm -rf {} +
  cp -r "$SRC/site/." .
  put beta
  [ -d fw/stable ] || put stable   # until the first release tag
fi
if [ "$TYPE" = tag ] && [[ "$REF" == v* ]]; then
  put stable
fi
touch .nojekyll

# index of everything published, for the flasher's source list
python3 - <<'PY'
import json, os
out = []
for d in sorted(os.listdir("fw")):
    m = os.path.join("fw", d, "manifest.json")
    if os.path.exists(m):
        j = json.load(open(m))
        out.append({"name": d, "version": j.get("version"), "date": j.get("date"), "ref": j.get("ref")})
json.dump({"builds": out}, open("fw/index.json", "w"), indent=1)
PY

git add -A
if git diff --cached --quiet; then echo "nothing to publish"; exit 0; fi
git commit --quiet -m "Publish $REF ($(cd "$SRC" && git rev-parse --short HEAD))"
for i in 1 2 3 4; do
  if git push --quiet origin gh-pages; then exit 0; fi
  sleep $((i * 3)); git pull --quiet --rebase origin gh-pages || true
done
exit 1
