# AgentSH Release & Distribution Setup

This document describes how to set up the complete release and distribution pipeline for AgentSH.

## Overview

The release pipeline automatically:
1. Builds and tests the Python package
2. Publishes to PyPI
3. Builds and pushes Docker images (multi-arch)
4. Updates the Homebrew tap
5. Creates a GitHub Release with changelog

## Required Accounts

### 1. PyPI (Required)

**Purpose**: Python package distribution (`pip install agentsh`)

**Setup**:
1. Create account at https://pypi.org/account/register/
2. Verify email address
3. Enable 2FA (required for new projects)

**Two options for authentication**:

#### Option A: Trusted Publishing (Recommended)
No token needed! PyPI trusts GitHub Actions directly.

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - PyPI Project Name: `agentsh`
   - Owner: `agentsh` (your GitHub org/user)
   - Repository: `agentsh`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

3. In your GitHub repo, create an environment:
   - Go to Settings → Environments → New environment
   - Name: `pypi`
   - Add protection rules if desired (e.g., required reviewers)

4. Set `USE_TRUSTED_PUBLISHING=true` in the workflow env

#### Option B: API Token
1. Go to https://pypi.org/manage/account/token/
2. Create a new API token (scope: Entire account, or project-specific after first upload)
3. Add to GitHub Secrets as `PYPI_API_TOKEN`

---

### 2. GitHub Container Registry (Automatic)

**Purpose**: Docker image hosting (`ghcr.io/agentsh/agentsh`)

**Setup**: No additional setup needed! Uses the automatic `GITHUB_TOKEN`.

Images will be available at:
- `ghcr.io/agentsh/agentsh:latest`
- `ghcr.io/agentsh/agentsh:0.1.0`
- `ghcr.io/agentsh/agentsh:alpine`

---

### 3. Docker Hub (Optional)

**Purpose**: Additional Docker distribution (`docker pull agentsh/agentsh`)

**Setup**:
1. Create account at https://hub.docker.com/signup
2. Create organization or use personal account
3. Create repository: `agentsh/agentsh`
4. Create access token: Account Settings → Security → New Access Token
5. Add to GitHub Secrets:
   - `DOCKERHUB_USERNAME`: Your Docker Hub username
   - `DOCKERHUB_TOKEN`: The access token

---

### 4. Homebrew Tap (Required for macOS)

**Purpose**: macOS package distribution (`brew install agentsh/tap/agentsh`)

**Setup**:

1. **Create the tap repository**:
   ```bash
   # Create new repo: agentsh/homebrew-tap
   gh repo create agentsh/homebrew-tap --public --description "Homebrew tap for AgentSH"
   ```

2. **Initialize the tap**:
   ```bash
   git clone https://github.com/agentsh/homebrew-tap
   cd homebrew-tap
   mkdir -p Formula .github/workflows

   # Copy the formula template
   cp /path/to/agentsh/packaging/homebrew/agentsh.rb Formula/

   # Copy the update workflow
   cp /path/to/agentsh/.github/homebrew-tap/update-formula.yml .github/workflows/

   # Create README
   cat > README.md << 'EOF'
   # Homebrew Tap for AgentSH

   ## Installation

   ```bash
   brew tap agentsh/tap
   brew install agentsh
   ```

   ## Updating

   ```bash
   brew update
   brew upgrade agentsh
   ```
   EOF

   git add .
   git commit -m "Initial tap setup"
   git push
   ```

3. **Create Personal Access Token for cross-repo dispatch**:
   - Go to https://github.com/settings/tokens
   - Generate new token (classic) with `repo` scope
   - Add to main repo secrets as `HOMEBREW_TAP_TOKEN`

---

### 5. Codecov (Optional)

**Purpose**: Test coverage reporting and badges

**Setup**:
1. Sign up at https://codecov.io with GitHub
2. Add your repository
3. Copy the upload token
4. Add to GitHub Secrets as `CODECOV_TOKEN` (if not using GitHub App integration)

---

## GitHub Repository Secrets Summary

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `PYPI_API_TOKEN` | Yes* | PyPI API token (*not needed if using Trusted Publishing) |
| `HOMEBREW_TAP_TOKEN` | Yes | PAT with repo scope for homebrew-tap |
| `DOCKERHUB_USERNAME` | No | Docker Hub username |
| `DOCKERHUB_TOKEN` | No | Docker Hub access token |
| `CODECOV_TOKEN` | No | Codecov upload token |

