#!/usr/bin/env python3
"""
Consolidated Twitter API Test Suite
Combines all essential tests in one file
"""

import os
import sys
import tweepy
import requests
import json
from datetime import datetime
from requests_oauthlib import OAuth1
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

class TwitterAPITest:
    def __init__(self):
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        
    def run_all_tests(self):
        """Run all tests"""
        print("🔍 TWITTER API TEST SUITE\n")
        print("1. Credential Check")
        self.check_credentials()
        
        print("\n2. Authentication Test")
        self.test_authentication()
        
        print("\n3. Permission Check")
        self.check_permissions()
        
        print("\n4. App vs User Limits Explanation")
        self.check_app_vs_user_limits()
        
        print("\n5. Rate Limit Status")
        self.check_rate_limits()
        
        print("\n6. Account Tier Check")
        self.check_account_tier()
        
        print("\n7. Tweet Endpoint Rate Limit")
        self.check_tweet_endpoint_limits()
        
    def check_credentials(self):
        """Check if all credentials exist"""
        creds = {
            "API_KEY": self.api_key,
            "API_SECRET": self.api_secret,
            "ACCESS_TOKEN": self.access_token,
            "ACCESS_TOKEN_SECRET": self.access_token_secret,
            "BEARER_TOKEN": self.bearer_token
        }
        
        all_present = True
        for name, value in creds.items():
            if value:
                print(f"✅ {name}: {value[:20]}...")
            else:
                print(f"❌ {name}: MISSING")
                all_present = False
                
        return all_present
        
    def test_authentication(self):
        """Test authentication"""
        try:
            client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            
            me = client.get_me(user_fields=['public_metrics'])
            if me.data:
                print(f"✅ Authenticated as: @{me.data.username}")
                print(f"   Followers: {me.data.public_metrics.get('followers_count', 0):,}")
                return True
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
            
    def check_permissions(self):
        """Check API permissions"""
        try:
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.get("https://api.twitter.com/1.1/account/verify_credentials.json", auth=auth)
            
            if 'x-access-level' in response.headers:
                access_level = response.headers['x-access-level']
                print(f"✅ Access level: {access_level}")
                
                if access_level == 'read-write':
                    print("   → App has read-write permissions")
                else:
                    print("   → App has read-only permissions")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            
    def check_rate_limits(self):
        """Check current rate limits"""
        try:
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": "Test"},
                auth=auth
            )
            
            if response.status_code == 429:
                print("❌ Rate limited (429)")
                
                # Show ALL rate limit headers
                print("\n   All rate limit headers:")
                for header, value in response.headers.items():
                    if 'limit' in header.lower() or 'rate' in header.lower():
                        print(f"   • {header}: {value}")
                
                if 'x-user-limit-24hour-remaining' in response.headers:
                    remaining = response.headers.get('x-user-limit-24hour-remaining', '0')
                    limit = response.headers.get('x-user-limit-24hour-limit', '0')
                    print(f"\n   Daily limit: {remaining}/{limit}")
                    
                    if 'x-user-limit-24hour-reset' in response.headers:
                        reset_time = datetime.fromtimestamp(int(response.headers['x-user-limit-24hour-reset']))
                        hours_until_reset = (reset_time - datetime.now()).total_seconds() / 3600
                        print(f"   Resets in: {hours_until_reset:.1f} hours")
                        
            elif response.status_code == 201:
                print("✅ Can post tweets!")
                # Delete the test tweet
                tweet_data = response.json()
                if 'data' in tweet_data:
                    tweet_id = tweet_data['data']['id']
                    requests.delete(f"https://api.twitter.com/2/tweets/{tweet_id}", auth=auth)
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            
    def check_account_tier(self):
        """Check account tier based on limits"""
        try:
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": "Test"},
                auth=auth
            )
            
            if 'x-user-limit-24hour-limit' in response.headers:
                daily_limit = int(response.headers.get('x-user-limit-24hour-limit', '0'))
                
                if daily_limit == 100:
                    print("❌ Account Tier: FREE (100 tweets/day)")
                    print("   You're paying for Basic but getting Free tier!")
                elif daily_limit >= 3000:
                    print("✅ Account Tier: BASIC or higher")
                else:
                    print(f"🤔 Account Tier: Unknown (limit: {daily_limit})")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            
    def check_tweet_endpoint_limits(self):
        """Check specific /2/tweets endpoint rate limits"""
        print("Checking /2/tweets endpoint specifically...")
        
        try:
            # Use tweepy to check rate limits
            client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            
            # Try to get rate limit status using v1.1 endpoint
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.get(
                "https://api.twitter.com/1.1/application/rate_limit_status.json?resources=statuses",
                auth=auth
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'resources' in data and 'statuses' in data['resources']:
                    statuses = data['resources']['statuses']
                    print("\n   v1.1 Status endpoints:")
                    for endpoint, info in statuses.items():
                        if info['remaining'] < info['limit']:
                            reset_time = datetime.fromtimestamp(info['reset'])
                            print(f"   • {endpoint}: {info['remaining']}/{info['limit']} (resets {reset_time.strftime('%H:%M')})")
            
            # Also check v2 directly
            print("\n   Attempting test post to check v2 limits...")
            test_response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": f"API Test {int(time.time())}"},
                auth=auth
            )
            
            print(f"\n   Response status: {test_response.status_code}")
            print(f"   Response text: {test_response.text[:200]}...")
            
            # Print ALL headers for debugging
            print("\n   Response headers:")
            for header, value in sorted(test_response.headers.items()):
                print(f"   • {header}: {value}")
                
        except Exception as e:
            print(f"❌ Error checking tweet endpoint: {e}")
            
    def check_app_vs_user_limits(self):
        """Check both app-level and user-level limits to show the difference"""
        print("🔍 APP vs USER RATE LIMITS EXPLAINED\n")
        
        print("📱 APP-LEVEL LIMITS (Bearer Token only):")
        print("   • Used for reading public data")
        print("   • Higher limits typically")
        print("   • Cannot post tweets")
        
        # Check app-level limits using bearer token
        try:
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            response = requests.get(
                "https://api.twitter.com/2/users/by/username/twitter",
                headers=headers
            )
            
            if response.status_code == 200:
                app_limit_headers = {}
                for header, value in response.headers.items():
                    if 'rate-limit' in header.lower() or 'x-rate-limit' in header.lower():
                        app_limit_headers[header] = value
                
                if app_limit_headers:
                    print("   ✅ App-level rate limit headers:")
                    for header, value in app_limit_headers.items():
                        print(f"      • {header}: {value}")
                else:
                    print("   📊 No standard rate limit headers found")
                    
        except Exception as e:
            print(f"   ❌ Error checking app limits: {e}")
        
        print("\n👤 USER-LEVEL LIMITS (OAuth with access tokens):")
        print("   • Used for posting tweets and user-specific actions")
        print("   • Lower limits per user")
        print("   • Required for posting")
        
        # Check user-level limits
        try:
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": "Test"},
                auth=auth
            )
            
            user_limit_headers = {}
            for header, value in response.headers.items():
                if any(keyword in header.lower() for keyword in ['limit', 'rate']):
                    user_limit_headers[header] = value
            
            if user_limit_headers:
                print("   ✅ User-level rate limit headers:")
                for header, value in user_limit_headers.items():
                    print(f"      • {header}: {value}")
                    
                # Specifically highlight the daily tweet limit
                if 'x-user-limit-24hour-limit' in response.headers:
                    daily_limit = response.headers['x-user-limit-24hour-limit']
                    remaining = response.headers.get('x-user-limit-24hour-remaining', 'N/A')
                    print(f"\n   🎯 YOUR TWEET LIMIT: {remaining}/{daily_limit} tweets per day")
                    
                    # Determine tier based on daily limit
                    daily_limit_int = int(daily_limit)
                    if daily_limit_int == 100:
                        print("   📊 Account Tier: FREE (This is why you're limited!)")
                        print("   💡 Even with a production app, you need Basic+ subscription")
                    elif daily_limit_int >= 3000:
                        print("   📊 Account Tier: BASIC or higher ✅")
                    else:
                        print(f"   📊 Account Tier: Unknown (limit: {daily_limit_int})")
            
        except Exception as e:
            print(f"   ❌ Error checking user limits: {e}")
        
        print("\n💡 KEY INSIGHT:")
        print("   Your app might have high app-level limits (like 1667),")
        print("   but posting tweets ALWAYS uses user-level limits!")
        print("   To increase tweet limits, upgrade your Twitter account subscription.")
            
    def quick_status(self):
        """Quick status check - when can post again"""
        print("\n⏰ POSTING STATUS\n")
        
        try:
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": "Test"},
                auth=auth
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 429:
                print("\n❌ RATE LIMITED!")
                print("\nAll headers:")
                for header, value in sorted(response.headers.items()):
                    print(f"• {header}: {value}")
            
            if 'x-user-limit-24hour-remaining' in response.headers:
                remaining = int(response.headers.get('x-user-limit-24hour-remaining', '0'))
                limit = int(response.headers.get('x-user-limit-24hour-limit', '0'))
                
                if remaining > 0:
                    print(f"\n✅ Can post now! ({remaining}/{limit} remaining)")
                else:
                    print(f"\n❌ Daily limit reached (0/{limit})")
                    
                    if 'x-user-limit-24hour-reset' in response.headers:
                        reset_time = datetime.fromtimestamp(int(response.headers['x-user-limit-24hour-reset']))
                        time_diff = reset_time - datetime.now()
                        hours = int(time_diff.total_seconds() / 3600)
                        minutes = int((time_diff.total_seconds() % 3600) / 60)
                        
                        print(f"⏰ Can post again in: {hours}h {minutes}m")
                        print(f"📅 Reset time: {reset_time.strftime('%A at %I:%M %p')}")
                        
        except Exception as e:
            print(f"❌ Error: {e}")

    def check_subscription_status(self):
        """Check if paid subscription is properly applied"""
        print("💳 SUBSCRIPTION STATUS CHECK\n")
        
        print("Expected Basic API limits:")
        print("   • 3,000 tweets per day (minimum)")
        print("   • 50,000+ read requests per month")
        print("   • Should see x-user-limit-24hour-limit >= 3000")
        
        try:
            auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
            response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": "Subscription test"},
                auth=auth
            )
            
            print(f"\nActual limits detected:")
            if 'x-user-limit-24hour-limit' in response.headers:
                daily_limit = int(response.headers['x-user-limit-24hour-limit'])
                remaining = response.headers.get('x-user-limit-24hour-remaining', 'N/A')
                
                print(f"   • Daily tweet limit: {daily_limit}")
                print(f"   • Remaining today: {remaining}")
                
                if daily_limit == 100:
                    print("\n❌ PROBLEM DETECTED!")
                    print("   You're paying for Basic ($194.25) but getting Free limits!")
                    print("\n🔧 POSSIBLE FIXES:")
                    print("   1. Check if subscription is applied to the RIGHT account")
                    print("   2. Verify your API keys are from the PAYING account") 
                    print("   3. Contact Twitter Support - you're not getting what you paid for")
                    print("   4. Check if subscription needs time to activate")
                    
                elif daily_limit >= 3000:
                    print("\n✅ Subscription working correctly!")
                    print("   You have Basic tier limits as expected")
                    
                else:
                    print(f"\n🤔 Unusual limit detected: {daily_limit}")
                    print("   This doesn't match standard Free (100) or Basic (3000+) tiers")
            
            # Check account details
            print(f"\n📊 Full account diagnostics:")
            print(f"   • API Key starts with: {self.api_key[:10]}...")
            
            # Get account info
            client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            
            me = client.get_me()
            if me.data:
                print(f"   • Authenticated as: @{me.data.username}")
                print(f"   • User ID: {me.data.id}")
                print("\n💡 Make sure this matches the account you paid for!")
                
        except Exception as e:
            print(f"❌ Error checking subscription: {e}")
            
    def run_subscription_diagnosis(self):
        """Run focused subscription diagnosis"""
        print("🔍 TWITTER SUBSCRIPTION DIAGNOSIS\n")
        print("Issue: Paying for Basic API but getting Free tier limits\n")
        
        self.check_subscription_status()
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("1. Verify the API keys belong to your paying account")
        print("2. Check Twitter Developer Portal subscription status")
        print("3. If still wrong, contact Twitter Support with:")
        print("   - Your invoice/receipt") 
        print("   - Your app ID")
        print("   - Screenshots of the limit headers")
        print("="*60)

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        # Quick status check
        test = TwitterAPITest()
        test.quick_status()
    elif len(sys.argv) > 1 and sys.argv[1] == 'subscription':
        # Subscription diagnosis
        test = TwitterAPITest()
        test.run_subscription_diagnosis()
    else:
        # Full test suite
        test = TwitterAPITest()
        test.run_all_tests()
        
        print("\n" + "="*60)
        print("For quick status check, run: python twitter_api_test.py status")
        print("For subscription diagnosis, run: python twitter_api_test.py subscription")

if __name__ == "__main__":
    main() 