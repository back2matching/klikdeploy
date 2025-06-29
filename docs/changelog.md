# Changelog - Klik Token Deployer

All notable changes to the Klik Token Deployer bot system will be documented in this file.

## [V3.0] - 2025-01-03

### 💰 Self-Claim Fees System

#### New Feature: Fee Capture Choice
- **Verified users can now choose**: Community fee split OR self-claim fees
- **Default behavior**: Unchanged - fees still fund community buybacks
- **Self-claim mode**: Users get 50% of fees from their token deployments
- **Maintains buybacks**: 25% source token + 25% $DOK buybacks still happen

#### How It Works
- **Automated integration**: Works with existing `test_fee_detection.py` system
- **Smart detection**: System checks deployer preferences for each fee
- **No manual work**: Fully automated based on user settings
- **Backwards compatible**: Existing system unchanged

#### User Interface (Telegram Bot)
- **Fee Settings menu**: Toggle self-claim on/off
- **Claimable fees view**: See accumulated fees from deployments  
- **Simple controls**: One-click toggle between modes
- **Real-time stats**: Track total claimed and available amounts

#### Security Requirements
- **Twitter verification required**: Only verified accounts can self-claim
- **Wallet verification required**: Must have deposited from registered wallet
- **Prevents exploitation**: Unverified users default to community split
- **Secure preferences**: Settings stored safely in database

#### Database Updates
- **New tables**: `user_fee_settings`, `deployment_fees`
- **Fee tracking**: Records claimable amounts per user per token
- **Migration script**: `migrate_self_claim_fees.py` for safe updates
- **Full compatibility**: All existing data preserved

#### Benefits
- **User choice**: Community support OR personal profit
- **Transparency**: Users see exactly what they earn
- **Security**: Multiple verification layers
- **Platform growth**: Incentivizes verification and engagement

## [2.2.0] - 2025-01-03

### 🎉 Major Tier System Overhaul - More Generous!

#### New Tier System
- **Free Tier (250+ followers)**: 3 deploys/week ≤2 gwei
- **VIP Free Tier (20k+ followers)**: 3 deploys/week ≤6 gwei  
- **Holder Tier (5M+ $DOK)**: 10 deploys/week ≤10 gwei + NO FEES

#### What Changed
- **Follower requirement**: Reduced from 1500 to 250 (6x easier!)
- **Free deploys**: Increased from ~1/week to 3/week (3x more!)
- **Holder benefits**: Massively increased from 3/week to 10/week!
- **Gas limits**: Free tier 2 gwei, VIP 6 gwei, Holders 10 gwei
- **Cooldowns**: Relaxed - only 30-day for 4+ deploys in ONE day

#### Why These Changes
- Make system more accessible to new users
- Reward holders with significantly better benefits
- Reduce friction while maintaining anti-spam protection
- Better differentiation between tiers

## 📱 Twitter Update Templates

### Latest Update (v2.2.0)
```
🎉 HUGE UPDATE: More generous tiers!

NEW LIMITS:
• Free: 3/week ≤2 gwei (was ~1/week)
• VIP (20k+): 3/week ≤6 gwei
• Holders: 10/week ≤10 gwei (was 3/week!)

EASIER ACCESS:
• Only need 250+ followers (was 1500!)

Hold 5M+ $DOK for massive benefits
CA: 0x69ca61398eCa94D880393522C1Ef5c3D8c058837
```

### Updated Deployment Tiers
```
💎 NEW Deployment Tiers (Jan 2025)

🆓 FREE Tier (250+ followers)
• 3 deployments per week
• Gas must be ≤2 gwei (≤6 gwei for VIP 20k+)
• 6x easier to qualify!

💰 PPD (Pay-Per-Deploy)
• Unlimited deployments
• Any gas price
• Cost: Gas + 0.01 ETH fee

🎯 $DOK Holder Benefits
• 10 FREE deployments per week!
• Works up to 10 gwei gas
• NO platform fees (save 0.01 ETH)
• Hold 5M+ $DOK (0.5% of supply)
```

---

## [2.1.3] - 2024-12-27

### 💎 Enhanced Holder Benefits

#### Increased Weekly Allowance
- **Changed**: Holder benefits from 2/week to 3/week
- **Reason**: Better differentiation from free tier (3x more deployments)
- **Impact**: Holders get 3 free deployments per week vs ~1/week for free users

## [2.1.2] - 2024-12-27

### 🔄 Holder Benefits Adjustment

#### Changed Holder Limits
- **Old**: 2 free deployments per day
- **New**: 2 free deployments per week
- **Reason**: Further reduce gas costs while maintaining holder value
- **Impact**: Holders still get 2x more than free users (~1/week)

### 🎯 Updated Deployment Tiers
- **Free**: ~1/week below 3 gwei (1500+ followers)
- **Free VIP**: ~1/week below 6 gwei (20k+ followers)
- **Holders**: 2/week up to 15 gwei (5M+ $DOK)
- **Pay-Per-Deploy**: Unlimited (gas + 0.01 ETH)

## [2.1.1] - 2024-12-27

### 🔒 More Restrictive Cooldown System

#### Updated Progressive Cooldowns (3 Levels)
- **Much stricter** to encourage holder/paid deployments:
  - 1st free deployment in 7 days: Allowed ✅
  - 2nd free deployment within 7 days → 30-day cooldown ⏳
  - Back-to-back deployments (consecutive days) → 14-day cooldown ⏳