---

## GitHub Environments

Create these environments in Settings → Environments:

### `pypi`
- Used for PyPI publishing
- Optional: Add required reviewers for production releases
- Optional: Add deployment branch rules (only `main` or tags)

---

## Release Process

### Automatic Release (Recommended)

1. Update version in `pyproject.toml`:
   ```python
   version = "0.2.0"
   ```

2. Commit and push:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.2.0"
   git push
   ```

3. Create and push tag:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

4. The workflow automatically:
   - Runs tests
   - Publishes to PyPI
   - Builds Docker images
   - Updates Homebrew tap
   - Creates GitHub Release

### Manual Release

Use the workflow dispatch:
1. Go to Actions → Release → Run workflow
2. Enter the version (e.g., `0.2.0`)
3. Click "Run workflow"

---

## Verifying the Release

After release, verify each channel:

```bash
# PyPI
pip install agentsh==0.2.0 --dry-run

# Docker (GHCR)
docker pull ghcr.io/agentsh/agentsh:0.2.0

# Docker Hub (if configured)
docker pull agentsh/agentsh:0.2.0

# Homebrew (after tap updates)
brew update
brew info agentsh/tap/agentsh

# GitHub Release
gh release view v0.2.0
```

---

## Installer Hosting (get.agentsh.dev)

For the curl installer to work, you need to host `scripts/install.sh`.

### Option A: GitHub Pages (Free)

1. Create repo `agentsh/get.agentsh.dev`
2. Copy `scripts/install.sh` to `index.html` (or use redirect)
3. Enable GitHub Pages
4. Configure custom domain

### Option B: Simple Redirect

Configure your domain to redirect:
- `https://get.agentsh.dev` → `https://raw.githubusercontent.com/agentsh/agentsh/main/scripts/install.sh`
- `https://get.agentsh.dev/windows` → `https://raw.githubusercontent.com/agentsh/agentsh/main/packaging/windows/install.ps1`

### Option C: Cloudflare Worker

```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)

  if (url.pathname === '/windows') {
    return fetch('https://raw.githubusercontent.com/agentsh/agentsh/main/packaging/windows/install.ps1')
  }

  return fetch('https://raw.githubusercontent.com/agentsh/agentsh/main/scripts/install.sh')
}
```

---

## Package Repository Hosting (pkg.agentsh.dev)

For APT/DNF repositories (advanced):

### Option A: Use GitHub Releases

The current installer falls back to pip when native packages aren't available.
This is sufficient for most users.

### Option B: Packagecloud.io

1. Create account at https://packagecloud.io
2. Create repository
3. Upload packages from CI:
   ```yaml
   - name: Push to Packagecloud
     uses: computology/packagecloud-github-action@v0.6
     with:
       package-name: dist/*.deb
       packagecloud-username: agentsh
       packagecloud-reponame: agentsh
       packagecloud-distro: ubuntu/jammy
       packagecloud-token: ${{ secrets.PACKAGECLOUD_TOKEN }}
   ```

### Option C: Self-hosted with Aptly/Createrepo

Requires your own server infrastructure.

---

## First Release Checklist

Before your first release:

- [ ] PyPI account created and verified
- [ ] PyPI Trusted Publishing configured OR API token created
- [ ] `pypi` environment created in GitHub
- [ ] Homebrew tap repository created
- [ ] `HOMEBREW_TAP_TOKEN` secret added
- [ ] (Optional) Docker Hub account and secrets
- [ ] (Optional) Codecov integration
- [ ] Version in `pyproject.toml` is correct
- [ ] CHANGELOG.md updated

Then create your first tag:
```bash
git tag v0.1.0
git push origin v0.1.0
```

---

## Troubleshooting

### PyPI Upload Fails

- Check if package name is available
- Verify API token has correct scope
- For Trusted Publishing, verify environment name matches

### Docker Build Fails

- Check Dockerfile syntax
- Verify base image availability
- Check for architecture-specific issues

### Homebrew Tap Not Updating

- Verify `HOMEBREW_TAP_TOKEN` has repo scope
- Check homebrew-tap repository exists
- Verify workflow file is in correct location

### Release Stuck

- Check job dependencies in workflow
- Verify all secrets are configured
- Check GitHub Actions logs for specific errors
