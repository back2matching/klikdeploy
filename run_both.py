#!/usr/bin/env python3
"""
Run both Twitter and Telegram bots together
Shows output from both in a clean, organized way
"""

import asyncio
import sys
import os
from datetime import datetime
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from dotenv import load_dotenv
import requests
import signal

# Load environment variables FIRST
load_dotenv()

# Configure logging to reduce noise
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)  # Reduce Telegram HTTP request logs
logging.getLogger("telegram").setLevel(logging.INFO)  # Keep telegram at INFO but not DEBUG

# Add colors for better visibility
class Colors:
    TWITTER = '\033[94m'  # Blue
    TELEGRAM = '\033[92m' # Green
    ERROR = '\033[91m'    # Red
    WARNING = '\033[93m'  # Yellow
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Print a nice header"""
    print("\n" + "="*60)
    print(f"{Colors.BOLD}🚀 KLIK TOKEN DEPLOYER - UNIFIED SYSTEM{Colors.RESET}")
    print("="*60)
    print(f"{Colors.TWITTER}[TWITTER BOT]{Colors.RESET} Monitoring @DeployOnKlik mentions")
    print(f"{Colors.TELEGRAM}[TELEGRAM BOT]{Colors.RESET} Managing deposits & withdrawals")
    print(f"⚡ Response time: 1-3 seconds from tweet to deployment")
    print("="*60 + "\n")

def format_output(source, message):
    """Format output with color and timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if source == "twitter":
        prefix = f"{Colors.TWITTER}[{timestamp} TWITTER]{Colors.RESET}"
    elif source == "telegram":
        prefix = f"{Colors.TELEGRAM}[{timestamp} TELEGRAM]{Colors.RESET}"
    else:
        prefix = f"{Colors.WARNING}[{timestamp} SYSTEM]{Colors.RESET}"
    
    return f"{prefix} {message}"

