# Twitter API Test Suite

This test suite validates Twitter API credentials and permissions for the DeployOnKlik bot.

## Quick Start

### Run full test suite:
```bash
python twitter_api_test.py
```

### Check posting status:
```bash
python twitter_api_test.py status
```

## What it tests:

1. **Credentials Check** - Validates all Twitter API credentials are present
2. **Authentication** - Verifies login works
3. **Permissions** - Checks app has read-write permissions
4. **Rate Limits** - Shows current rate limit status
5. **Account Tier** - Identifies if you have Free or Basic tier

## Common Issues & Fixes

### Issue: "No write permissions"
**Solution**: Update app permissions on developer.twitter.com
1. Go to your app settings
2. Change to "Read and Write" permissions
3. Regenerate Access Token & Secret
4. Update .env file

### Issue: "Rate limited (429)"
**Solution**: Check your tier and limits
- **Free tier**: 100 tweets/day, 1,500/month
- **Basic tier**: 3,000 tweets/month, no daily limit

### Issue: "Paying for Basic but getting Free tier"
**This is the current issue with @DeployOnKlik**

**Solution**: Contact Twitter Support
1. Use TWITTER_SUPPORT_ISSUE.md as template
2. Go to https://help.twitter.com/forms/platform
3. Explain you're paying $200/month but getting Free tier limits

**Evidence to provide**:
- You have 100 tweets/day limit (Free tier)
- You're paying for Basic ($200/month)
- Header shows: `x-user-limit-24hour-limit: 100`

## File Structure

- `twitter_api_test.py` - Main consolidated test suite
- `TWITTER_SUPPORT_ISSUE.md` - Template for contacting support
- `README.md` - This file 