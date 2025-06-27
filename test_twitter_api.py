#!/usr/bin/env python3
"""
Test Twitter API credentials and check rate limits
"""

import os
import sys
import tweepy
from datetime import datetime
from dotenv import load_dotenv

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
            access_token_secret=access_token_secret
        )
        
        # Get authenticated user info
        me = client.get_me()
        if me.data:
            print(f"✅ Authenticated as: @{me.data.username} (ID: {me.data.id})")
            print(f"   Name: {me.data.name}")
        else:
            print("❌ Failed to get user info")
            return False
            
        # Check rate limits
        print("\n📊 Checking Rate Limits...")
        
        # Try to get rate limit status using v1.1 API
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api = tweepy.API(auth)
        
        rate_limits = api.rate_limit_status()
        
        # Check tweet posting limits
        if 'statuses' in rate_limits['resources']:
            update_limits = rate_limits['resources']['statuses'].get('/statuses/update', {})
            if update_limits:
                remaining = update_limits.get('remaining', 0)
                limit = update_limits.get('limit', 0)
                reset = update_limits.get('reset', 0)
                reset_time = datetime.fromtimestamp(reset).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"\n🐦 Tweet Posting Limits:")
                print(f"   Limit: {limit} tweets per 15 min window")
                print(f"   Remaining: {remaining} tweets")
                print(f"   Resets at: {reset_time}")
                
                if remaining == 0:
                    print("   ⚠️  WARNING: No tweets remaining in current window!")
        
        # Test ability to post
        print("\n🧪 Testing Tweet Capability...")
        print("   Would you like to send a test tweet? (y/N): ", end='')
        
        if input().lower() == 'y':
            test_message = f"🧪 API Test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Please ignore"
            print(f"   Sending: {test_message}")
            
            try:
                response = client.create_tweet(text=test_message)
                if response.data:
                    tweet_id = response.data['id']
                    print(f"   ✅ SUCCESS! Tweet sent: https://twitter.com/i/status/{tweet_id}")
                    
                    # Delete the test tweet
                    print("   🗑️  Deleting test tweet...")
                    client.delete_tweet(tweet_id)
                    print("   ✅ Test tweet deleted")
                else:
                    print("   ❌ Failed to send tweet - no response data")
            except tweepy.TooManyRequests as e:
                print(f"   ❌ Rate limit error: {e}")
            except Exception as e:
                print(f"   ❌ Error sending tweet: {e}")
        
        # Get current user's recent tweets to check activity
        print("\n📜 Recent Tweet Activity:")
        try:
            # Get tweets from the last hour
            tweets = client.get_users_tweets(
                id=me.data.id,
                max_results=10,
                tweet_fields=['created_at']
            )
            
            if tweets.data:
                print(f"   Found {len(tweets.data)} recent tweets:")
                for i, tweet in enumerate(tweets.data[:5], 1):
                    created = tweet.created_at.strftime('%H:%M:%S')
                    text_preview = tweet.text[:50] + '...' if len(tweet.text) > 50 else tweet.text
                    print(f"   {i}. {created} - {text_preview}")
            else:
                print("   No recent tweets found")
                
        except Exception as e:
            print(f"   Error fetching tweets: {e}")
        
        print("\n✅ Twitter API is properly configured!")
        return True
        
    except tweepy.Unauthorized:
        print("❌ Authentication failed - check your credentials")
        print("   Make sure all 4 OAuth keys are correct")
        return False
    except tweepy.Forbidden:
        print("❌ Forbidden - your app might not have write permissions")
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
        
        # Check if there are any Twitter reply tracking issues
        # The bot might be tracking replies in memory that persist across restarts
        
        conn.close()
    except Exception as e:
        print(f"   Could not check deployment database: {e}")

if __name__ == "__main__":
    print("Starting Twitter API test...\n")
    
    # Test API
    success = test_twitter_api()
    
    # Check bot state
    check_bot_state()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Twitter API test completed successfully!")
        print("\n💡 If you're still getting rate limit errors in the bot:")
        print("   1. The bot might have stale data in memory")
        print("   2. Try restarting the bot completely")
        print("   3. The bot tracks replies internally - it might think it sent more than it did")
    else:
        print("❌ Twitter API test failed - check the errors above") 