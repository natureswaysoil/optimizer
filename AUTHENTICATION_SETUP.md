# Authentication Setup for Password-Free Access

This guide shows you how to set up authentication so you don't need to enter your password when accessing the dashboard or running commands.

## For Dashboard Access (No Password Required)

The deployed dashboard on Cloud Run is **publicly accessible** by default - no password needed!

Your dashboard URL: `https://amazon-ppc-dashboard-xxxxx-uc.a.run.app`

Anyone with the URL can access it. If you want to restrict access, see the "Optional: Restrict Access" section below.

## For Git Operations (No Password)

If you're being asked for passwords when using git, use one of these methods:

### Method 1: Cloud Shell (Recommended - No Setup Needed)

Google Cloud Shell has authentication built-in. Just use it!

```bash
# In Cloud Shell, you're already authenticated
# No passwords or tokens needed
git clone https://github.com/natureswaysoil/optimizer.git
cd optimizer
git checkout copilot/retrieve-data-and-build-dashboard
```

### Method 2: GitHub Personal Access Token (For Local Terminal)

If working from your local machine:

1. **Create a token:**
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Give it a name like "Optimizer Access"
   - Select scopes: `repo` (full control)
   - Click "Generate token"
   - **Copy the token immediately** (you won't see it again)

2. **Use the token instead of password:**
   ```bash
   # When git asks for password, paste your token instead
   git clone https://github.com/natureswaysoil/optimizer.git
   ```

3. **Save the token permanently:**
   ```bash
   # Configure git to remember credentials
   git config --global credential.helper store
   
   # Next time you enter the token, it will be saved
   ```

### Method 3: SSH Keys (Most Secure)

1. **Generate SSH key:**
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   # Press Enter to accept default location
   # Enter passphrase (optional, can leave empty for no password)
   ```

2. **Add SSH key to GitHub:**
   ```bash
   # Copy your public key
   cat ~/.ssh/id_ed25519.pub
   
   # Go to https://github.com/settings/keys
   # Click "New SSH key"
   # Paste the key and save
   ```

3. **Use SSH URLs:**
   ```bash
   git clone git@github.com:natureswaysoil/optimizer.git
   # No password ever needed!
   ```

## For GCP Authentication (No Password)

### In Cloud Shell
Already authenticated automatically - no setup needed!

### In Local Terminal
```bash
# One-time setup - opens browser for login
gcloud auth login

# For application default credentials
gcloud auth application-default login

# Now all gcloud commands work without passwords
```

## Optional: Restrict Dashboard Access

If you want to require authentication for your dashboard:

### Option 1: Require Google Account Login

```bash
# Remove public access
gcloud run services remove-iam-policy-binding amazon-ppc-dashboard \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"

# Add specific users
gcloud run services add-iam-policy-binding amazon-ppc-dashboard \
  --region=us-central1 \
  --member="user:someone@example.com" \
  --role="roles/run.invoker"
```

Users will need to authenticate with their Google account when accessing the URL.

### Option 2: Use Identity-Aware Proxy (IAP)

For enterprise-grade authentication with your organization's identity provider.

See: https://cloud.google.com/iap/docs/enabling-cloud-run

### Option 3: Add Basic Auth to Dashboard

Modify `dashboard.py` to add simple username/password:

```python
import streamlit as st

# Add at the top of dashboard.py
def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == "your-secret-password":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

if check_password():
    # Rest of your dashboard code here
    st.title("Amazon PPC Dashboard")
    # ... rest of dashboard code
```

## Recommended Setup

**For easiest password-free experience:**

1. ✅ Use **Cloud Shell** for all git and gcloud operations
2. ✅ Keep dashboard **publicly accessible** (it's just analytics)
3. ✅ Store sensitive credentials in **Google Secret Manager** (already configured)

**That's it!** No passwords needed anywhere.

## Summary

| What | Solution | Password Needed? |
|------|----------|------------------|
| View Dashboard | Use Cloud Run URL | ❌ No |
| Git Clone/Push (Cloud Shell) | Already authenticated | ❌ No |
| Git Clone/Push (Local) | Use SSH keys or token | ⚠️ One-time setup |
| GCP Commands (Cloud Shell) | Already authenticated | ❌ No |
| GCP Commands (Local) | `gcloud auth login` | ⚠️ One-time setup |
| BigQuery Data | Service account | ❌ No |
| Amazon Credentials | Secret Manager | ❌ No |

**Bottom line:** Use Cloud Shell and you'll never need to enter a password!
