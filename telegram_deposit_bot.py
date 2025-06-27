#!/usr/bin/env python3
"""
Telegram Bot for Klik Token Deployer Management
Fully automated deposit/withdrawal system
"""

import os
import logging
from datetime import datetime, timedelta
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import requests
import telegram

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce noise from httpx (Telegram API requests)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Bot configuration
BOT_TOKEN = os.getenv('TELEGRAM_DEPLOYER_BOT')
BOT_WALLET = os.getenv('DEPLOYER_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
RPC_URL = os.getenv('ALCHEMY_RPC_URL')

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)

# Initialize database (using same one as Twitter bot)
def init_db():
    conn = sqlite3.connect('deployments.db')
    
    # Create all tables if they don't exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitter_username TEXT UNIQUE,
            eth_address TEXT,
            telegram_id INTEGER,
            balance REAL DEFAULT 0,
            is_holder BOOLEAN DEFAULT FALSE,
            holder_balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create deposits table - FIXED
    conn.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitter_username TEXT,
            amount REAL,
            tx_hash TEXT UNIQUE,
            from_address TEXT,
            confirmed BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add withdrawals table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            eth_address TEXT,
            amount REAL,
            tx_hash TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with buttons"""
    telegram_id = update.effective_user.id
    
    # Check if user exists
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT twitter_username, eth_address, balance, is_holder FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    
    # Get current gas price
    gas_price = w3.eth.gas_price
    gas_gwei = float(w3.from_wei(gas_price, 'gwei'))
    
    # Determine what's available for this user
    if gas_gwei <= 3:
        current_tier = "FREE TIER"
        tier_desc = "1 free deploy available today"
    else:
        current_tier = "PAY PER DEPLOY"
        tier_desc = f"Deposit ETH to deploy"
    
    conn.close()
    
    keyboard = []
    
    if not user or not user[0]:
        # New user - needs to link Twitter
        message = (
            "**Welcome to Deploy On Klik! 🚀**\n"
            "══════════════════════\n"
            "The fastest way to launch tokens on Ethereum\n\n"
            
            "**How It Works**\n"
            "══════════════════════\n"
            "**1.** Tweet to deploy:\n"
            "`@DeployOnKlik $TICKER - Token Name`\n\n"
            "**2.** Bot deploys in 1-3 seconds\n"
            "• Automatically adds images from tweet\n"
            "• Replies with DexScreener link\n"
            "• Links to your original tweet\n\n"
            
            f"**Active Now ({current_tier})**\n"
            f"══════════════════════\n"
            f"{tier_desc}\n"
            f"Gas: **{gas_gwei:.1f} gwei**\n"
            f"Deploy Cost: **~{gas_gwei * 8_000_000 / 1e9:.4f} ETH**\n\n"
            
            "**Deployment Tiers**\n"
            "══════════════════════\n"
            "**🆓 FREE TIER**\n"
            "• 1 deployment per day\n"
            "• Gas ≤ 3 gwei\n"
            "• **Requires 1500+ Twitter followers**\n"
            "• VIP: 20k+ followers (gas ≤ 6 gwei)\n"
            "• Bot pays all gas fees\n\n"
            
            "**🎯 HOLDER TIER** (Gas ≤ 15 gwei)\n"
            "• 2 FREE deployments daily\n"
            "• Hold 0.5%+ of $DOK supply (5M+ DOK)\n"
            "• **Must deposit once to verify wallet**\n"
            "• Bot pays gas (NO FEES!)\n\n"
            
            "**💰 PAY PER DEPLOY** (Any gas price)\n"
            "• Unlimited deployments\n"
            "• **No follower requirements**\n"
            "• Deposit ETH to this bot\n"
            "• Cost: Gas + 0.01 ETH fee\n\n"
            
            "**Get Started**\n"
            "══════════════════════\n"
            "Link your Twitter account to begin:"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Link Twitter Account", callback_data="link_twitter")],
            [InlineKeyboardButton("⛽ View Gas Prices", callback_data="gas")],
            [InlineKeyboardButton("📚 Full Guide", url="https://t.me/DeployOnKlik")]
        ]
    elif not user[1]:
        # Has Twitter but no wallet
        message = (
            f"**Deploy On Klik**\n"
            f"══════════════════════\n"
            f"Twitter: @{user[0]} ✅\n"
            f"Wallet: Not registered ❌\n\n"
            
            f"**Active Now ({current_tier})**\n"
            f"══════════════════════\n"
            f"{tier_desc}\n"
            f"Gas: **{gas_gwei:.1f} gwei**\n"
            f"Deploy Cost: **~{gas_gwei * 8_000_000 / 1e9:.4f} ETH**\n\n"
            
            "**Why Register a Wallet?**\n"
            "══════════════════════\n"
            "**Without wallet:** Limited to FREE tier only\n"
            "**With wallet:** Access all deployment tiers\n\n"
            
            "• Deposit ETH for paid deployments\n"
            "• Deploy when gas is above 3 gwei\n"
            "• Track your deployment history\n"
            "• Withdraw balance anytime\n\n"
            
            "**How Deposits Work**\n"
            "══════════════════════\n"
            "**1.** Register your ETH wallet\n"
            "**2.** Send 0.03-1 ETH from that wallet\n"
            "**3.** Balance credits instantly\n"
            "**4.** Deploy unlimited tokens!\n\n"
            
            "**Security:** Only deposits from YOUR\n"
            "registered wallet will be credited.\n\n"
            
            "**Next Step**\n"
            "══════════════════════\n"
            "Register your wallet to unlock full access:"
        )
        keyboard = [
            [InlineKeyboardButton("💳 Register Wallet", callback_data="register_wallet")],
            [InlineKeyboardButton("⛽ View Gas Prices", callback_data="gas")],
            [InlineKeyboardButton("🔄 Change Twitter", callback_data="link_twitter")]
        ]
    else:
        # Fully registered - show comprehensive dashboard
        twitter_username, eth_address, balance, is_holder = user[0], user[1], user[2], user[3]
        
        # Get deployment stats
        conn = sqlite3.connect('deployments.db')
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN date(requested_at) = date('now') THEN 1 ELSE 0 END) as today
            FROM deployments
            WHERE username = ?
        ''', (twitter_username,))
        stats = cursor.fetchone()
        total_deploys, successful_deploys, today_deploys = stats if stats else (0, 0, 0)
        
        # Get today's limits
        cursor = conn.execute('''
            SELECT free_deploys, holder_deploys 
            FROM daily_limits 
            WHERE username = ? AND date = date('now')
        ''', (twitter_username.lower(),))
        limits = cursor.fetchone()
        free_used, holder_used = limits if limits else (0, 0)
        conn.close()
        
        # Calculate deployment cost
        deploy_gas_cost = gas_gwei * 6000000 / 1e9
        deploy_fee = 0 if is_holder else 0.01
        deploy_total = deploy_gas_cost + deploy_fee
        
        # Get DOK holder balance if available
        cursor = conn.execute(
            "SELECT holder_balance FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        holder_balance_result = cursor.fetchone()
        dok_balance = holder_balance_result[0] if holder_balance_result else 0
        
        # Determine user status and what's active for them specifically
        if is_holder:
            status_emoji = "🎯"
            if dok_balance > 0:
                status_text = f"$DOK HOLDER ({dok_balance:,.0f} DOK)"
            else:
                status_text = "$DOK HOLDER"
            daily_limit = f"{holder_used}/2 holder deploys used"  # Changed from 5 to 2
            fee_text = "NO FEES!"
            if holder_used < 2:  # Changed from 5 to 2
                active_mode = "HOLDER TIER"
            else:
                active_mode = "PAY PER DEPLOY"
        else:
            status_emoji = "👤"
            status_text = "Regular User"
            fee_text = "0.01 ETH fee/deploy"
            if gas_gwei <= 3 and free_used < 1:
                daily_limit = f"{free_used}/1 free deploy used"
                active_mode = "FREE TIER"
            else:
                daily_limit = f"{free_used}/1 free deploy used" if gas_gwei <= 3 else "Pay per deploy active"
                active_mode = "PAY PER DEPLOY"
        
        # Build comprehensive message
        message = (
            f"**Deploy On Klik 🚀**\n"
            f"══════════════════════\n"
            f"{status_emoji} **@{twitter_username}** ({status_text})\n"
            f"💰 Balance: **{balance:.4f} ETH**\n"
            f"💳 Wallet: `{eth_address}`\n"
            f"══════════════════════\n"
            f"**📊 Your Stats:**\n"
            f"══════════════════════\n"
            f"• Total deployments: **{total_deploys}**\n"
            f"• Successful: **{successful_deploys}**\n"
            f"• Today: **{today_deploys}** ({daily_limit})\n"
            f"• Success rate: **{(successful_deploys/total_deploys*100 if total_deploys > 0 else 0):.1f}%**\n"
            f"══════════════════════\n"
            f"**⛽ Current Market ({active_mode}):**\n"
            f"══════════════════════\n"
            f"• Gas: **{gas_gwei:.1f} gwei**\n"
            f"• Deploy cost: ~**{deploy_gas_cost:.4f} ETH**\n"
            f"• Your fee: **{fee_text}**\n"
            f"• Total: ~**{deploy_total:.4f} ETH**/deploy\n"
        )
        
        # Add deployment instructions based on current conditions
        message += "══════════════════════\n"
        if gas_gwei <= 3 and free_used < 1:
            message += "**FREE Deployment Requirements:**\n"
            message += "• Gas ≤ 3 gwei ✅\n"
            message += "• 1500+ Twitter followers\n"
            message += "• 1 per day (unused) ✅\n\n"
            message += "Tweet: `@DeployOnKlik $TICKER`\n"
        elif is_holder and holder_used < 2:  # Changed from 5 to 2
            message += f"✅ **{2-holder_used} holder deploys left today!**\nTweet now: `@DeployOnKlik $TICKER - Token Name`\n"
        elif balance >= deploy_total:
            message += f"✅ **Ready to deploy!** ({int(balance/deploy_total)} deploys available)\nTweet now: `@DeployOnKlik $TICKER - Token Name`\n"
        else:
            needed = deploy_total - balance
            message += f"❌ **Low balance!** Need **{needed:.4f}** more ETH\n"
            if gas_gwei > 3:
                message += f"\n**FREE tier requires gas ≤ 3 gwei**\n"
                message += f"Current gas: {gas_gwei:.1f} gwei\n"
        
        message += "══════════════════════"
        
        keyboard = [
            [InlineKeyboardButton("📥 Deposit", callback_data="deposit"),
             InlineKeyboardButton("📤 Withdraw", callback_data="withdraw")],
            [InlineKeyboardButton("📜 History", callback_data="history"),
             InlineKeyboardButton("🔄 Refresh", callback_data="main_menu")],
            [InlineKeyboardButton("🎯 Check $DOK Holder", callback_data="check_holder"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/DeployOnKlik")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        await start(update, context)
    
    elif query.data == "settings":
        await show_settings(update, context)
    
    elif query.data == "link_twitter":
        keyboard = [[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "**Link Twitter Account**\n"
            "══════════════════════\n\n"
            "**Instructions**\n"
            "══════════════════════\n"
            "Send your Twitter username without the @\n\n"
            "**Example:**\n"
            "`/link yourusername`\n\n"
            "**Why Link Twitter?**\n"
            "══════════════════════\n"
            "• Connects deployments to your balance\n"
            "• Tracks your deployment history\n"
            "• Enables holder verification\n"
            "• Links deposits to your account\n\n"
            "**Note:** You can change this later in settings.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif query.data == "register_wallet":
        keyboard = [[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "**Register ETH Wallet**\n"
            "══════════════════════\n\n"
            "**Instructions**\n"
            "══════════════════════\n"
            "Send your Ethereum wallet address\n\n"
            "**Example:**\n"
            "`/wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f6ed8`\n\n"
            "**Important Security Notice**\n"
            "══════════════════════\n"
            "⚠️ **Only deposits from this wallet will credit!**\n\n"
            "• Use a wallet you control\n"
            "• Not an exchange wallet\n"
            "• Must be on Ethereum mainnet\n"
            "• You can change it later\n\n"
            "**Why This Matters**\n"
            "══════════════════════\n"
            "This prevents unauthorized deposits and\n"
            "ensures only YOU can fund your account.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif query.data == "deposit":
        await show_deposit_info(update, context)
    
    elif query.data == "withdraw":
        await show_withdraw_info(update, context)
    
    elif query.data == "confirm_withdraw":
        await confirm_withdrawal(update, context)
    
    elif query.data == "history":
        await show_history(update, context)
    
    elif query.data == "check_deposits":
        await check_my_deposits(update, context)
    
    elif query.data == "gas":
        await show_gas_prices(update, context)
    
    elif query.data == "check_holder":
        await check_holder_status(update, context)

async def show_gas_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current gas prices and deployment costs"""
    query = update.callback_query
    
    # Get current gas price
    gas_price = w3.eth.gas_price
    gas_gwei = float(w3.from_wei(gas_price, 'gwei'))
    
    # Calculate deployment costs at different gas levels
    deploy_gas_units = 6.5e6  # 6.5M gas for deployment
    
    message = (
        f"**Current Gas Prices ⛽**\n"
        f"══════════════════════\n\n"
        f"**Live Network Gas:** {gas_gwei:.1f} gwei\n\n"
        f"**Deployment Cost Estimates:**\n"
        f"*(6.5M gas + 0.01 ETH fee)*\n\n"
        f"**1 gwei:** ~{1 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**3 gwei:** ~{3 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**5 gwei:** ~{5 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**10 gwei:** ~{10 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**15 gwei:** ~{15 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**20 gwei:** ~{20 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**30 gwei:** ~{30 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n"
        f"**50 gwei:** ~{50 * deploy_gas_units / 1e9 + 0.01:.4f} ETH\n\n"
        f"**Note:** Holders pay gas only (no 0.01 fee)\n\n"
        f"*Updates every 12 seconds*"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Gas Prices", callback_data="gas_prices")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            # Gas prices haven't changed, just acknowledge the button press
            await query.answer("Gas prices unchanged")
        else:
            # Re-raise other errors
            raise

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent deployment history"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT twitter_username FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    
    if not user:
        await query.edit_message_text("❌ Account not found!")
        conn.close()
        return
    
    twitter_username = user[0]
    
    # Get recent deployments (case-insensitive)
    cursor = conn.execute('''
        SELECT 
            token_symbol,
            token_name,
            status,
            requested_at,
            tx_hash,
            token_address
        FROM deployments
        WHERE LOWER(username) = LOWER(?)
        ORDER BY requested_at DESC
        LIMIT 5
    ''', (twitter_username,))
    
    deployments = cursor.fetchall()
    
    # Get recent deposits (case-insensitive)
    cursor = conn.execute('''
        SELECT 
            amount,
            created_at,
            tx_hash
        FROM deposits
        WHERE LOWER(twitter_username) = LOWER(?)
        ORDER BY created_at DESC
        LIMIT 3
    ''', (twitter_username,))
    
    deposits = cursor.fetchall()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"**Recent Activity 📜**\n"
    message += f"══════════════════════\n\n"
    
    if deployments:
        message += f"**Recent Deployments:**\n"
        message += f"══════════════════════\n"
        for symbol, name, status, requested_at, tx_hash, token_address in deployments:
            # Format date
            date = datetime.fromisoformat(requested_at).strftime("%b %d %H:%M")
            status_emoji = "✅" if status == "success" else "❌"
            
            message += f"{status_emoji} **${symbol}** - {name}\n"
            message += f"   {date}"
            if status == "success" and token_address:
                # Shorten addresses for display
                short_addr = f"{token_address[:6]}...{token_address[-4:]}"
                message += f" • {short_addr}"
            message += "\n"
        message += "\n"
    else:
        message += "No deployments yet.\n\n"
    
    if deposits:
        message += f"══════════════════════\n"
        message += f"**Recent Deposits:**\n"
        message += f"══════════════════════\n"
        for amount, created_at, tx_hash in deposits:
            date = datetime.fromisoformat(created_at).strftime("%b %d %H:%M")
            message += f"💰 **{amount:.4f} ETH**\n"
            message += f"   {date}\n"
        message += "\n"
    
    message += f"══════════════════════\n"
    message += f"For full transaction details,\ncheck Etherscan."
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def link_twitter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Link Twitter username to Telegram account"""
    if not context.args:
        keyboard = [[InlineKeyboardButton("🔗 Link Twitter", callback_data="link_twitter")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "**Missing username!**\n\n"
            "Try: `/link yourusername`\n"
            "(without the @ symbol)",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    twitter_username = context.args[0].replace('@', '').lower()
    telegram_id = update.effective_user.id
    
    conn = sqlite3.connect('deployments.db')
    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Check current user status
        cursor = conn.execute(
            "SELECT id, twitter_username FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        current_user = cursor.fetchone()
        
        # Check if new username is already taken
        cursor = conn.execute(
            "SELECT telegram_id FROM users WHERE twitter_username = ? AND telegram_id != ?",
            (twitter_username, telegram_id)
        )
        username_taken = cursor.fetchone()
        
        if username_taken and username_taken[0]:
            # Username is taken by another active user
            await update.message.reply_text(
                f"❌ **@{twitter_username} is already linked to another Telegram account!**\n\n"
                f"Each Twitter account can only be linked to one Telegram user.",
                parse_mode='Markdown'
            )
            return
        
        if current_user:
            # User exists - update their username
            old_username = current_user[1]
            
            if old_username == twitter_username:
                await update.message.reply_text(
                    f"ℹ️ **You're already linked to @{twitter_username}**",
                    parse_mode='Markdown'
                )
                return
            
            # Check if target username has any orphaned balance to recover
            cursor = conn.execute(
                "SELECT balance, eth_address FROM users WHERE twitter_username = ? AND (telegram_id IS NULL OR telegram_id = 0)",
                (twitter_username,)
            )
            orphaned_account = cursor.fetchone()
            recovered_balance = 0
            recovered_address = None
            
            if orphaned_account and orphaned_account[0] > 0:
                recovered_balance = orphaned_account[0]
                recovered_address = orphaned_account[1]
                logger.info(f"Found orphaned balance of {recovered_balance:.4f} ETH on @{twitter_username}")
            
            # Clear orphaned entries (including the one we just checked)
            conn.execute(
                "DELETE FROM users WHERE twitter_username = ? AND (telegram_id IS NULL OR telegram_id = 0 OR telegram_id = ?)",
                (twitter_username, telegram_id)
            )
            
            # Update the user's username
            logger.info(f"Updating Twitter username from @{old_username} to @{twitter_username} for Telegram ID {telegram_id}")
            
            # If recovering balance, add it to the user's current balance
            if recovered_balance > 0:
                conn.execute(
                    "UPDATE users SET twitter_username = ?, balance = balance + ? WHERE telegram_id = ?",
                    (twitter_username, recovered_balance, telegram_id)
                )
                # Also update deposits table to link old deposits to new username
                conn.execute(
                    "UPDATE deposits SET twitter_username = ? WHERE twitter_username = ?",
                    (twitter_username, old_username)
                )
                message_text = f"**✅ Twitter username updated!**\n\nFrom: @{old_username}\nTo: @{twitter_username}\n\n💰 **Recovered balance: {recovered_balance:.4f} ETH**\n\nYour total balance has been updated."
            else:
                conn.execute(
                    "UPDATE users SET twitter_username = ? WHERE telegram_id = ?",
                    (twitter_username, telegram_id)
                )
                # Update deposits table to link old deposits to new username
                conn.execute(
                    "UPDATE deposits SET twitter_username = ? WHERE twitter_username = ?",
                    (twitter_username, old_username)
                )
                message_text = f"**✅ Twitter username updated!**\n\nFrom: @{old_username}\nTo: @{twitter_username}\n\nYour wallet and balance remain unchanged."
            
            is_update = True
        else:
            # New user - create entry
            # First clear any orphaned entries
            conn.execute(
                "DELETE FROM users WHERE twitter_username = ? AND (telegram_id IS NULL OR telegram_id = 0)",
                (twitter_username,)
            )
            
            logger.info(f"Creating new user @{twitter_username} for Telegram ID {telegram_id}")
            conn.execute(
                "INSERT INTO users (twitter_username, telegram_id) VALUES (?, ?)",
                (twitter_username, telegram_id)
            )
            
            message_text = f"**✅ Linked to @{twitter_username}**\n\nNow register your wallet 👇"
            is_update = False
        
        conn.commit()
        
        # Show appropriate response
        if is_update:
            keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        else:
            keyboard = [[InlineKeyboardButton("💳 Register Wallet", callback_data="register_wallet")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except sqlite3.IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        await update.message.reply_text(
            f"❌ **Database error!**\n\n"
            f"Could not update to @{twitter_username}.\n"
            f"This username may be corrupted in the database.\n\n"
            f"Please contact support or try a different username.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error linking Twitter: {e}")
        await update.message.reply_text(
            f"❌ **An error occurred!**\n\n"
            f"Please try again or contact support.",
            parse_mode='Markdown'
        )
    finally:
        conn.close()

async def register_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register user's ETH wallet address"""
    if not context.args:
        keyboard = [[InlineKeyboardButton("💳 Register Wallet", callback_data="register_wallet")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "**Missing wallet address!**\n\n"
            "Try: `/wallet 0x123...abc`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    eth_address = context.args[0]
    telegram_id = update.effective_user.id
    
    # Validate ETH address
    if not w3.is_address(eth_address):
        await update.message.reply_text("❌ Invalid ETH address! Please check and try again.")
        return
    
    conn = sqlite3.connect('deployments.db')
    try:
        # Update user's wallet
        conn.execute('''
            UPDATE users 
            SET eth_address = ?
            WHERE telegram_id = ?
        ''', (eth_address, telegram_id))
        
        if conn.total_changes == 0:
            await update.message.reply_text("❌ Please link your Twitter first with /link")
            return
        
        conn.commit()
        
        keyboard = [
            [InlineKeyboardButton("📥 Deposit Instructions", callback_data="deposit")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"**✅ Wallet registered!**\n\n"
            f"`{eth_address}`\n\n"
            f"Ready to deposit ETH 👇",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    finally:
        conn.close()

async def show_deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit instructions"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT twitter_username, eth_address, balance FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user[1]:
        keyboard = [[InlineKeyboardButton("💳 Register Wallet", callback_data="register_wallet")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Please register your wallet first!",
            reply_markup=reply_markup
        )
        return
    
    # Get current gas price
    gas_price = w3.eth.gas_price
    gas_gwei = float(w3.from_wei(gas_price, 'gwei'))
    deploy_cost = gas_gwei * 6000000 / 1e9  # Estimate
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check for Deposits", callback_data="check_deposits")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if holder for fee calculation
    is_holder = False
    conn2 = sqlite3.connect('deployments.db')
    cursor2 = conn2.execute(
        "SELECT is_holder FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    holder_result = cursor2.fetchone()
    if holder_result:
        is_holder = holder_result[0]
    conn2.close()
    
    fee_amount = 0 if is_holder else 0.01
    fee_text = "NO FEES!" if is_holder else "0.01 ETH fee"
    
    await query.edit_message_text(
        f"**Deposit Instructions**\n"
        f"══════════════════════\n\n"
        f"**Your Account**\n"
        f"══════════════════════\n"
        f"Wallet: `{user[1][:6]}...{user[1][-4:]}`\n"
        f"Balance: **{user[2]:.4f} ETH**\n"
        f"Status: {'🎯 HOLDER' if is_holder else '👤 Regular'}\n\n"
        f"**Send ETH To This Address**\n"
        f"══════════════════════\n"
        f"`{BOT_WALLET}`\n\n"
        f"**Deposit Requirements**\n"
        f"══════════════════════\n"
        f"• **Amount:** 0.03 - 1 ETH per deposit\n"
        f"• **From:** Your registered wallet only\n"
        f"• **Network:** Ethereum Mainnet\n"
        f"• **Credits:** Instantly after 3 confirmations\n\n"
        f"**Current Deployment Costs**\n"
        f"══════════════════════\n"
        f"• **Gas Price:** {gas_gwei:.1f} gwei\n"
        f"• **Gas Cost:** ~{deploy_cost:.4f} ETH\n"
        f"• **Platform Fee:** {fee_text}\n"
        f"• **Total per Deploy:** ~{deploy_cost + fee_amount:.4f} ETH\n\n"
        f"With your balance, you can deploy:\n"
        f"**{int(user[2] / (deploy_cost + fee_amount))} tokens** at current gas\n\n"
        f"**After Sending**\n"
        f"══════════════════════\n"
        f"Click below to check for deposits:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def check_my_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually check for deposits from user's registered wallet"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    await query.edit_message_text("🔄 Checking for deposits...")
    
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT eth_address, balance, twitter_username FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    
    if not user or not user[0]:
        await query.edit_message_text("❌ No wallet registered!")
        conn.close()
        return
    
    user_wallet = user[0]
    old_balance = user[1]
    twitter_username = user[2]
    
    # Check recent transfers from this wallet using Alchemy
    try:
        current_block = w3.eth.block_number
        # IMPORTANT: Only check last 30 minutes (approximately 150 blocks) to prevent old deposits
        from_block = max(0, current_block - 150)  # ~30 minutes
        
        logger.info(f"Checking deposits for {user_wallet} from block {from_block} to {current_block}")
        
        # Get transfers FROM user's wallet TO bot wallet
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": hex(from_block),
                "toBlock": "latest",
                "fromAddress": user_wallet,
                "toAddress": BOT_WALLET,
                "category": ["external"],
                "excludeZeroValue": True
            }]
        })
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'transfers' in data['result']:
                transfers = data['result']['transfers']
                
                total_deposited = 0
                new_deposits = []
                
                for transfer in transfers:
                    tx_hash = transfer['hash']
                    value = float(transfer['value'])
                    block_num = int(transfer['blockNum'], 16) if isinstance(transfer.get('blockNum'), str) else transfer.get('blockNum', 0)
                    
                    # Check if already processed
                    cursor = conn.execute(
                        "SELECT id FROM deposits WHERE tx_hash = ?",
                        (tx_hash,)
                    )
                    
                    if not cursor.fetchone() and 0.03 <= value <= 1:
                        # Verify transaction is confirmed (at least 3 blocks deep)
                        if current_block - block_num < 3:
                            logger.info(f"Skipping unconfirmed tx {tx_hash} - only {current_block - block_num} confirmations")
                            continue
                        
                        # New valid deposit
                        logger.info(f"Processing new deposit: {value:.4f} ETH from {user_wallet} (tx: {tx_hash})")
                        
                        conn.execute('''
                            INSERT INTO deposits (twitter_username, amount, tx_hash, from_address, confirmed)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (twitter_username.lower(), value, tx_hash, user_wallet, True))
                        
                        total_deposited += value
                        new_deposits.append(f"• {value:.4f} ETH")
                
                if total_deposited > 0:
                    # Update balance
                    conn.execute('''
                        UPDATE users 
                        SET balance = balance + ?
                        WHERE telegram_id = ?
                    ''', (total_deposited, telegram_id))
                    
                    conn.commit()
                    
                    keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Calculate deployment capacity
                    gas_price = w3.eth.gas_price
                    gas_gwei = float(w3.from_wei(gas_price, 'gwei'))
                    deploy_cost = gas_gwei * 8_000_000 / 1e9
                    deploy_fee = 0.01  # TODO: Check if holder
                    tokens_available = int((old_balance + total_deposited) / (deploy_cost + deploy_fee))
                    
                    await query.edit_message_text(
                        f"**Deposit Confirmed ✅**\n"
                        f"══════════════════════\n\n"
                        f"**Transaction Details**\n"
                        f"══════════════════════\n"
                        f"**Received:**\n" + "\n".join(new_deposits) + "\n\n"
                        f"**Total:** {total_deposited:.4f} ETH\n"
                        f"**Previous balance:** {old_balance:.4f} ETH\n"
                        f"**New balance:** {old_balance + total_deposited:.4f} ETH\n\n"
                        f"**Next Steps**\n"
                        f"══════════════════════\n"
                        f"Tweet `@DeployOnKlik $TICKER` to deploy!\n\n"
                        f"You can now deploy approximately:\n"
                        f"**{tokens_available} tokens** at current gas ({gas_gwei:.1f} gwei)",
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    keyboard = [
                        [InlineKeyboardButton("🔄 Check Again", callback_data="check_deposits")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        "**No New Deposits Found**\n"
                        "══════════════════════\n\n"
                        "**Checklist**\n"
                        "══════════════════════\n"
                        "✓ Sent FROM your registered wallet?\n"
                        "✓ Amount between 0.03-1 ETH?\n"
                        "✓ Transaction has 3+ confirmations?\n"
                        "✓ Sent to correct bot address?\n\n"
                        "**Your Registered Wallet**\n"
                        "══════════════════════\n"
                        f"`{user_wallet}`\n\n"
                        "**Bot Deposit Address**\n"
                        "══════════════════════\n"
                        f"`{BOT_WALLET}`\n\n"
                        "**Note:** Only checks last 30 minutes.\n"
                        "Older deposits must be manually verified.",
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
    except Exception as e:
        logger.error(f"Error checking deposits: {e}")
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Error checking deposits. Please try again.",
            reply_markup=reply_markup
        )
    finally:
        conn.close()

async def show_withdraw_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show withdrawal interface"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT balance, eth_address FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await query.edit_message_text("❌ Account not found!")
        return
    
    balance, eth_address = user
    
    if balance < 0.01:
        keyboard = [
            [InlineKeyboardButton("📥 Deposit", callback_data="deposit")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"❌ **Insufficient balance!**\n\n"
            f"Your balance: {balance:.4f} ETH\n"
            f"Minimum withdrawal: 0.01 ETH",
            reply_markup=reply_markup
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ Withdraw All", callback_data="confirm_withdraw")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Calculate gas estimate with extra buffer
    base_gas_price = w3.eth.gas_price
    extra_gas_gwei = 4  # Add 4 gwei for fast confirmation
    extra_gas_wei = w3.to_wei(extra_gas_gwei, 'gwei')
    gas_price = base_gas_price + extra_gas_wei
    gas_cost = gas_price * 21000 / 1e18  # Standard ETH transfer
    net_amount = balance - gas_cost if balance > gas_cost else 0
    
    # Show gas breakdown
    base_gwei = float(w3.from_wei(base_gas_price, 'gwei'))
    final_gwei = float(w3.from_wei(gas_price, 'gwei'))
    
    await query.edit_message_text(
        f"**Withdrawal Confirmation 📤**\n"
        f"══════════════════════\n\n"
        f"**Transaction Details:**\n"
        f"• Amount: **{balance:.4f} ETH**\n"
        f"• To wallet: `{eth_address}`\n\n"
        f"══════════════════════\n"
        f"**Gas Settings:**\n"
        f"══════════════════════\n"
        f"⛽ Gas: {base_gwei:.1f} + {extra_gas_gwei} = **{final_gwei:.1f} gwei**\n"
        f"💨 Fast confirmation buffer included\n"
        f"⛽ Gas fee: ~**{gas_cost:.5f} ETH**\n\n"
        f"══════════════════════\n"
        f"💰 **You'll receive: ~{net_amount:.4f} ETH**\n\n"
        f"Withdraw your entire balance?",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process full balance withdrawal"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    await query.edit_message_text("⏳ Processing withdrawal...")
    
    # Get user info
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT balance, eth_address, twitter_username FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    
    if not user or user[0] < 0.01:
        conn.close()
        await query.edit_message_text("❌ Insufficient balance!")
        return
    
    balance, eth_address, twitter_username = user
    
    try:
        # Calculate gas with extra buffer for fast confirmation
        base_gas_price = w3.eth.gas_price
        extra_gas_gwei = 4  # Add 4 gwei to ensure fast confirmation
        extra_gas_wei = w3.to_wei(extra_gas_gwei, 'gwei')
        gas_price = base_gas_price + extra_gas_wei
        gas_limit = 21000  # Standard ETH transfer
        
        # Log gas info
        base_gwei = float(w3.from_wei(base_gas_price, 'gwei'))
        final_gwei = float(w3.from_wei(gas_price, 'gwei'))
        logger.info(f"Withdrawal gas: base {base_gwei:.1f} + {extra_gas_gwei} = {final_gwei:.1f} gwei")
        
        # Build transaction
        nonce = w3.eth.get_transaction_count(BOT_WALLET)
        tx = {
            'nonce': nonce,
            'to': eth_address,
            'value': w3.to_wei(balance, 'ether'),
            'gas': gas_limit,
            'gasPrice': gas_price,
            'chainId': w3.eth.chain_id
        }
        
        # Sign and send
        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        
        # Update balance to 0
        conn.execute('''
            UPDATE users 
            SET balance = 0
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        # Record withdrawal
        conn.execute('''
            INSERT INTO withdrawals (telegram_id, eth_address, amount, tx_hash, status)
            VALUES (?, ?, ?, ?, 'completed')
        ''', (telegram_id, eth_address, balance, tx_hash_hex))
        
        conn.commit()
        
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ **Withdrawal Sent!**\n\n"
            f"Amount: {balance:.4f} ETH\n"
            f"To: `{eth_address}`\n"
            f"TX: `{tx_hash_hex}`\n\n"
            f"Your balance is now: 0 ETH\n\n"
            f"[View on Etherscan](https://etherscan.io/tx/{tx_hash_hex})",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        logger.info(f"Withdrawal completed: @{twitter_username} withdrew {balance:.4f} ETH")
        
    except Exception as e:
        logger.error(f"Withdrawal error: {e}")
        await query.edit_message_text(
            f"❌ Withdrawal failed!\n"
            f"Error: {str(e)}\n\n"
            f"Your balance was not deducted. Please try again."
        )
    finally:
        conn.close()

async def monitor_deposits():
    """Background task to monitor deposits - runs every 30 seconds"""
    while True:
        try:
            # This now uses Alchemy instead of Etherscan
            # Process deposits automatically as they come in
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            await asyncio.sleep(30)

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy command - redirect to button interface"""
    keyboard = [[InlineKeyboardButton("📤 Withdraw", callback_data="withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Please use the button to withdraw:",
        reply_markup=reply_markup
    )

async def check_holder_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check and update $DOK holder status"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    await query.edit_message_text("🔄 Checking $DOK holder status...")
    
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT twitter_username, eth_address, is_holder, holder_balance FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    
    if not user or not user[1]:
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ No wallet registered! Register a wallet first to check holder status.",
            reply_markup=reply_markup
        )
        conn.close()
        return
    
    twitter_username, eth_address, current_holder_status, holder_balance = user
    
    try:
        # Import holder verification
        from holder_verification import check_holder_status as verify_dok_holder
        
        # Check real-time holder status
        is_holder_now, balance, percentage = verify_dok_holder(eth_address)
        
        # Update database if status changed
        if is_holder_now != current_holder_status or balance != holder_balance:
            conn.execute(
                "UPDATE users SET is_holder = ?, holder_balance = ? WHERE telegram_id = ?",
                (is_holder_now, balance, telegram_id)
            )
            conn.commit()
        
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"**$DOK Holder Status 🎯**\n"
        message += f"══════════════════════\n\n"
        message += f"**Your Details:**\n"
        message += f"• Twitter: **@{twitter_username}**\n"
        message += f"• Wallet: `{eth_address[:6]}...{eth_address[-4:]}`\n\n"
        message += f"══════════════════════\n"
        message += f"**$DOK Balance:**\n"
        message += f"══════════════════════\n"
        message += f"• Balance: **{balance:,.0f} DOK**\n"
        message += f"• Percentage: **{percentage:.4f}%** of supply\n"
        message += f"• Required: **5,000,000 DOK** (0.5%)\n\n"
        
        if is_holder_now:
            message += f"**✅ YOU ARE A HOLDER!**\n\n"
            # Check if wallet is verified through deposits
            cursor = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE LOWER(twitter_username) = LOWER(?) AND from_address = ? AND confirmed = 1",
                (twitter_username, eth_address)
            )
            deposit_count = cursor.fetchone()[0]
            
            if deposit_count > 0:
                message += f"**Your Benefits:**\n"
                message += f"• 2 FREE deployments daily\n"
                message += f"• Gas limit: ≤ 15 gwei\n"
                message += f"• NO platform fees (save 0.01 ETH)\n"
                message += f"• Priority support\n\n"
            else:
                message += f"**⚠️ WALLET NOT VERIFIED!**\n\n"
                message += f"You have {balance:,.0f} DOK but need to:\n"
                message += f"**Deposit once from this wallet** to verify ownership\n\n"
                message += f"This prevents others from claiming your tokens.\n"
                message += f"Deposit 0.03+ ETH to verify and unlock benefits!\n\n"
            message += f"**Token Info:**\n"
            message += f"• Token: Deploy On Klik (DOK)\n"
            message += f"• CA: `0x69ca61398eCa94D880393522C1Ef5c3D8c058837`\n"
            message += f"• [View on DexScreener](https://dexscreener.com/ethereum/0x69ca61398eca94d880393522c1ef5c3d8c058837)"
        else:
            needed = 5_000_000 - balance
            message += f"**❌ NOT A HOLDER**\n\n"
            message += f"You need **{needed:,.0f} more DOK** to qualify.\n\n"
            message += f"**Buy $DOK:**\n"
            message += f"• [DexScreener](https://dexscreener.com/ethereum/0x69ca61398eca94d880393522c1ef5c3d8c058837)\n"
            message += f"• [Uniswap](https://app.uniswap.org/#/swap?outputCurrency=0x69ca61398eca94d880393522c1ef5c3d8c058837)\n\n"
            message += f"CA: `0x69ca61398eCa94D880393522C1Ef5c3D8c058837`"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=False
        )
        
    except ImportError:
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Holder verification system not available. Please contact support.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error checking holder status: {e}")
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Error checking holder status. Please try again later.",
            reply_markup=reply_markup
        )
    finally:
        conn.close()

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings menu"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute(
        "SELECT twitter_username, eth_address FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await query.edit_message_text("❌ Account not found!")
        return
    
    twitter_username, eth_address = user[0], user[1]
    
    keyboard = [
        [InlineKeyboardButton("🔗 Change Twitter", callback_data="link_twitter")],
        [InlineKeyboardButton("💳 Change Wallet", callback_data="register_wallet")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    wallet_display = f"`{eth_address}`" if eth_address else "Not set"
    
    await query.edit_message_text(
        f"**Settings ⚙️**\n"
        f"══════════════════════\n\n"
        f"**Current Setup:**\n"
        f"• Twitter: **@{twitter_username}**\n"
        f"• Wallet: {wallet_display}\n\n"
        f"══════════════════════\n"
        f"Select an option to change:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def credit_failed_deployment(username: str, amount: float, tx_hash: str):
    """Credit user for a failed deployment - safety mechanism"""
    try:
        conn = sqlite3.connect('deployments.db')
        cursor = conn.execute(
            "SELECT balance FROM users WHERE LOWER(twitter_username) = LOWER(?)",
            (username,)
        )
        result = cursor.fetchone()
        
        if result:
            # Credit the user
            conn.execute('''
                UPDATE users 
                SET balance = balance + ?
                WHERE LOWER(twitter_username) = LOWER(?)
            ''', (amount, username))
            
            # Log the credit
            logger.info(f"Credited {amount} ETH to @{username} for failed deployment {tx_hash}")
        else:
            logger.error(f"User @{username} not found for failed deployment credit")
            
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error crediting failed deployment: {e}")
        return False

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_DEPLOYER_BOT not set in .env!")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Add the token to .env")
        return
    
    # Initialize database
    init_db()
    
    # Safety check: Verify total user balances don't exceed bot wallet balance
    conn = sqlite3.connect('deployments.db')
    cursor = conn.execute("SELECT SUM(balance) FROM users")
    total_user_balances = cursor.fetchone()[0] or 0
    conn.close()
    
    bot_wallet_balance = float(w3.from_wei(w3.eth.get_balance(BOT_WALLET), 'ether'))
    
    if total_user_balances > bot_wallet_balance:
        print(f"⚠️  WARNING: Balance mismatch detected!")
        print("   Please check database integrity.")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("link", link_twitter))
    application.add_handler(CommandHandler("wallet", register_wallet))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start monitoring in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(monitor_deposits())
    
    # Run the bot
    print("🤖 Telegram Management Bot Started!")
    print("🔗 Bot: @DeployOnKlikBot")
    print("✅ Fully automated - no admin needed!")
    print("📱 Commands: /start /link /wallet /withdraw")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 