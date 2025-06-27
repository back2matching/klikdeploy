# Complete Setup Guide - Klik Token Deployer

## What This System Does

Users tweet `@DeployOnKlik $TOKEN` → Bot deploys tokens on Ethereum in 1-3 seconds

- **FREE** when gas ≤ 2.5 gwei (strict limits, 1500+ followers)
- **PAID** when gas > 2.5 gwei (deposit ETH first)
- **$DOK HOLDERS** get 2 free deploys/day up to 15 gwei (5M+ DOK)

## Progressive Cooldown System (NEW!)

To prevent abuse and save gas costs, the bot now uses a VERY restrictive progressive cooldown:

- **1st free deployment**: Always allowed ✅
- **2nd deployment within 7 days**: 14-day cooldown applied ⏳
- **3+ deployments within 7 days**: 30-day cooldown applied ⏳⏳

This encourages users to either:
- Become $DOK holders for more deploys
- Use the pay-per-deploy system
- Use their free deploys wisely

**Note**: $DOK ticker is reserved and cannot be deployed.

## Quick Start - Run Both Bots Together

### Single Terminal (Recommended)
```bash
python run_both.py
```
This runs both bots in ONE terminal with color-coded output:
- 🔵 Blue = Twitter bot messages
- 🟢 Green = Telegram bot messages

### Separate Terminals
```bash
# Terminal 1
python klik_token_deployer.py

# Terminal 2 (optional)
python telegram_deposit_bot.py
```

## How The System Works

### For New Users

1. **Tweet at the bot**
   ```
   @user: @DeployOnKlik $MEME
   Bot: ❌ Gas too high! DM @DeployOnKlikBot on Telegram
   ```

2. **Open Telegram bot**
   - Search for @DeployOnKlikBot
   - Press START
   - Click "🔗 Link Twitter Account"
   - Enter: `/link yourusername`

3. **Register wallet**
   - Click "💳 Register Wallet"
   - Enter: `/wallet 0x123...`
   - ⚠️ IMPORTANT: You MUST send ETH from THIS wallet!

4. **Deposit ETH**
   - Click "📥 Deposit"
   - Send 0.03-1 ETH to bot wallet FROM your registered wallet
   - Click "🔄 Check for Deposits"
   - Bot credits your account instantly

5. **Deploy tokens**
   - Tweet again: `@DeployOnKlik $MEME`
   - Bot deploys and deducts from balance

6. **Withdraw anytime**
   - Click "📤 Withdraw" 
   - Confirm withdrawal of FULL balance
   - ETH sent to your wallet automatically!
   - Note: Only full balance withdrawals supported (no partial)

## Telegram Bot Setup

### 1. Bot Already Created!

Your bot is ready at: **@DeployOnKlikBot**
Token is already in `.env`: `7896903262:AAG_qEn6LsG04ZYA2mUsgSBZbagTkEkuPXc`

**Note**: The Twitter bot username is currently set to `mlquantlab` in .env for testing. Change `BOT_USERNAME` to `DeployOnKlik` for production.

### 2. Just Run It!

```bash
python telegram_deposit_bot.py
# or
python run_both.py  # To run both bots together
```

That's it! No need to create a bot or get tokens - it's all set up.

## Why Users Must Register Their Wallet

The bot needs to know which wallet belongs to which user. When you:
1. Register wallet: `0x123...`
2. Send ETH FROM that wallet
3. Bot sees: "Oh, 0x123... sent money, that's @username's wallet"
4. Credits your account

If you send from a different wallet, the bot won't know it's you!

## Telegram Bot Features

### Main Menu (after setup)
Shows comprehensive dashboard with:
- 💰 **Your Balance** - Current ETH balance
- 📊 **Deployment Stats** - Total, successful, today's count
- ⛽ **Current Gas** - Live gas prices and costs
- 🚀 **Deploy Status** - Whether you can deploy now

### Buttons
- **📥 Deposit** - Get deposit instructions
- **📤 Withdraw** - Withdraw full balance (no partial withdrawals)
- **📜 History** - View recent deployments and deposits
- **⚙️ Settings** - Change Twitter/wallet

### Commands
- `/start` - Open main menu
- `/link <twitter>` - Link Twitter account
- `/wallet <address>` - Register your ETH wallet

## How Deposits Work

1. **User sends ETH** from registered wallet
2. **Clicks "Check for Deposits"** button
3. **Bot uses Alchemy** to find transfers
4. **Credits account** instantly

No manual TX hash needed! The bot checks the blockchain directly.

## For $DOK Token Holders

To become a holder, buy 5,000,000+ DOK tokens:
- **Token**: Deploy On Klik (DOK)
- **CA**: `0x69ca61398eCa94D880393522C1Ef5c3D8c058837`
- **Buy**: [DexScreener](https://dexscreener.com/ethereum/0x69ca61398eca94d880393522c1ef5c3d8c058837)

Benefits:
- 2 FREE deploys/day (gas ≤ 15 gwei)
- **NO FEES** (save 0.01 ETH per deploy)
- Works even when gas is high!

Check holder status:
- Telegram bot: Click "🎯 Check $DOK Holder"
- Command line: `python holder_verification.py username`

## Security

- ✅ Only YOU can withdraw YOUR balance
- ✅ Withdrawals are automatic (no admin needed)
- ✅ Must deposit from registered wallet
- ✅ All transactions tracked in database
- ✅ Withdrawals include +4 gwei gas for fast confirmation

## Common Issues

### "No new deposits found"
- Make sure you sent FROM your registered wallet
- Amount must be 0.03-1 ETH
- Wait for transaction to confirm
- Click "Check for Deposits" again

### Twitter bot not responding
- Check TwitterAPI.io dashboard
- Verify filter rules include @DeployOnKlik (or current bot username)
- Ensure 1,500+ followers requirement is met

### Colors not showing in terminal
- Windows: Use Windows Terminal (not cmd.exe)
- Mac/Linux: Most terminals support colors

## Running 24/7

```bash
# Using screen
screen -S klik
python run_both.py
# Detach: Ctrl+A, D
# Reattach: screen -r klik

# Using tmux  
tmux new -s klik
python run_both.py
# Detach: Ctrl+B, D
# Reattach: tmux attach -t klik
```

## Important Notes

- **Withdrawals**: Only full balance withdrawals supported (not partial amounts)
- **Bot Username**: Currently set to `mlquantlab` for testing - change to `DeployOnKlik` in production
- **Self-Protection**: Bot can deploy and reply to its first token only (for testing), then ignores all subsequent own tweets
- **Follower Requirement**: 1,500+ followers required for ALL deployments (spam protection)
- **Gas Buffer**: Withdrawals add +4 gwei to current gas for fast confirmation
- **Deposit Security**: 
  - Only checks last 30 minutes of transactions
  - Requires 3+ block confirmations
  - Each tx_hash credited only once
  - Startup verification that user balances ≤ wallet balance

## That's It!

Your bot system is now:
- 🤖 Fully automated (no admin needed)
- 💰 Self-service deposits & withdrawals
- 🎨 Beautiful colored output when using `run_both.py`
- 📊 Everything tracked in database

Just run `python run_both.py` and you're good to go! 