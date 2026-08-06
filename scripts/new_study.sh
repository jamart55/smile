#!/bin/bash
# Provision a new lab study repo end to end, with its own DreamHost deploy key.
#
# Usage: npm run new_study -- [--dry-run] <study-name> <github-username> [description]
#
# Run from the root of a nyucdsc/smile checkout that has env/.env.local and
# env/.env.deploy.local populated (the lab's shared Firebase + deploy config).
# See docs/labconfig.md for what those files contain.
#
# BASE_REPO env var overrides the template repo (default nyucdsc/smile), for
# a different lab base.

set -euo pipefail

ORG=nyucdsc
BASE_REPO="${BASE_REPO:-nyucdsc/smile}"

DRY_RUN=false
STUDY=""
GH_USER=""
DESCRIPTION=""

usage() {
  echo "Usage: npm run new_study -- [--dry-run] <study-name> <github-username> [description]" >&2
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
      elif [ -z "$GH_USER" ]; then
        GH_USER="$arg"
      elif [ -z "$DESCRIPTION" ]; then
        DESCRIPTION="$arg"
      else
        usage
      fi
      ;;
  esac
done
[ -n "$STUDY" ] && [ -n "$GH_USER" ] || usage

STUDY_REPO="$ORG/$STUDY"
KEYFILE="$HOME/.ssh/nyucdsc_deploy_${STUDY}"

# Every gh/ssh call in this script routes through here so --dry-run prints
# exactly what would run and executes nothing. In dry-run mode the call is
# assumed to succeed so the rest of the script's control flow still prints.
maybe_run() {
  if $DRY_RUN; then
    echo "+ $*"
    return 0
  fi
  "$@"
}

# Pulls KEY's value out of a lab env/.env.*.local file (space-padded
# `KEY = "value"` dotenv-ish format — see docs/labconfig.md). Strips
# surrounding double quotes if present.
# Empty stdout (no such key) is a legitimate outcome (SLACK_WEBHOOK_* are
# optional) — `|| true` keeps a missing key from tripping `set -e` via
# pipefail, since grep's own exit status is 1 when nothing matches.
dotenv_get() {
  local key="$1" file="$2"
  { grep -E "^${key}[[:space:]]*=" "$file" | tail -1 |
    sed -E "s/^${key}[[:space:]]*=[[:space:]]*//" |
    sed -E 's/^"(.*)"$/\1/'; } || true
}

echo "==> Preflight"

for bin in gh ssh-keygen ssh node; do
  command -v "$bin" >/dev/null 2>&1 || {
    echo "error: '$bin' not found on PATH" >&2
    exit 1
  }
done

if ! [[ "$STUDY" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "error: study name '$STUDY' must match ^[a-z0-9][a-z0-9-]*\$" >&2
  exit 1
fi

if [ ! -f env/.env.local ] || [ ! -f env/.env.deploy.local ]; then
  echo "error: run this from a smile repo root with env/.env.local and env/.env.deploy.local present" >&2
  exit 1
fi

maybe_run gh auth status >/dev/null

if [ -e "$KEYFILE" ]; then
  echo "error: $KEYFILE already exists — pick a different study name or clean it up first" >&2
  exit 1
fi

if $DRY_RUN; then
  echo "+ gh repo view $STUDY_REPO  # (would abort if this succeeds)"
else
  if gh repo view "$STUDY_REPO" >/dev/null 2>&1; then
    echo "error: $STUDY_REPO already exists" >&2
    exit 1
  fi
fi

EXP_DEPLOY_USER=$(dotenv_get EXP_DEPLOY_USER env/.env.deploy.local)
EXP_DEPLOY_HOST=$(dotenv_get EXP_DEPLOY_HOST env/.env.deploy.local)
EXP_DEPLOY_PORT=$(dotenv_get EXP_DEPLOY_PORT env/.env.deploy.local)
EXP_DEPLOY_PATH=$(dotenv_get EXP_DEPLOY_PATH env/.env.deploy.local)
SLACK_WEBHOOK_URL=$(dotenv_get SLACK_WEBHOOK_URL env/.env.deploy.local)
SLACK_WEBHOOK_ERROR_URL=$(dotenv_get SLACK_WEBHOOK_ERROR_URL env/.env.deploy.local)

for v in EXP_DEPLOY_USER EXP_DEPLOY_HOST EXP_DEPLOY_PORT EXP_DEPLOY_PATH; do
  if [ -z "${!v}" ]; then
    echo "error: $v missing from env/.env.deploy.local" >&2
    exit 1
  fi
done

echo "==> Generating deploy key: $KEYFILE"
maybe_run ssh-keygen -t ed25519 -N "" -C "nyucdsc-deploy-${STUDY}" -f "$KEYFILE"

echo "==> Installing pubkey on $EXP_DEPLOY_HOST"
if $DRY_RUN; then
  echo "+ cat ${KEYFILE}.pub | ssh -p $EXP_DEPLOY_PORT $EXP_DEPLOY_USER@$EXP_DEPLOY_HOST 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'"
else
  cat "${KEYFILE}.pub" |
    ssh -p "$EXP_DEPLOY_PORT" "$EXP_DEPLOY_USER@$EXP_DEPLOY_HOST" \
      'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
fi

echo "==> Verifying the new key before touching GitHub"
if $DRY_RUN; then
  echo "+ ssh -i $KEYFILE -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p $EXP_DEPLOY_PORT $EXP_DEPLOY_USER@$EXP_DEPLOY_HOST true"
else
  if ! ssh -i "$KEYFILE" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
    -p "$EXP_DEPLOY_PORT" "$EXP_DEPLOY_USER@$EXP_DEPLOY_HOST" true; then
    echo "error: new key does not authenticate. Undo the authorized_keys append with:" >&2
    echo "  ssh -p $EXP_DEPLOY_PORT $EXP_DEPLOY_USER@$EXP_DEPLOY_HOST \"grep -v 'nyucdsc-deploy-${STUDY}\$' ~/.ssh/authorized_keys > ~/.ssh/ak.new && mv ~/.ssh/ak.new ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys\"" >&2
    exit 1
  fi
fi

echo "==> Creating $STUDY_REPO from template $BASE_REPO"
maybe_run gh repo create "$STUDY_REPO" --private --template "$BASE_REPO"

# Repo creation is async on GitHub's side; hitting repos/$STUDY_REPO right
# after the create call can 404 before it's materialized. Poll rather than
# risk steps 6-8 failing after the pubkey is already live on the server.
echo "==> Waiting for $STUDY_REPO to become available"
if $DRY_RUN; then
  echo "+ poll: gh repo view $STUDY_REPO (up to 15 x 2s)"
else
  found=false
  for _ in $(seq 1 15); do
    if gh repo view "$STUDY_REPO" >/dev/null 2>&1; then
      found=true
      break
    fi
    sleep 2
  done
  if ! $found; then
    echo "error: $STUDY_REPO did not become available after creation (30s). The pubkey is already installed on $EXP_DEPLOY_HOST — check GitHub manually, then re-run once the repo shows up." >&2
    exit 1
  fi
fi

if [ -n "$DESCRIPTION" ]; then
  echo "==> Setting description on $STUDY_REPO"
  maybe_run gh repo edit "$STUDY_REPO" --description "$DESCRIPTION"
fi

# Actions being disabled by default only applies to forks (docs/labconfig.md
# "Enable Actions on your new template repository"). A --template copy is a
# normal repo, so Actions should already be on; this call is expected to be a
# harmless no-op here, kept as a belt-and-suspenders in case that ever changes.
# Non-fatal: an org-level Actions policy could make this 422 even though the
# repo (and pubkey, and collaborator/secrets still to come) are already live —
# warn and keep going rather than abort a half-provisioned run over an
# optional step.
echo "==> Ensuring Actions are enabled on $STUDY_REPO"
maybe_run gh api -X PUT "repos/$STUDY_REPO/actions/permissions" -F enabled=true -f allowed_actions=all >/dev/null \
  || echo "[warn] could not set Actions permissions on $STUDY_REPO — check the repo's Actions tab manually" >&2

echo "==> Adding $GH_USER as admin collaborator"
maybe_run gh api -X PUT "repos/$STUDY_REPO/collaborators/$GH_USER" -f permission=admin >/dev/null

echo "==> Uploading secrets"
upload_secrets() {
  set +x # never trace this block — it would put secret values in the log
  local enc
  if $DRY_RUN; then
    echo "+ gh secret set SECRET_APP_CONFIG --body '<base64 of env/.env.local>' --repo $STUDY_REPO"
  else
    enc=$(base64 <env/.env.local)
    gh secret set SECRET_APP_CONFIG --body "$enc" --repo "$STUDY_REPO"
  fi

  local name value
  for name in EXP_DEPLOY_HOST EXP_DEPLOY_USER EXP_DEPLOY_PATH EXP_DEPLOY_PORT SLACK_WEBHOOK_URL SLACK_WEBHOOK_ERROR_URL; do
    if $DRY_RUN; then
      echo "+ gh secret set $name --body '<from env/.env.deploy.local>' --repo $STUDY_REPO"
    else
      value=$(dotenv_get "$name" env/.env.deploy.local)
      gh secret set "$name" --body "$value" --repo "$STUDY_REPO"
    fi
  done

  # Piped from stdin, never a file or argv — see docs section on why.
  if $DRY_RUN; then
    echo "+ gh secret set EXP_DEPLOY_KEY --repo $STUDY_REPO < $KEYFILE"
  else
    gh secret set EXP_DEPLOY_KEY --repo "$STUDY_REPO" <"$KEYFILE"
  fi
}
upload_secrets

CODENAME=$(node scripts/codenamize.cjs "/${ORG}/${STUDY}/main") || CODENAME=unknown

DONE_SUFFIX=""
if $DRY_RUN; then DONE_SUFFIX=" (dry-run, nothing was actually created)"; fi

cat <<EOF

==> Done${DONE_SUFFIX}

Study repo:   https://github.com/$STUDY_REPO
Clone URL:    git@github.com:${STUDY_REPO}.git
Deploy key:   $KEYFILE (public half already installed on $EXP_DEPLOY_HOST)
Deploy URL:   https://$EXP_DEPLOY_HOST/${ORG}/${STUDY}/main/ (once deployed)
Codename URL: https://$EXP_DEPLOY_HOST/e/$CODENAME

Next steps for $GH_USER:
  1. git clone git@github.com:${STUDY_REPO}.git
  2. cd $STUDY && npm run setup_project
  3. Request TWO files from the lab vault and drop them in env/:
       env/.env.local          (Firebase config)
       env/.env.deploy.local   (deploy host/user/path/port + Slack webhooks —
                                 this copy will have NO EXP_DEPLOY_KEY line,
                                 that's expected: this study's key was set
                                 directly as a GitHub secret and never leaves
                                 this machine. A later 'npm run upload_config'
                                 from the owner is safe and will not clobber it.)
  4. Push a commit on a deployable branch to trigger the first deploy.
EOF