- **Effectively**: Users get ~1 free deploy per week maximum
- **Goal**: Push users to become $DOK holders or use pay-per-deploy
- **Savings**: Dramatically reduces gas waste from free tier abuse

## [2.1.0] - 2024-12-27

### 🛡️ Security & Anti-Abuse Features

#### DOK Ticker Protection
- **Added**: $DOK ticker is now reserved and cannot be deployed by users
- **Behavior**: Attempts to deploy $DOK are silently ignored (no Twitter reply waste)
- **Reason**: Prevents spam/confusion with the bot's own token

#### Progressive Cooldown System
- **Replaced**: Old wasteful "1 free per day" system that reset daily
- **New System**: Smart progressive cooldowns based on usage patterns:
  - 1st deployment: Always allowed ✅
  - 2 deployments on consecutive days → 7-day cooldown
  - 3-4 deployments within 7 days → 14-day cooldown
  - 5+ deployments within 7 days → 30-day cooldown
- **Benefits**: 
  - Dramatically reduces gas waste
  - Prevents daily reset exploitation
  - Fair access for genuine users
  - Progressive penalties for abusers

### 📊 Database Updates
- **Added**: `deployment_cooldowns` table to track:
  - Free deployments in last 7 days
  - Consecutive deployment days
  - Active cooldown periods
  - Total lifetime deployments per user

### 🎯 Improved Fairness
- **Kept**: Duplicate tickers allowed (except $DOK)
- **Reason**: Users with larger followings can compete for higher market caps
- **Balance**: Only the bot's own ticker is protected

### 🔧 Technical Improvements
- **Enhanced**: Rate limit checking now includes cooldown verification
- **Updated**: Deployment tracking for progressive system
- **Added**: Cooldown status in rate limit messages

## [2.0.0] - 2024-12-26

### 🚀 Major Release - Unified Bot System

#### Dual Bot Architecture
- **Twitter Bot**: Monitors mentions and deploys tokens
- **Telegram Bot**: Handles deposits, withdrawals, and account management
- **Unified Runner**: `run_both.py` runs both bots with color-coded output

#### Key Features
- **Free Tier**: 1 free deploy/day when gas ≤ 3 gwei (1500+ followers)
- **Holder Benefits**: 2 free deploys/week up to 15 gwei gas for $DOK holders
- **Pay-Per-Deploy**: Deposit ETH for unlimited deployments
- **Automated System**: No admin intervention needed

### 💰 Financial Features
- **Self-Service Deposits**: Users deposit directly via Telegram
- **Instant Withdrawals**: Full balance withdrawals with gas buffer
- **Balance Protection**: User deposits kept separate from bot funds
- **Fee Structure**: 0.01 ETH platform fee (waived for holders)

### 🔒 Security Features
- **Wallet Verification**: Users must deposit from registered wallet
- **Transaction Tracking**: All deposits/withdrawals logged
- **Duplicate Protection**: Each transaction hash credited only once
- **Balance Safety**: Multiple checks prevent overspending

### 📱 User Experience
- **Twitter Replies**: Automated responses with deployment status
- **Telegram Dashboard**: Real-time gas prices, balance, and stats
- **Queue System**: Up to 10 pending deployments
- **Image Support**: Auto-attach images from parent tweets

### 🎨 Developer Features
- **Colored Output**: Blue for Twitter, Green for Telegram
- **Comprehensive Logging**: Detailed logs for debugging
- **Database Storage**: SQLite for all user data
- **Environment Config**: Easy setup via .env file

## [1.0.0] - 2024-12-20

### Initial Release
- Basic Twitter monitoring via TwitterAPI.io
- Token deployment on Ethereum mainnet
- Simple rate limiting (1 per hour)
- Manual deployment approval process

---

## Upcoming Features (Planned)

### [2.2.0] - Q1 2025
- [ ] Multi-chain support (Base, Arbitrum)
- [ ] Custom token parameters (tax, max wallet)
- [ ] Referral system with rewards
- [ ] Advanced holder tiers (10M, 50M DOK)

### [2.3.0] - Q2 2025
- [ ] Web dashboard for stats
- [ ] API for third-party integrations
- [ ] Automated liquidity management
- [ ] Token presale functionality

## v1.02 Updates - Complete
1. Incentive Distribution split changed:
   - V1.01: 100% of 0.001 ETH to token deployer
   - V1.02: 25% to DOK buyback, 25% incentives, 50% developer

## Deposit System Update - June 27, 2025

### Problem
Users reported deposits not being credited automatically, requiring manual intervention.

### Solution
Implemented robust deposit monitoring using Alchemy Transfers API:

1. **Automatic Monitoring**: 
   - Checks for deposits every 30 seconds
   - Processes deposits automatically with notifications
   - Tracks last checked block to avoid missing transactions

2. **Manual Check Enhancement**:
   - Now checks ENTIRE transaction history (not just 24 hours)
   - Users can claim ANY historical deposits via "Check Deposits" button
   - Shows summary of transfers found, already credited, and invalid amounts

3. **Support Tools**:
   - Added `/credit_tx <tx_hash>` command for manual crediting
   - Validates transaction before crediting to prevent errors

4. **Security**:
   - 3 block confirmation requirement
   - Transaction hash tracking prevents double-crediting
   - Only registered wallets can be credited

### Impact
- Users get credited within 30 seconds automatically
- No more lost deposits
- Support can manually credit edge cases if needed 