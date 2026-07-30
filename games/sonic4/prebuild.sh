#!/bin/bash
set -euo pipefail

# sonic4 prebuild — intentionally a NO-OP.
#
# The OJZ level tree (games/sonic4/data/generated/) and the ROM collision tables
# (games/sonic4/data/collision/*.bin) used to be regenerated here every build.
# They are now COMMITTED artifacts the build consumes directly, because their
# generators read out-of-repo donor projects (sonic_hack / skdisasm) that a
# fresh checkout does not have — regenerating at build time made a fresh
# worktree build a wrong ROM (or fail). See .gitignore (the level-gen parcel).
#
# To RE-BAKE the level tree from the editor data + donor projects, run
# tools/regenerate-level.sh by hand, then commit the regenerated tree.
#
# This file stays as a documented hook: if sonic4 ever needs build-time content
# generation that depends ONLY on in-repo inputs, add it here.

exit 0
