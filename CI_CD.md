# CI/CD

This folder has a GitHub Actions pipeline with three stages:

- `CI`: runs on pull requests and pushes to `dev`, `main`, and `master`
- `Deploy Dev`: runs after CI when code is pushed to `dev`
- `Deploy Prod`: runs after CI when code is pushed to `main` or `master`

## What CI Checks

The CI job:

- installs the Flask dashboard dependencies from `03_web_browser/requirements.txt`
- compiles Python files in the pipeline folders to catch syntax errors
- imports the Flask app and checks that key routes exist
- validates the resume JSON/template inputs exist and the JSON parses

## Branch Flow

Use this branch flow:

```bash
git checkout -b dev
git push origin dev
```

Pushes to `dev` trigger the development environment. Merging `dev` into `main` or `master` triggers the production environment.

## Deploy Hooks

The deploy jobs call:

```bash
./scripts/deploy.sh dev
./scripts/deploy.sh prod
```

Right now these hooks are safe placeholders. Add your real deployment commands there, such as:

- copying files to a server with `rsync`
- rebuilding a Docker image
- restarting a `systemd` service
- deploying to a cloud host

## GitHub Environments

Create these environments in GitHub repository settings:

- `development`
- `production`

For production, enable required reviewers if you want manual approval before the production deploy runs.
