#!/usr/bin/env bash
# Scripted local worker for the e2e example: performs one assignment as a real commit in a package worktree.
# usage: worker.sh <repo> <worktree> <branch> <base> <op> <purpose> <path>...
set -euo pipefail
repo=$1 wt=$2 branch=$3 base=$4 op=$5 purpose=$6
shift 6
if [ ! -d "$wt" ]; then
	git -C "$repo" worktree add -q -b "$branch" "$wt" "$base"
fi
for path in "$@"; do
	mkdir -p "$wt/$(dirname "$path")"
	printf '# %s (%s)\n' "$op" "$purpose" >>"$wt/$path"
done
git -C "$wt" add -A
git -C "$wt" -c user.name=worker -c user.email=worker@example.invalid commit -q -m "$op: $purpose" -m "Orchestration-Op: $op"
echo "run-${op//:/-}"
