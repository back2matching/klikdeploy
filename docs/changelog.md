# Changelog - Klik Token Deployer

All notable changes to the Klik Token Deployer bot system will be documented in this file.

## 📱 Twitter Update Templates

### Latest Update (v2.1.2)
```
🚨 UPDATE: ALL deployment limits adjusted for sustainability

FREE users: ~1 deploy/week
HOLDER benefits: 2 deploys/WEEK (was 2/day)

Why? To ensure long-term sustainability while keeping value for holders.

Hold 5M+ $DOK → Still get 2 FREE/week up to 15 gwei
CA: 0x69ca61398eCa94D880393522C1Ef5c3D8c058837
```

### For $DOK Holders
```
🎯 $DOK HOLDERS: Benefits adjusted for sustainability

Your benefits:
• 2 FREE deploys/week (was 2/day)
• Up to 15 gwei gas
• NO platform fees

Still more than free users who get ~1/week!

CA: 0x69ca61398eCa94D880393522C1Ef5c3D8c058837
```

---

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