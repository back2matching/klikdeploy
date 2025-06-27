#!/usr/bin/env python3
"""
Test Twitter API credentials and check rate limits
"""

import os
import sys
import tweepy
from datetime import datetime
from dotenv import load_dotenv
import requests
import json

def test_twitter_api():
    """Test Twitter API credentials and check what we can do"""
    load_dotenv()
    
    print("🐦 TWITTER API CREDENTIAL TEST")
    print("=" * 50)
    
    # Get credentials
    api_key = os.getenv('TWITTER_API_KEY')
    api_secret = os.getenv('TWITTER_API_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    
    # Check what we have
    print("📋 Credential Status:")
    print(f"   API Key: {'✅' if api_key else '❌'} {api_key[:10] + '...' if api_key else 'Missing'}")
    print(f"   API Secret: {'✅' if api_secret else '❌'} {api_secret[:10] + '...' if api_secret else 'Missing'}")
    print(f"   Access Token: {'✅' if access_token else '❌'} {access_token[:10] + '...' if access_token else 'Missing'}")
    print(f"   Access Token Secret: {'✅' if access_token_secret else '❌'} {access_token_secret[:10] + '...' if access_token_secret else 'Missing'}")
    print(f"   Bearer Token: {'✅' if bearer_token else '❌'} {bearer_token[:30] + '...' if bearer_token else 'Missing'}")
    
    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("\n❌ Missing OAuth 1.0a credentials needed for posting!")
        return False
    
    print("\n🔑 Testing OAuth 1.0a Authentication...")
    
    try:
        # Create client with OAuth 1.0a
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=False  # Don't wait, we want to see the errors
        )
        
        # Get authenticated user info
        me = client.get_me(user_fields=['created_at', 'verified'])
        if me.data:
            print(f"✅ Authenticated as: @{me.data.username} (ID: {me.data.id})")
            print(f"   Name: {me.data.name}")
            print(f"   Account created: {me.data.created_at}")
            print(f"   Verified: {'✅' if me.data.verified else '❌'}")
        else:
            print("❌ Failed to get user info")
            return False
            
        # Check API tier using direct API call with OAuth 1.0a
        print("\n🔍 Checking Twitter API Access Level...")
        
        # First, try v1.1 rate limit endpoint
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api = tweepy.API(auth, wait_on_rate_limit=False)
        
        try:
            rate_limits = api.rate_limit_status()
            
            # Check various endpoints to determine tier
            statuses_update = rate_limits['resources']['statuses'].get('/statuses/update', {})
            statuses_timeline = rate_limits['resources']['statuses'].get('/statuses/user_timeline', {})
            
            print("\n📊 Rate Limits Detected:")
            
            # Tweet posting limits
            if statuses_update:
                limit = statuses_update.get('limit', 0)
                remaining = statuses_update.get('remaining', 0)
                reset = statuses_update.get('reset', 0)
                reset_time = datetime.fromtimestamp(reset).strftime('%H:%M:%S')
                
                print(f"\n🐦 Tweet Posting (/statuses/update):")
                print(f"   Limit: {limit} tweets per 15 min")
                print(f"   Remaining: {remaining} tweets")
                print(f"   Resets at: {reset_time}")
                
                # Determine tier based on limits
                if limit == 0:
                    print(f"   ⚠️  NO POSTING ACCESS - App may be restricted!")
                elif limit <= 300:
                    print(f"   📱 Tier: FREE or BASIC (limit suggests restricted access)")
                elif limit <= 1500:
                    print(f"   💎 Tier: Likely BASIC tier")
                else:
                    print(f"   🚀 Tier: PRO or higher")
                
                if remaining == 0:
                    print("   ❌ RATE LIMIT HIT! No tweets remaining!")
            
            # Check timeline endpoint for comparison
            if statuses_timeline:
                print(f"\n📜 Timeline Reading (/statuses/user_timeline):")
                print(f"   Limit: {statuses_timeline.get('limit', 0)} per 15 min")
                print(f"   Remaining: {statuses_timeline.get('remaining', 0)}")
            
            # Check app-level vs user-level limits
            print("\n🔐 Access Type:")
            if 'application' in rate_limits['rate_limit_context']:
                print("   Type: Application-level access")
            else:
                print("   Type: User-level access")
                
        except tweepy.errors.TooManyRequests as e:
            print("❌ Rate limit hit while checking limits!")
            print(f"   Error: {e}")
            
        # Test actual posting capability
        print("\n🧪 Testing Tweet Capability...")
        
        # First check if we can even attempt to post
        try:
            # Try a simple timeline read first
            tweets = client.get_users_tweets(id=me.data.id, max_results=5)
            print("✅ Can read tweets successfully")
        except Exception as e:
            print(f"❌ Cannot even read tweets: {e}")
        
        print("\n💡 DIAGNOSIS:")
        print("=" * 50)
        
        # Provide clear diagnosis
        if statuses_update and statuses_update.get('remaining', 0) == 0:
            print("❌ YOU ARE RATE LIMITED!")
            print("   The Twitter API is returning 429 because you've hit the limit.")
            print("   This is NOT a bot issue - it's Twitter's rate limiting.")
            print(f"   Wait until {reset_time} for the limit to reset.")
        else:
            print("🤔 Rate limits show availability, but you're still getting 429 errors.")
            print("   Possible causes:")
            print("   1. App-level rate limit (shared across all users of the app)")
            print("   2. Account restrictions or suspicious activity flags")
            print("   3. API tier mismatch (using wrong tier endpoints)")
        
        print("\n💰 YOUR TWITTER API TIER:")
        print("=" * 50)
        
        # Determine actual tier
        if statuses_update:
            limit = statuses_update.get('limit', 0)
        else:
            limit = 0
            
        if limit == 0:
            print("🚫 NO WRITE ACCESS - Your app cannot post tweets!")
            print("   → Check app permissions at developer.twitter.com")
            print("   → Make sure app has 'Read and Write' permissions")
        elif limit <= 300:
            print("🆓 FREE TIER (or restricted)")
            print("   → Limited to ~300 posts per 15 minutes")
            print("   → May need to upgrade for production use")
        elif limit <= 1500:
            print("💎 BASIC TIER ($200/month)")
            print("   → Up to 1,500 posts per 15 minutes")
            print("   → 50,000 posts per month app-level")
            print("   → Should be sufficient for your bot")
        else:
            print("🚀 PRO TIER or higher")
            print("   → High rate limits detected")
        
        print("\n🔧 SOLUTIONS:")
        print("=" * 50)
        
        if statuses_update.get('remaining', 0) == 0:
            print("1. IMMEDIATE: Wait for rate limit reset")
            print(f"   → Resets at {reset_time}")
            print("   → Then restart your bot")
        
        print("\n2. CHECK APP SETTINGS:")
        print("   → Go to developer.twitter.com")
        print("   → Verify app has 'Read and Write' permissions")
        print("   → Check if app is suspended or restricted")
        
        print("\n3. CONSIDER YOUR OPTIONS:")
        print("   → Create a NEW app (fresh rate limits)")
        print("   → Upgrade to Basic tier ($200/month) if on Free")
        print("   → Use multiple apps and rotate between them")
        
        print("\n4. BOT CONFIGURATION:")
        print("   → Your bot is configured for 60 replies/15min")
        print("   → This assumes Basic tier or higher")
        print("   → For Free tier, reduce to ~15-20 replies/15min")
        
        # Test if we can check v2 API limits
        print("\n📊 Checking v2 API access...")
        try:
            # Make a simple v2 API call
            user = client.get_user(username='twitter')
            if user.data:
                print("✅ Twitter API v2 access confirmed")
        except tweepy.errors.TooManyRequests:
            print("❌ v2 API also rate limited")
        except Exception as e:
            print(f"❌ v2 API error: {e}")
        
        return True
        
    except tweepy.Unauthorized:
        print("❌ Authentication failed - check your credentials")
        print("   Make sure all 4 OAuth keys are correct")
        return False
    except tweepy.Forbidden as e:
        print("❌ Forbidden - your app might not have write permissions")
        print(f"   Error: {e}")
        print("   Check your app permissions at developer.twitter.com")
        return False
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False

