# Why GitHub/Git Commands Hang

## Common Causes

1. **Network Issues**
   - Slow or unstable internet connection
   - Firewall/proxy blocking git operations
   - GitHub rate limiting

2. **Large Repository Operations**
   - Fetching large amounts of data
   - Checking out large branches
   - History operations on big repos

3. **Authentication Issues**
   - SSH key not properly configured
   - Credential prompts waiting for input
   - Token expiration

4. **Repository State**
   - Corrupted git index
   - Large number of untracked files
   - Merge conflicts waiting for resolution

5. **Tool Limitations**
   - Some git commands don't have timeouts
   - Interactive prompts that can't be answered
   - Commands that wait for user input

## Solutions

1. **Use GitHub CLI (`gh`) instead of direct git**
   ```bash
   gh pr create --base dev --head main --title "Sync main to dev"
   ```

2. **Use GitHub Web Interface**
   - Create PRs via web UI
   - Merge via web UI
   - Avoids git command issues

3. **Add Timeouts to Commands**
   ```bash
   timeout 30 git fetch origin
   ```

4. **Use Shallow Clones**
   ```bash
   git fetch --depth=1 origin
   ```

5. **Check Network First**
   ```bash
   ping github.com
   curl -I https://github.com
   ```

## For This Project

The best approach is to:
1. Use GitHub web interface for PRs/merges
2. Use the provided scripts that have better error handling
3. Manually run git commands in your terminal (not through the tool)
4. Check GitHub Actions status via web interface


