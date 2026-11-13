#!/bin/sh
# The version a build is stamped with: the release tag when HEAD is tagged (v1.0.0), else the
# newest CHANGELOG version plus the commit (0.1.0-86c57d4), else the commit alone.
cd "$(dirname "$0")/.."
TAG=$(git describe --tags --exact-match 2>/dev/null) && { echo "$TAG"; exit 0; }
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo dev)
TOP=$(sed -n 's/^## \[\{0,1\}\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' CHANGELOG.md 2>/dev/null | head -1)
if [ -n "$TOP" ]; then echo "$TOP-$SHA"; else echo "$SHA"; fi
