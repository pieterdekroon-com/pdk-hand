#!/bin/sh
# Photos to fonts. Run from the root of the repository.
set -e
python scripts/segment.py
python scripts/build.py
python scripts/specimen.py
