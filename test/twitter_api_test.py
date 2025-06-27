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
        
        print("\n4. Rate Limit Status")
        self.check_rate_limits()
        
        print("\n5. Account Tier Check")
        self.check_account_tier()
        
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
                
                if 'x-user-limit-24hour-remaining' in response.headers:
                    remaining = response.headers.get('x-user-limit-24hour-remaining', '0')
                    limit = response.headers.get('x-user-limit-24hour-limit', '0')
                    print(f"   Daily limit: {remaining}/{limit}")
                    
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
            
            if 'x-user-limit-24hour-remaining' in response.headers:
                remaining = int(response.headers.get('x-user-limit-24hour-remaining', '0'))
                limit = int(response.headers.get('x-user-limit-24hour-limit', '0'))
                
                if remaining > 0:
                    print(f"✅ Can post now! ({remaining}/{limit} remaining)")
                else:
                    print(f"❌ Daily limit reached (0/{limit})")
                    
                    if 'x-user-limit-24hour-reset' in response.headers:
                        reset_time = datetime.fromtimestamp(int(response.headers['x-user-limit-24hour-reset']))
                        time_diff = reset_time - datetime.now()
                        hours = int(time_diff.total_seconds() / 3600)
                        minutes = int((time_diff.total_seconds() % 3600) / 60)
                        
                        print(f"⏰ Can post again in: {hours}h {minutes}m")
                        print(f"📅 Reset time: {reset_time.strftime('%A at %I:%M %p')}")
                        
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        # Quick status check
        test = TwitterAPITest()
        test.quick_status()
    else:
        # Full test suite
        test = TwitterAPITest()
        test.run_all_tests()
        
        print("\n" + "="*60)
        print("For quick status check, run: python twitter_api_test.py status")

if __name__ == "__main__":
    main() 