def cleanup_existing_processes():
    """Kill any existing bot processes (except current one)"""
    import platform
    
    print(format_output("system", "🧹 Cleaning up existing processes..."))
    
    current_pid = os.getpid()
    
    if platform.system() == "Windows":
        # Windows: Use taskkill to find and kill Python processes running our scripts
        try:
            # Get current process ID to exclude it
            result = subprocess.run([
                "powershell", "-Command", 
                f"Get-Process python* | Where-Object {{$_.Id -ne {current_pid} -and ($_.CommandLine -like '*telegram_deposit_bot*' -or $_.CommandLine -like '*klik_token_deployer*')}} | Stop-Process -Force"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(format_output("system", "✅ Cleaned up existing bot processes"))
            else:
                print(format_output("system", "ℹ️  No existing bot processes found"))
        except Exception as e:
            print(format_output("system", f"⚠️  Process cleanup warning: {e}"))
    else:
        # Linux/Mac: Use pkill
        try:
            # Kill only the bot scripts, not the current run_both.py
            subprocess.run(["pkill", "-f", "telegram_deposit_bot.py"], capture_output=True)
            subprocess.run(["pkill", "-f", "klik_token_deployer.py"], capture_output=True)
            print(format_output("system", "✅ Cleaned up existing bot processes"))
        except Exception as e:
            print(format_output("system", f"⚠️  Process cleanup warning: {e}"))
    
    # Clear any existing Telegram webhooks
    telegram_token = os.getenv('TELEGRAM_DEPLOYER_BOT')
    if telegram_token:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{telegram_token}/deleteWebhook",
                json={"drop_pending_updates": True}
            )
            if response.status_code == 200:
                print(format_output("system", "✅ Cleared Telegram webhooks"))
            time.sleep(2)  # Give it more time to clean up
        except Exception as e:
            print(format_output("system", f"⚠️  Webhook cleanup warning: {e}"))

async def run_twitter_bot():
    """Run the Twitter bot"""
    try:
        print(format_output("twitter", "Starting Twitter bot..."))
        
        # Import and run the Twitter bot
        from klik_token_deployer import main as twitter_main
        await twitter_main("realtime")
        
    except Exception as e:
        print(format_output("twitter", f"{Colors.ERROR}Error: {e}{Colors.RESET}"))

def run_telegram_bot():
    """Run the Telegram bot in a separate thread"""
    try:
        print(format_output("telegram", "Starting Telegram bot..."))
        
        # Import and run the Telegram bot
        from telegram_deposit_bot import main as telegram_main
        telegram_main()
        
    except Exception as e:
        print(format_output("telegram", f"{Colors.ERROR}Error: {e}{Colors.RESET}"))

async def check_environment():
    """Check that all required environment variables are set"""
    print(format_output("system", "Checking environment..."))
    
    required_vars = {
        "Twitter": ["TWITTERAPI_IO_KEY", "DEPLOYER_ADDRESS", "PRIVATE_KEY", "ALCHEMY_RPC_URL"],
        "Telegram": ["TELEGRAM_DEPLOYER_BOT"]
    }
    
    all_good = True
    
    for service, vars in required_vars.items():
        for var in vars:
            if not os.getenv(var):
                if service == "Telegram" and var == "TELEGRAM_DEPLOYER_BOT":
                    print(format_output("system", f"{Colors.WARNING}⚠️  {var} not set - Telegram bot will be disabled{Colors.RESET}"))
                else:
                    print(format_output("system", f"{Colors.ERROR}❌ {var} not set!{Colors.RESET}"))
                    all_good = False
            else:
                # Only show non-sensitive values
                if var == "DEPLOYER_ADDRESS":
                    value = os.getenv(var)
                    print(format_output("system", f"✅ Wallet: {value}"))
                # Don't display other sensitive values
    
    # Show current bot username for Twitter
    bot_username = os.getenv('BOT_USERNAME', 'DeployOnKlik')
    print(format_output("system", f"📱 Twitter bot monitoring: @{bot_username}"))
    
    return all_good

async def main():
    """Main function to run both bots"""
    print_header()
    
    # Clean up any existing processes first
    cleanup_existing_processes()
    
    # Check environment
    env_ok = await check_environment()
    
    # Only check Twitter requirements
    twitter_ready = bool(os.getenv('TWITTERAPI_IO_KEY') and os.getenv('DEPLOYER_ADDRESS') and os.getenv('PRIVATE_KEY'))
    
    if not twitter_ready:
        print(format_output("system", f"{Colors.ERROR}Please set all required environment variables in .env{Colors.RESET}"))
        print(format_output("system", "Required for Twitter bot:"))
        print(format_output("system", "- TWITTERAPI_IO_KEY (from twitterapi.io)"))
        print(format_output("system", "- DEPLOYER_ADDRESS (your bot wallet)"))
        print(format_output("system", "- PRIVATE_KEY (for deployments)"))
        print(format_output("system", "- ALCHEMY_RPC_URL (for blockchain access)"))
        return
    
    # Check if Telegram bot is configured
    telegram_enabled = bool(os.getenv('TELEGRAM_DEPLOYER_BOT'))
    
    if telegram_enabled:
        print(format_output("system", "Running BOTH bots..."))
        print(format_output("system", "Press Ctrl+C to stop\n"))
        
        # Start Telegram bot in a separate thread
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
        
        # Give Telegram bot time to start
        await asyncio.sleep(2)
        
        # Run Twitter bot in main thread
        await run_twitter_bot()
    else:
        print(format_output("system", f"{Colors.WARNING}Telegram bot not configured - running Twitter bot only{Colors.RESET}"))
        print(format_output("system", "To enable Telegram bot:"))
        print(format_output("system", "1. Create bot with @BotFather"))
        print(format_output("system", "2. Add TELEGRAM_DEPLOYER_BOT to .env"))
        print(format_output("system", ""))
        print(format_output("system", f"{Colors.BOLD}Running Twitter bot only...{Colors.RESET}"))
        print(format_output("system", "Press Ctrl+C to stop\n"))
        
        await run_twitter_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(format_output("system", "\n👋 Shutting down gracefully..."))
        sys.exit(0)
    except Exception as e:
        print(format_output("system", f"{Colors.ERROR}Fatal error: {e}{Colors.RESET}"))
        sys.exit(1) 