def check_bot_state():
    """Check the bot's internal rate limit tracking"""
    print("\n🤖 Checking Bot's Rate Limit State...")
    
    # Check if there's a SQLite database with deployment history
    import sqlite3
    from datetime import datetime, timedelta
    
    try:
        conn = sqlite3.connect('deployments.db')
        cursor = conn.cursor()
        
        # Check recent deployments
        cursor.execute("""
            SELECT COUNT(*) FROM deployments 
            WHERE datetime(requested_at) > datetime('now', '-1 hour')
        """)
        recent_deploys = cursor.fetchone()[0]
        
        print(f"   Recent deployments (last hour): {recent_deploys}")
        
        # Check last few deployment attempts
        cursor.execute("""
            SELECT username, requested_at, status, token_symbol
            FROM deployments 
            ORDER BY requested_at DESC
            LIMIT 5
        """)
        
        recent = cursor.fetchall()
        if recent:
            print("\n   Last 5 deployment attempts:")
            for user, req_time, status, symbol in recent:
                print(f"   • @{user} - ${symbol} - {status} - {req_time}")
        
        conn.close()
    except Exception as e:
        print(f"   Could not check deployment database: {e}")

def quick_rate_limit_check():
    """Quick check of current rate limit status"""
    load_dotenv()
    
    api_key = os.getenv('TWITTER_API_KEY')
    api_secret = os.getenv('TWITTER_API_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    
    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("❌ Missing credentials")
        return
        
    print("\n⚡ QUICK RATE LIMIT CHECK")
    print("=" * 30)
    
    try:
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api = tweepy.API(auth, wait_on_rate_limit=False)
        
        # Just check the posting endpoint
        rate_limits = api.rate_limit_status(resources=['statuses'])
        update_limits = rate_limits['resources']['statuses']['/statuses/update']
        
        remaining = update_limits['remaining']
        limit = update_limits['limit']
        reset_timestamp = update_limits['reset']
        reset_time = datetime.fromtimestamp(reset_timestamp)
        time_until_reset = (reset_time - datetime.now()).total_seconds()
        
        print(f"Tweet posting limit: {remaining}/{limit}")
        
        if remaining == 0:
            print(f"❌ RATE LIMITED! Resets in {int(time_until_reset/60)} minutes")
        else:
            print(f"✅ Can post {remaining} more tweets")
            
        print(f"Reset time: {reset_time.strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting Twitter API test...\n")
    
    # Quick rate limit check first
    quick_rate_limit_check()
    
    print("\n" + "=" * 50 + "\n")
    
    # Full test
    success = test_twitter_api()
    
    # Check bot state
    check_bot_state()
    
    print("\n" + "=" * 50)
    print("�� Test complete!") 