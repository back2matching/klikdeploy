# Changelog - Klik Token Deployer

All notable changes to the Klik Token Deployer bot system will be documented in this file.

## [2.1.0] - 2024-12-27

### 🛡️ Security & Anti-Abuse Features

#### DOK Ticker Protection
- **Added**: $DOK ticker is now reserved and cannot be deployed by users
- **Behavior**: Attempts to deploy $DOK are silently ignored (no Twitter reply waste)
- **Reason**: Prevents spam/confusion with the bot's own token

#### Progressive Cooldown System - ULTRA RESTRICTIVE
- **Replaced**: Old wasteful "1 free per day" system that reset daily
- **New System**: Very restrictive 3-level progressive cooldowns:
  - 1st deployment: Always allowed ✅
  - 2nd deployment within 7 days → 14-day cooldown (immediate penalty!)
  - 3+ deployments within 7 days → 30-day cooldown
- **Benefits**: 
  - Dramatically reduces gas waste (saves 80%+ on free deploys)
  - Forces users to become $DOK holders or pay
  - No more daily reset exploitation
  - Much more sustainable long-term

### 💸 Cost Reduction Measures
- **Reduced**: Free deployment gas limit from 3.0 → 2.5 gwei
- **Reduced**: Max deployments per hour from 15 → 10
- **Impact**: Estimated 70-80% reduction in monthly gas costs

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
- **Holder Benefits**: 2 free deploys/day up to 15 gwei gas for $DOK holders
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