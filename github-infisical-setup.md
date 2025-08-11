# GitHub Actions + Infisical Secrets Sync Setup

This guide explains how to configure GitHub Actions to work with your self-hosted Infisical instance using GitHub's built-in secrets sync functionality.

## Overview

The repository uses Infisical's GitHub integration to automatically sync secrets from your Infisical project to GitHub repository/environment secrets. This provides a seamless CI/CD experience without needing additional actions or authentication steps.

## Prerequisites

1. **Self-hosted Infisical instance** running and accessible
2. **Machine Identity** created in your Infisical project
3. **GitHub repository** with proper permissions
4. **Secrets configured** in your Infisical project

## Step 1: Configure Infisical GitHub Integration

1. Navigate to your Infisical project
2. Go to **Integrations** tab
3. Click on the **GitHub** tile
4. Choose **GitHub App** as the authentication method (recommended)
5. Click **Connect to GitHub** 
6. Install and authorize the Infisical GitHub App for your repository
7. Configure the integration:
   - **Repository**: Select your target repository
   - **Sync Level**: Choose Repository or Environment level
   - **Environment Mapping**: Map Infisical environments to GitHub environments
   - **Secret Path**: Usually `/` (root path)

## Step 2: Verify Secrets Sync

Once configured, Infisical will automatically sync your secrets to GitHub:

### Check Repository Secrets
1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Verify that your secrets appear in the **Repository secrets** section

### Expected Synced Secrets
The following secrets should be automatically synced from Infisical:

| GitHub Secret Name | Infisical Secret Name | Description |
|-------------------|----------------------|-------------|
| `READWISE_API_KEY` | `READWISE_API_KEY` | Readwise API key |
| `GLASP_API_KEY` | `GLASP_API_KEY` | Glasp API key |
| `RSS_FEEDS` | `RSS_FEEDS` | RSS feed URLs |
| `BUTTONDOWN_API_KEY` | `BUTTONDOWN_API_KEY` | Buttondown API key |
| `OPENROUTER_API_KEY` | `OPENROUTER_API_KEY` | OpenRouter API key |
| `UNSPLASH_API_KEY` | `UNSPLASH_API_KEY` | Unsplash API key |

## Step 3: Configure Infisical Project Secrets

In your Infisical project, ensure these secrets are configured for each environment:

### Development Environment (`dev`)
- `READWISE_API_KEY`
- `GLASP_API_KEY`
- `RSS_FEEDS`
- `BUTTONDOWN_API_KEY`
- `OPENROUTER_API_KEY`
- `UNSPLASH_API_KEY`

### Production Environment (`prod`)
- Same secrets as dev, but with production values

## Step 3: Workflow Configuration

The `.github/workflows/ci.yml` file is configured to use the synced secrets:

### Test Job
- Accesses secrets directly via `${{ secrets.SECRET_NAME }}`
- No additional authentication or setup required
- Secrets are automatically available in the workflow environment

### Deploy Job
- Uses the same synced secrets for production deployment
- Only runs on `main` branch pushes
- Uses the `production` environment for additional security

## Step 5: Environment Protection (Recommended)

For production deployments, configure environment protection:

1. Go to **Settings** → **Environments**
2. Create environment named `production`
3. Configure protection rules:
   - **Required reviewers**: Add team members
   - **Wait timer**: Optional delay before deployment
   - **Branch restrictions**: Limit to `main` branch

## Alternative Integration Methods

### Method 1: GitHub App Integration (Recommended for Sync)

If you prefer to sync secrets directly to GitHub secrets:

1. In Infisical, go to **Integrations**
2. Select **GitHub** tile
3. Choose **GitHub App** authentication
4. Install and authorize the GitHub App
5. Configure sync settings:
   - Select repository or organization
   - Choose environment level (Repository/Environment)
   - Map Infisical environments to GitHub environments

### Method 2: OAuth Integration

Similar to GitHub App but uses OAuth for authentication.

## Troubleshooting

### Common Issues

**1. "Secrets not syncing"**
- Verify the GitHub App is properly installed and authorized
- Check if the integration is configured for the correct repository
- Ensure the Infisical project has the required secrets

**2. "Integration disconnected"**
- Re-authorize the GitHub App in your Infisical integrations
- Check if repository permissions have changed
- Verify the GitHub App hasn't been uninstalled

**3. "Secrets not available in workflow"**
- Confirm secrets appear in GitHub repository settings
- Check if secret names match exactly (case-sensitive)
- Verify the workflow is accessing secrets correctly with `${{ secrets.SECRET_NAME }}`

### Debug Mode

To debug synced secrets, add to your workflow:

```yaml
- name: Debug synced secrets
  run: |
    echo "Checking synced secrets availability:"
    echo "READWISE_API_KEY: ${{ secrets.READWISE_API_KEY != '' && 'Set' || 'Not set' }}"
    echo "GLASP_API_KEY: ${{ secrets.GLASP_API_KEY != '' && 'Set' || 'Not set' }}"
    echo "RSS_FEEDS: ${{ secrets.RSS_FEEDS != '' && 'Set' || 'Not set' }}"
    echo "BUTTONDOWN_API_KEY: ${{ secrets.BUTTONDOWN_API_KEY != '' && 'Set' || 'Not set' }}"
    echo "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY != '' && 'Set' || 'Not set' }}"
    echo "UNSPLASH_API_KEY: ${{ secrets.UNSPLASH_API_KEY != '' && 'Set' || 'Not set' }}"
```

## Security Best Practices

1. **Environment Separation**: Use different Infisical environments for dev/prod
2. **Repository Access**: Limit GitHub App permissions to specific repositories
3. **Secret Rotation**: Regularly rotate secrets in Infisical (auto-syncs to GitHub)
4. **Audit Logs**: Monitor both Infisical and GitHub access logs
5. **Environment Protection**: Use GitHub environment protection for production deployments

## Workflow Customization

The workflow can be customized by modifying `.github/workflows/ci.yml`:

- **Additional secrets**: Add new secrets to the env sections as they're synced
- **Environment-specific secrets**: Use GitHub environments for different secret sets
- **Conditional deployment**: Modify the deploy job conditions
- **Multi-environment**: Configure different Infisical environment mappings

## Next Steps

1. Test the setup by pushing a commit to a branch
2. Check the Actions tab to verify secrets are loaded
3. Configure environment protection for production
4. Set up monitoring for secret access and usage