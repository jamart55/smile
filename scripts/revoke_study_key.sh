#!/bin/bash
# Revoke a per-study deploy key created by new_study.sh. Every other study's
# key keeps working — that's the whole point of one key per study.
#
# Usage: npm run revoke_study_key -- [--dry-run] <study-name>
#
# Run from the root of a nyucdsc/smile checkout with env/.env.deploy.local
# present (all studies share the same DreamHost host/user/port).

set -euo pipefail

ORG=nyucdsc

DRY_RUN=false
STUDY=""

usage() {
  echo "Usage: npm run revoke_study_key -- [--dry-run] <study-name>" >&2
  exit 1
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    -h | --help) usage ;;
    -*)
      echo "Unknown flag: $arg" >&2
      usage
      ;;
    *)
      if [ -z "$STUDY" ]; then
        STUDY="$arg"
      else
        usage
      fi
      ;;
  esac
done
[ -n "$STUDY" ] || usage

if ! [[ "$STUDY" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "error: study name '$STUDY' must match ^[a-z0-9][a-z0-9-]*\$" >&2
  exit 1
fi

STUDY_REPO="$ORG/$STUDY"
KEYFILE="$HOME/.ssh/nyucdsc_deploy_${STUDY}"
COMMENT="nyucdsc-deploy-${STUDY}"

if [ ! -f env/.env.deploy.local ]; then
  echo "error: run this from a smile repo root with env/.env.deploy.local present" >&2
  exit 1
fi

dotenv_get() {
  local key="$1" file="$2"
  { grep -E "^${key}[[:space:]]*=" "$file" | tail -1 |
    sed -E "s/^${key}[[:space:]]*=[[:space:]]*//" |
    sed -E 's/^"(.*)"$/\1/'; } || true
}

EXP_DEPLOY_USER=$(dotenv_get EXP_DEPLOY_USER env/.env.deploy.local)
EXP_DEPLOY_HOST=$(dotenv_get EXP_DEPLOY_HOST env/.env.deploy.local)
EXP_DEPLOY_PORT=$(dotenv_get EXP_DEPLOY_PORT env/.env.deploy.local)

for v in EXP_DEPLOY_USER EXP_DEPLOY_HOST EXP_DEPLOY_PORT; do
  if [ -z "${!v}" ]; then
    echo "error: $v missing from env/.env.deploy.local" >&2
    exit 1
  fi
done

echo "==> Removing '$COMMENT' from authorized_keys on $EXP_DEPLOY_HOST"
# Anchored on the end of the line: the comment is the last field of an
# authorized_keys entry, and study names can prefix one another (e.g. "foo"
# vs "foo-pilot") — an unanchored grep -v would silently revoke both.
REMOTE_CMD="grep -v '${COMMENT}\$' ~/.ssh/authorized_keys > ~/.ssh/ak.new && mv ~/.ssh/ak.new ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
if $DRY_RUN; then
  echo "+ ssh -p $EXP_DEPLOY_PORT $EXP_DEPLOY_USER@$EXP_DEPLOY_HOST \"$REMOTE_CMD\""
else
  ssh -p "$EXP_DEPLOY_PORT" "$EXP_DEPLOY_USER@$EXP_DEPLOY_HOST" "$REMOTE_CMD"
fi

echo "==> Deleting EXP_DEPLOY_KEY secret on $STUDY_REPO"
if $DRY_RUN; then
  echo "+ gh secret delete EXP_DEPLOY_KEY --repo $STUDY_REPO"
else
  gh secret delete EXP_DEPLOY_KEY --repo "$STUDY_REPO"
fi

echo "==> Shredding local key halves"
for f in "$KEYFILE" "${KEYFILE}.pub"; do
  if $DRY_RUN; then
    echo "+ shred -u $f"
  elif [ -e "$f" ]; then
    shred -u "$f"
  fi
done

echo "==> Done. $COMMENT is revoked; every other study's key is untouched."
