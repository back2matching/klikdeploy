#!/usr/bin/env python3
"""
Get Telegram channel ID for public channel @DeployOnKlik
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_channel_id():
    """Get channel ID for public channel"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env")
        return
    
    # For public channels, use the @username
    channel_username = "@DeployOnKlik"
    
    print(f"🔍 Getting ID for public channel: {channel_username}")
    
    # Method 1: Try using the username directly
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    test_message = "🧪 Test message to get channel ID"
    
    data = {
        'chat_id': channel_username,
        'text': test_message
    }
    
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            # Extract the actual channel ID from the response
            channel_id = result['result']['chat']['id']
            print(f"\n✅ SUCCESS! Channel ID found: {channel_id}")
            print(f"\n📝 Update your .env file:")
            print(f"   TELEGRAM_CHANNEL_ID={channel_id}")
            print(f"\n✅ Test message sent to {channel_username}")
            
            # Delete the test message
            message_id = result['result']['message_id']
            delete_url = f"https://api.telegram.org/bot{token}/deleteMessage"
            delete_data = {'chat_id': channel_id, 'message_id': message_id}
            requests.post(delete_url, json=delete_data)
            print("🗑️  Test message deleted")
            
            return channel_id
        else:
            error = result.get('description', 'Unknown error')
            print(f"❌ Error: {error}")
            
            if "bot is not a member" in error.lower():
                print("\n💡 Solution: Add your bot as admin to @DeployOnKlik channel")
                print("   1. Go to @DeployOnKlik channel")
                print("   2. Channel Info → Administrators → Add Administrator")
                print("   3. Search for your bot and add it")
                print("   4. Give it 'Post Messages' permission")
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        print(response.text)
    
    # Method 2: Try getChat
    print("\n🔍 Trying alternative method...")
    get_chat_url = f"https://api.telegram.org/bot{token}/getChat"
    chat_data = {'chat_id': channel_username}
    
    response = requests.post(get_chat_url, json=chat_data)
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            chat_info = result['result']
            channel_id = chat_info['id']
            print(f"\n✅ Channel found via getChat!")
            print(f"   Name: {chat_info.get('title', 'Unknown')}")
            print(f"   Type: {chat_info.get('type', 'Unknown')}")
            print(f"   ID: {channel_id}")
            print(f"\n📝 Update your .env file:")
            print(f"   TELEGRAM_CHANNEL_ID={channel_id}")
            return channel_id
    
    print("\n❌ Could not determine channel ID")
    print("   Make sure the bot is added as admin to @DeployOnKlik")

if __name__ == "__main__":
    get_channel_id() 