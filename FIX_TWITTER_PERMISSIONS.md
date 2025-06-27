# Fix Twitter App Permissions

## Your Current Issue:
- Your app has **READ ONLY** permissions
- Bot needs **READ AND WRITE** permissions to post tweets

## Steps to Fix:

### 1. Go to Twitter Developer Portal
- Visit: https://developer.twitter.com
- Sign in with @DeployOnKlik account

### 2. Find Your App
- Click "Projects & Apps" → "Overview"
- Find the app with API Key: `gFXpOaSOUmGGWQ25S9sdTdWpw`

### 3. Update App Permissions
- Click on your app name
- Go to "User authentication settings" (or "App permissions")
- Click "Edit" or "Setup"
- Change from "Read" to **"Read and write"**
- Save changes

### 4. CRITICAL: Regenerate Tokens
**After changing permissions, you MUST regenerate:**
- Go to "Keys and tokens" tab
- Under "Authentication Tokens":
  - Click "Regenerate" for Access Token and Secret
  - Copy the new values

### 5. Update .env File
Replace in your .env:
```
TWITTER_ACCESS_TOKEN=<new_access_token>
TWITTER_ACCESS_TOKEN_SECRET=<new_access_token_secret>
```

### 6. Get Missing Client ID
While you're there, also get:
- Scroll down to "OAuth 2.0 Client ID and Client Secret"
- Copy the Client ID (looks like: `abc123def456...`)
- Update `TWITTER_CLIENT_ID=` in .env

### 7. Test Again
Run: `python test_twitter_api.py`

## If App Doesn't Exist:
You might need to create a new app with the correct permissions from the start. 