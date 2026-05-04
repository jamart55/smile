#!/bin/bash


url=$(git config --get remote.origin.url)

repo_path=$(echo "$url" | sed -E 's|.*/([^/]+)/([^/.]+)(\.git)?|\1/\2|')


# update the app configs using a base64 encoding of
# all the variables (use python to avoid macOS base64 line-wrap issue)
ENC=$(python3 -c "import base64; f=open('env/.env.local','rb'); print(base64.b64encode(f.read()).decode())")
gh secret set SECRET_APP_CONFIG --body "$ENC" --repo $repo_path


# update doc secrets (these go one variable at a time)
# only do this if repo name is nyuccl/docs
re="^(https|git)(:\/\/|@)([^\/:]+)[\/:]([^\/:]+)\/(.+)(.git)*$"

if [[ $url =~ $re ]]; then    
    protocol=${BASH_REMATCH[1]}
    separator=${BASH_REMATCH[2]}
    hostname=${BASH_REMATCH[3]}
    user=${BASH_REMATCH[4]}
    repo=${BASH_REMATCH[5]}
fi

if [[ "$user/$repo" == "NYUCCL/smile.git" ]]
then
    gh secret set -f env/.env.docs.local
fi

# update deploy secrets individually (gh secret set -f can't handle multi-line values or KEY = "value" format)
parse_env_val() {
    # strips leading/trailing whitespace and surrounding quotes from a value
    echo "$1" | sed -E 's/^[[:space:]]*"?([^"]*)"?[[:space:]]*$/\1/'
}

EXP_DEPLOY_HOST=$(parse_env_val "$(grep '^EXP_DEPLOY_HOST' env/.env.deploy.local | cut -d= -f2-)")
EXP_DEPLOY_PATH=$(parse_env_val "$(grep '^EXP_DEPLOY_PATH' env/.env.deploy.local | cut -d= -f2-)")
EXP_DEPLOY_PORT=$(parse_env_val "$(grep '^EXP_DEPLOY_PORT' env/.env.deploy.local | cut -d= -f2-)")
EXP_DEPLOY_USER=$(parse_env_val "$(grep '^EXP_DEPLOY_USER' env/.env.deploy.local | cut -d= -f2-)")
SLACK_WEBHOOK_URL=$(parse_env_val "$(grep '^SLACK_WEBHOOK_URL' env/.env.deploy.local | cut -d= -f2-)")
SLACK_WEBHOOK_ERROR_URL=$(parse_env_val "$(grep '^SLACK_WEBHOOK_ERROR_URL' env/.env.deploy.local | cut -d= -f2-)")

gh secret set EXP_DEPLOY_HOST --body "$EXP_DEPLOY_HOST" --repo $repo_path
gh secret set EXP_DEPLOY_PATH --body "$EXP_DEPLOY_PATH" --repo $repo_path
gh secret set EXP_DEPLOY_PORT --body "$EXP_DEPLOY_PORT" --repo $repo_path
gh secret set EXP_DEPLOY_USER --body "$EXP_DEPLOY_USER" --repo $repo_path
gh secret set SLACK_WEBHOOK_URL --body "$SLACK_WEBHOOK_URL" --repo $repo_path
gh secret set SLACK_WEBHOOK_ERROR_URL --body "$SLACK_WEBHOOK_ERROR_URL" --repo $repo_path

# EXP_DEPLOY_KEY must be set from the actual key file, not .env.deploy.local
KEY_FILE=$(parse_env_val "$(grep '^EXP_DEPLOY_KEY_FILE' env/.env.deploy.local | cut -d= -f2-)")
KEY_FILE="${KEY_FILE/#\~/$HOME}"
if [ -n "$KEY_FILE" ] && [ -f "$KEY_FILE" ]; then
    gh secret set EXP_DEPLOY_KEY --repo $repo_path < "$KEY_FILE"
else
    echo "WARNING: EXP_DEPLOY_KEY not updated. Add EXP_DEPLOY_KEY_FILE=~/.ssh/ds_dreamhost to env/.env.deploy.local"
fi