#!/usr/bin/env python3
"""
Twitter Real-time Monitoring Module
Handles WebSocket connections, TwitterAPI.io integration, and webhook server
"""

import asyncio
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

import aiohttp
import websockets


class TwitterMonitor:
    """Handles real-time Twitter monitoring for deployment requests"""
    
    def __init__(self, deployer):
        """Initialize monitor with reference to main deployer"""
        self.deployer = deployer
        self.logger = deployer.logger
        self.bot_username = deployer.bot_username
        
    async def start_realtime_monitoring(self):
        """Start real-time monitoring using third-party services (1-3 second response time)"""
        # Check which service to use
        service_type = os.getenv('REALTIME_SERVICE', 'twitterapi.io')
        
        if service_type == 'twitterapi.io':
            await self._start_twitterapi_monitoring()
        elif service_type == 'webhook':
            await self._start_webhook_server()
        else:
            print(f"❌ Unknown realtime service: {service_type}")
    
    async def _start_twitterapi_monitoring(self):
        """Monitor using twitterapi.io WebSocket for real-time updates"""
        api_key = os.getenv('TWITTERAPI_IO_KEY')
        if not api_key:
            print("❌ Missing TWITTERAPI_IO_KEY in .env")
            print("📝 Get your API key at: https://twitterapi.io")
            return
        
        # First, ensure filter rules are set up
        from twitter_filter_manager import TwitterFilterManager
        filter_manager = TwitterFilterManager()
        
        print("🔧 Checking Twitter filter rules...")
        rules = await filter_manager.get_rules()
        active_rules = [r for r in rules if r.get('is_effect', 0) == 1]
        
        # Check if we have both deployment and verification rules
        deployment_rule = None
        verification_rule = None
        
        for rule in active_rules:
            if rule['tag'].endswith('_mentions'):
                deployment_rule = rule
            elif rule['tag'].endswith('_verification'):
                verification_rule = rule
        
        if not deployment_rule and not verification_rule:
            print("⚠️  No active filter rules found!")
            print("📝 Setting up both deployment and verification rules...")
            success = await filter_manager.setup_both_rules()
            if not success:
                print("❌ Failed to set up filter rules. Please check manually at https://twitterapi.io")
                return
            print("✅ Both filter rules activated!")
        elif not verification_rule:
            print("⚠️  Missing verification rule!")
            print("📝 Setting up verification rule...")
            success = await filter_manager.setup_verification_rule(interval_seconds=15.0)
            if not success:
                print("❌ Failed to set up verification rule")
                return
            print("✅ Verification rule activated!")
        
        # Show current rules
        if active_rules:
            print(f"✅ Found {len(active_rules)} active filter rule(s)")
            for rule in active_rules:
                print(f"   - {rule['tag']}: {rule['value']} (interval: {rule['interval_seconds']}s)")
        
        # WebSocket configuration
        ws_url = "wss://ws.twitterapi.io/twitter/tweet/websocket"
        headers = {"x-api-key": api_key}
        
        # Connection stats
        connection_count = 0
        last_ping_time = time.time()
        tweets_received = 0
        
        print(f"\n🔌 Connecting to twitterapi.io WebSocket...")
        
        while True:  # Reconnection loop
            try:
                connection_count += 1
                if connection_count > 1:
                    print(f"\n🔄 Reconnection attempt #{connection_count}")
                
                # WebSocket connection with improved settings
                async with websockets.connect(
                    ws_url, 
                    extra_headers=headers,
                    ping_interval=40,  # Send ping every 40 seconds
                    ping_timeout=30,   # Wait 30 seconds for pong
                    close_timeout=10   # Wait 10 seconds for close
                ) as websocket:
                    print(f"✅ Connected to real-time stream!")
                    print(f"👂 Listening for @{self.bot_username} mentions...")
                    print(f"📊 Stats: Connection #{connection_count}, Tweets: {tweets_received}")
                    
                    while True:
                        try:
                            # Add timeout to detect stale connections
                            message = await asyncio.wait_for(
                                websocket.recv(), 
                                timeout=120  # 2 minute timeout
                            )
                            data = json.loads(message)
                            
                            event_type = data.get("event_type")
                            timestamp = data.get("timestamp", 0)
                            
                            if event_type == "connected":
                                print("✅ WebSocket connection confirmed!")
                                self.logger.info("WebSocket connected successfully")
                                
                            elif event_type == "ping":
                                # Server heartbeat - track connection health
                                current_time = time.time()
                                latency = current_time - (timestamp / 1000)
                                last_ping_time = current_time
                                
                                if latency > 5:  # More than 5 seconds latency
                                    self.logger.warning(f"High WebSocket latency: {latency:.1f}s")
                                
                            elif event_type == "tweet":
                                # New tweet matching our filter!
                                tweets_received += 1
                                rule_tag = data.get("rule_tag", "")
                                rule_id = data.get("rule_id", "")
                                tweets = data.get("tweets", [])
                                
                                # Better timing diagnostics
                                current_time_ms = time.time() * 1000
                                event_timestamp = timestamp  # TwitterAPI.io timestamp
                                
                                print(f"\n⚡ New tweet event received!")
                                print(f"   Rule: {rule_tag} (ID: {rule_id})")
                                print(f"   Tweets in batch: {len(tweets)}")
                                print(f"   Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                print(f"   Event timestamp: {datetime.fromtimestamp(event_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')}")
                                
                                # Log full structure for debugging
                                if os.getenv('DEBUG_TWEETS', 'false').lower() == 'true':
                                    self.logger.debug(f"Received tweet event: {json.dumps(data, indent=2)}")
                                
                                for tweet in tweets:
                                    await self._process_tweet_from_websocket(tweet, event_timestamp)
                                    
                        except asyncio.TimeoutError:
                            print("\n⚠️  No data received for 2 minutes - connection may be stale")
                            self.logger.warning("WebSocket timeout - reconnecting")
                            break
                        except websockets.exceptions.ConnectionClosed as e:
                            print(f"\n⚠️  Connection closed: {e}")
                            self.logger.warning(f"WebSocket closed: code={e.code}, reason={e.reason}")
                            break
                        except json.JSONDecodeError as e:
                            self.logger.error(f"Invalid JSON received: {e}")
                            continue
                        except Exception as e:
                            print(f"\n❌ Processing error: {e}")
                            self.logger.error(f"WebSocket processing error: {e}", exc_info=True)
                            continue
                            
            except websockets.exceptions.WebSocketException as e:
                print(f"\n❌ WebSocket error: {e}")
                self.logger.error(f"WebSocket connection error: {e}")
            except Exception as e:
                print(f"\n❌ Connection error: {e}")
                self.logger.error(f"Unexpected connection error: {e}", exc_info=True)
            
            # Exponential backoff for reconnection
            wait_time = min(90, 10 * (2 ** min(connection_count - 1, 5)))
            print(f"⏳ Reconnecting in {wait_time} seconds...")
            
            # Show stats while waiting
            if tweets_received > 0:
                print(f"📊 Session stats: {tweets_received} tweets processed")
            
            await asyncio.sleep(wait_time)
    
    async def _process_tweet_from_websocket(self, tweet: dict, event_timestamp: int):
        """Process a single tweet from WebSocket"""
        # Extract tweet data according to TwitterAPI.io format
        author = tweet.get("author", {})
        
        # TwitterAPI.io uses camelCase: userName not username
        username = author.get("userName") or author.get("username", "unknown")
        author_id = author.get("id", "")
        
        # Get follower count - TwitterAPI.io provides it directly as "followers"
        follower_count = author.get("followers", 0)
        if follower_count == 0:
            # Fallback to public_metrics format
            follower_count = author.get("public_metrics", {}).get("followers_count", 0)
        
        # Only try to fetch user info if we really don't have the username
        if username == "unknown" or not username:
            self.logger.warning(f"Username not found in author data")
            
            # Try to fetch user info if we have author ID
            if author_id:
                print(f"📱 Fetching user info for ID: {author_id}...")
                user_info = await self._fetch_user_info_twitterapi(author_id)
                
                if user_info and user_info['username'] != 'unknown':
                    username = user_info['username']
                    follower_count = user_info['follower_count']
                    print(f"✅ Found user: @{username} (followers: {follower_count:,})")
                else:
                    print(f"❌ Could not fetch user info for ID: {author_id}")
                    print(f"⚠️  Skipping tweet - cannot determine username")
                    return
            else:
                self.logger.warning(f"No author ID available")
                print(f"⚠️  Skipping tweet - cannot determine username")
                return
        
        text = tweet.get("text", "")
        tweet_id = tweet.get("id", "")
        
        # Check if it mentions our bot (case-insensitive)
        if f"@{self.bot_username}".lower() not in text.lower():
            return
        
        # Extract and show tweet timing
        tweet_created_at = tweet.get("createdAt", "")
        print(f"\n⚡ New mention from @{username} (followers: {follower_count:,})")
        print(f"   Tweet: {text[:100]}{'...' if len(text) > 100 else ''}")
        print(f"   Tweet created: {tweet_created_at}")
        print(f"   Received at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Calculate actual delay
        try:
            # Parse Twitter's date format
            from dateutil import parser
            tweet_time = parser.parse(tweet_created_at)
            receive_time = datetime.now(tweet_time.tzinfo)
            actual_delay = (receive_time - tweet_time).total_seconds()
            print(f"   📊 Actual delay: {actual_delay:.1f} seconds")
        except Exception as e:
            print(f"   ⚠️  Could not calculate delay: {e}")
        
        # Log tweet text and full structure for debugging
        self.logger.info(f"Processing tweet from @{username}: {text[:100]}{'...' if len(text) > 100 else ''}")
        if os.getenv('DEBUG_TWEETS', 'false').lower() == 'true':
            self.logger.debug(f"Tweet structure: {json.dumps(tweet, indent=2)}")
        
        # No follower check here - let the main deployer decide based on balance
        # Users with ETH can deploy with ANY follower count
        
        start_time = time.time()
        
        # Process the tweet
        processed_data = {
            'id': tweet_id,
            'author_username': username,
            'text': text,
            'in_reply_to_status_id': tweet.get('in_reply_to_status_id'),
            'media': self._extract_ws_media(tweet),
            'parent_media': [],
            'follower_count': follower_count
        }
        
        # Log media detection
        if processed_data['media']:
            self.logger.info(f"Found {len(processed_data['media'])} images in deployment tweet")
        else:
            self.logger.info("No images found in deployment tweet from WebSocket")
            
            # Try to fetch tweet details to get media
            print(f"📷 Fetching tweet details for media...")
            tweet_details = await self._fetch_tweet_details_twitterapi(tweet_id)
            
            if tweet_details and tweet_details.get('media'):
                processed_data['media'] = tweet_details['media']
                self.logger.info(f"✅ Found {len(tweet_details['media'])} images via API")
            else:
                self.logger.info("❌ No images found via API either")
        
        # If it's a reply, fetch parent tweet media
        if processed_data['in_reply_to_status_id']:
            parent_media = await self._fetch_parent_media_twitterapi(
                processed_data['in_reply_to_status_id']
            )
            processed_data['parent_media'] = parent_media
            
            if parent_media:
                self.logger.info(f"Found {len(parent_media)} images in parent tweet")
        
        # Check if this is a verification tweet first
        verification_result = await self._check_verification_tweet(text, username)
        if verification_result:
            print(f"\n🔐 {verification_result}")
            print(f"✅ Processed verification in {time.time() - start_time:.1f}s total")
            return
        
        # Process deployment
        result = await self.deployer.process_tweet_mention(processed_data)
        print(f"\n📋 Result: {result}")
        print(f"✅ Processed in {time.time() - start_time:.1f}s total")
    
    def _extract_ws_media(self, tweet: dict) -> list:
        """Extract media from WebSocket tweet format"""
        media_list = []
        try:
            # Check all possible media locations with detailed logging
            media_sources = []
            
            # Only show detailed media debug logs if DEBUG_MEDIA is enabled
            debug_media = os.getenv('DEBUG_MEDIA', 'false').lower() == 'true'
            
            if debug_media:
                self.logger.debug(f"Tweet keys: {list(tweet.keys())}")
            
            # 1. Direct 'media' field
            if 'media' in tweet and isinstance(tweet['media'], list):
                media_sources.extend(tweet['media'])
                if debug_media:
                    self.logger.debug(f"Found 'media' field with {len(tweet['media'])} items")
            
            # 2. Under 'attachments'
            if 'attachments' in tweet and 'media' in tweet['attachments']:
                media_sources.extend(tweet['attachments']['media'])
                if debug_media:
                    self.logger.debug(f"Found 'attachments.media' with {len(tweet['attachments']['media'])} items")
            
            # 3. Under 'entities'
            if 'entities' in tweet and 'media' in tweet['entities']:
                media_sources.extend(tweet['entities']['media'])
                if debug_media:
                    self.logger.debug(f"Found 'entities.media' with {len(tweet['entities']['media'])} items")
            
            # 4. Under 'extended_entities'
            if 'extended_entities' in tweet and 'media' in tweet['extended_entities']:
                media_sources.extend(tweet['extended_entities']['media'])
                if debug_media:
                    self.logger.debug(f"Found 'extended_entities.media' with {len(tweet['extended_entities']['media'])} items")
            
            # 5. Under 'extendedEntities' (different casing)
            if 'extendedEntities' in tweet and 'media' in tweet['extendedEntities']:
                media_sources.extend(tweet['extendedEntities']['media'])
                if debug_media:
                    self.logger.debug(f"Found 'extendedEntities.media' with {len(tweet['extendedEntities']['media'])} items")
            
            # If no media found in standard locations, log the full structure
            if not media_sources:
                if os.getenv('DEBUG_TWEETS', 'false').lower() == 'true':
                    self.logger.debug(f"No media found in standard locations. Tweet structure: {json.dumps(tweet, indent=2)}")
            
            # Process all found media
            for media in media_sources:
                media_type = media.get('type') or media.get('media_type', '')
                
                if media_type == 'photo' or media_type == 'image':
                    # Try different URL fields
                    url = (media.get('url') or 
                           media.get('media_url_https') or 
                           media.get('media_url') or
                           media.get('preview_image_url'))
                    
                    # Special case: if url is a t.co shortlink, use media_url_https instead
                    if url and 't.co/' in url and media.get('media_url_https'):
                        url = media.get('media_url_https')
                    
                    if url:
                        media_list.append({
                            'type': 'photo',
                            'url': url
                        })
                        self.logger.info(f"Found image in tweet: {url}")
            
            if not media_list and debug_media:
                self.logger.debug(f"No images found in tweet data")
                
        except Exception as e:
            self.logger.error(f"Error extracting media: {e}")
            
        return media_list
    
    async def _fetch_parent_media_twitterapi(self, tweet_id: str) -> list:
        """Fetch parent tweet media using twitterapi.io"""
        try:
            api_key = os.getenv('TWITTERAPI_IO_KEY')
            url = f"https://api.twitterapi.io/v1/tweets/{tweet_id}"
            headers = {"Authorization": f"Bearer {api_key}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('media', [])
            return []
        except:
            return []
    
    async def _fetch_user_info_twitterapi(self, user_id: str) -> Optional[Dict]:
        """Fetch user info from TwitterAPI.io API as fallback"""
        try:
            api_key = os.getenv('TWITTERAPI_IO_KEY')
            url = f"https://api.twitterapi.io/twitter/user/info"
            headers = {
                "X-API-Key": api_key
            }
            
            # TwitterAPI.io expects userId (not user_id) in query params
            params = {
                "userId": user_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # TwitterAPI.io returns data directly (not in a 'data' field)
                        if isinstance(data, dict):
                            # Extract relevant info using TwitterAPI.io format
                            return {
                                'username': data.get('userName', 'unknown'),
                                'follower_count': data.get('followers', 0),
                                'name': data.get('name', ''),
                                'id': data.get('id', user_id)
                            }
                        else:
                            self.logger.error(f"Unexpected response format: {data}")
                            return None
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch user info: {response.status} - {error_text}")
                        return None
        except Exception as e:
            self.logger.error(f"Error fetching user info: {e}")
            return None
    
    async def _fetch_tweet_details_twitterapi(self, tweet_id: str) -> Optional[Dict]:
        """Fetch tweet details including media from TwitterAPI.io"""
        try:
            api_key = os.getenv('TWITTERAPI_IO_KEY')
            url = "https://api.twitterapi.io/twitter/tweets"
            headers = {
                "X-API-Key": api_key
            }
            
            params = {
                "tweet_ids": tweet_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        tweets = data.get('tweets', [])
                        
                        if tweets and len(tweets) > 0:
                            tweet = tweets[0]
                            media_list = []
                            
                            # Extract media from entities
                            entities = tweet.get('entities', {})
                            if 'media' in entities:
                                for media in entities['media']:
                                    if media.get('type') == 'photo':
                                        url = media.get('media_url_https') or media.get('media_url')
                                        if url:
                                            media_list.append({
                                                'type': 'photo',
                                                'url': url
                                            })
                            
                            # Also check for media URLs in the tweet
                            urls = entities.get('urls', [])
                            for url_obj in urls:
                                expanded_url = url_obj.get('expanded_url', '')
                                # Check if it's a Twitter photo URL
                                if 'pic.twitter.com' in expanded_url or '/photo/' in expanded_url:
                                    # This is likely a photo, but we need the actual image URL
                                    # For now, log it
                                    self.logger.info(f"Found photo URL in tweet: {expanded_url}")
                            
                            return {
                                'media': media_list,
                                'text': tweet.get('text', ''),
                                'entities': entities
                            }
                        
                        return None
                    else:
                        self.logger.error(f"Failed to fetch tweet details: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error fetching tweet details: {e}")
            return None
    
    async def _start_webhook_server(self):
        """Start a webhook server to receive real-time Twitter mentions"""
        from aiohttp import web
        
        print("\n🌐 Starting webhook server for real-time updates...")
        
        # Create webhook handler
        async def handle_webhook(request):
            try:
                data = await request.json()
                
                # Process Twitter webhook data
                if 'tweet_create_events' in data:
                    for tweet in data['tweet_create_events']:
                        # Check if it mentions our bot (case-insensitive)
                        if f"@{self.bot_username}".lower() in tweet.get('text', '').lower():
                            print(f"\n⚡ New mention via webhook!")
                            
                            processed_data = {
                                'id': tweet['id_str'],
                                'author_username': tweet['user']['screen_name'],
                                'text': tweet['text'],
                                'in_reply_to_status_id': tweet.get('in_reply_to_status_id_str'),
                                'media': self._extract_media_from_tweet(tweet),
                                'parent_media': [],
                                'follower_count': tweet['user'].get('followers_count', 0)
                            }
                            
                            # Process immediately
                            await self.deployer.process_tweet_mention(processed_data)
                
                return web.Response(text="OK", status=200)
                
            except Exception as e:
                self.logger.error(f"Webhook error: {e}")
                return web.Response(text="Error", status=500)
        
        # Setup routes
        app = web.Application()
        app.router.add_post('/webhook/twitter', handle_webhook)
        
        # Start server
        port = int(os.getenv('WEBHOOK_PORT', '8080'))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print(f"✅ Webhook server running on port {port}")
        print(f"📌 Configure your webhook URL: https://yourdomain.com/webhook/twitter")
        print(f"💡 Use services like twitterapi.io, IFTTT, or Zapier to send webhooks")
        
        # Keep server running
        while True:
            await asyncio.sleep(3600)
    
    def _extract_media_from_tweet(self, tweet: dict) -> list:
        """Extract media from webhook tweet format"""
        media_list = []
        if 'entities' in tweet and 'media' in tweet['entities']:
            for media in tweet['entities']['media']:
                if media.get('type') == 'photo':
                    media_list.append({
                        'type': 'photo',
                        'url': media.get('media_url_https', media.get('media_url'))
                    })
        return media_list
    
    async def _check_verification_tweet(self, text: str, username: str) -> str:
        """Check if this is a verification tweet and process it"""
        import re
        import sqlite3
        
        # Pattern: "@DeployOnKlik !verify user [CODE] in order to use start claiming fees from @[username]"
        verification_pattern = r"@deployonklik\s+!verify\s+user\s+([A-Z0-9]{8})\s+in\s+order\s+to\s+use\s+start\s+claiming\s+fees\s+from\s+@(\w+)"
        match = re.search(verification_pattern, text.lower())
        
        if not match:
            return None
        
        verification_code = match.group(1).upper()
        claimed_username = match.group(2).lower()
        
        # Security: Verify the username in the tweet matches who is tweeting
        if claimed_username != username.lower():
            self.logger.warning(f"Username mismatch: @{username} tweeted verification for @{claimed_username}")
            return f"❌ Username mismatch: You tweeted verification for @{claimed_username} but you are @{username}"
        
        self.logger.info(f"Found verification tweet from @{username} with code: {verification_code}")
        
        try:
            # Import database class
            from deployer.database import DeploymentDatabase
            db = DeploymentDatabase()
            
            # Verify the code
            success = db.verify_twitter_account(username, verification_code)
            
            if success:
                self.logger.info(f"✅ Successfully verified @{username}")
                
                # Send notification to Telegram if user has Telegram linked
                await self._send_verification_success_notification(username)
                
                return f"✅ Verification successful for @{username}! Account verified and fee capture unlocked."
            else:
                self.logger.warning(f"❌ Invalid verification code from @{username}: {verification_code}")
                return f"❌ Invalid verification code from @{username}"
                
        except Exception as e:
            self.logger.error(f"Error processing verification for @{username}: {e}")
            return f"❌ Error processing verification for @{username}"
    
    async def _send_verification_success_notification(self, username: str):
        """Send Telegram notification when verification succeeds"""
        try:
            import sqlite3
            import os
            from telegram import Bot
            
            # Get user's Telegram ID
            conn = sqlite3.connect('deployments.db')
            cursor = conn.execute(
                "SELECT telegram_id FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if not result or not result[0]:
                return  # No Telegram linked
            
            telegram_id = result[0]
            bot_token = os.getenv('TELEGRAM_DEPLOYER_BOT')
            
            if not bot_token:
                return  # No bot token
            
            bot = Bot(token=bot_token)
            
            message = (
                f"🎉 **Verification Complete!**\n"
                f"══════════════════════\n\n"
                f"✅ @{username} is now verified!\n\n"
                f"**New Benefits Unlocked:**\n"
                f"• 50% fee capture from your deployments\n"
                f"• Advanced deployment features\n"
                f"• Verified account status\n\n"
                f"**Next:** Deploy tokens to start earning fees!"
            )
            
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self.logger.info(f"Sent verification success notification to Telegram user {telegram_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send verification notification: {e}") 