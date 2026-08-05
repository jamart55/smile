#!/bin/bash

# force a deployment

BRANCH=$(git rev-parse --abbrev-ref HEAD | tr '[:upper:]' '[:lower:]')

echo "Forcing a deploy of branch: $BRANCH." 
echo "Warning: this will only work if you have run 'npm run upload_config' at least once"

# --ref matters as much as github_sha: deploy.yml takes its checkout from the input but
# VITE_GIT_BRANCH_NAME and the codename from GITHUB_REF_SLUG, which follows --ref. Without
# it gh dispatches on the default branch, so $BRANCH's code deploys under main's base path,
# main's codename, and main's Firestore projectRef.
gh workflow run deploy.yml --ref $BRANCH -f github_sha=$BRANCH

# the old way of doing this required a forced commit
# like the new way better
# PROJECT_NAME=$(basename $(git remote get-url origin) .git)
# OWNER=$(basename $(dirname $(git remote get-url origin)))
# if [ "$OWNER" == "NYUCCL" ] && [ "$PROJECT_NAME" == "smile" ] ; then
#     echo "Forcing an empty commit to trigger an initial deploy"
#     git commit --allow-empty -m "forcing a deploy"
# else
#     echo "Removing deploy script and generating initial deploy"
#     rm .github/workflows/docs-deploy.yml
#     git add .github/workflows/docs-deploy.yml
#     git commit -m "initial setup: removing docs deploy script"
# fi

# git push