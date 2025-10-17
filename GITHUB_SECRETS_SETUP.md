# GitHub Secrets Setup Guide

## Required Secrets for Auto-Deployment

To enable automatic deployment via GitHub Actions, you need to configure these secrets in your repository:

### 1. Navigate to Repository Settings
- Go to your GitHub repository: https://github.com/pbertain/sportspuff-v6
- Click on **Settings** tab
- Click on **Secrets and variables** → **Actions**

### 2. Add Repository Secrets

Click **New repository secret** and add each of these:

#### SSH_PRIVATE_KEY_DEV
- **Name**: `SSH_PRIVATE_KEY_DEV`
- **Value**: The contents of your SSH private key file (`~/.ssh/keys/nirdclub__id_ed25519`)
- **Usage**: Used for development environment deployments

#### SSH_PRIVATE_KEY_PROD
- **Name**: `SSH_PRIVATE_KEY_PROD`
- **Value**: The contents of your SSH private key file (`~/.ssh/keys/nirdclub__id_ed25519`)
- **Usage**: Used for production environment deployments

> **Note**: This project does not use Ansible vault, so no vault password is needed.

### 3. How to Get Your SSH Private Key

Run this command to display your private key:
```bash
cat ~/.ssh/keys/nirdclub__id_ed25519
```

Copy the entire output (including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines) and paste it as the secret value.

### 4. Manual Deployment Command

For manual deployments, use this command format:
```bash
ansible-playbook \
    -i ansible/inventory \
    -u ansible \
    --private-key ~/.ssh/keys/nirdclub__id_ed25519 \
    ansible/playbooks/deploy.yml \
    -e target_env=dev  # or prod
```

### 5. Testing the Setup

After adding the secrets:
1. Make a small change to the `dev` branch
2. Push the change
3. Check the **Actions** tab in GitHub to see the deployment workflow run
4. Verify the deployment on your server

### 6. NGINX Configuration

Remember to configure NGINX to route traffic to the internal ports:
- Development: Route to `localhost:34181`
- Production: Route to `localhost:34180`

See `nginx.conf.example` for a reference configuration.
