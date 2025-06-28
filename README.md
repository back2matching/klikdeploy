# Klik Deploy - Twitter-Triggered Token Deployer 🚀

<div align="center">

[![Ethereum](https://img.shields.io/badge/Ethereum-Mainnet-blue)](https://ethereum.org)
[![Twitter](https://img.shields.io/badge/Twitter-Bot-1DA1F2)](https://twitter.com/DeployOnKlik)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-0088cc)](https://t.me/DeployOnKlikBot)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Deploy ERC-20 tokens on Ethereum instantly by tweeting!**  
*The world's first Twitter-triggered token deployer with integrated wallet management*

[Live Demo](https://twitter.com/DeployOnKlik) • [Telegram Bot](https://t.me/DeployOnKlikBot) • [Channel](https://t.me/DeployOnKlik)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [How It Works](#-how-it-works)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Deployment Tiers](#-deployment-tiers)
- [Setup Guide](#-setup-guide)
- [API Documentation](#-api-documentation)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [Development](#-development)
- [Contributing](#-contributing)

## 🎯 Overview

Klik Deploy revolutionizes token deployment on Ethereum by enabling users to launch tokens with a simple tweet. Built on the [Klik Finance](https://klik.finance) factory, it combines Twitter's social reach with blockchain technology for instant token creation.

### Key Statistics
- ⚡ **Response Time**: 1-3 seconds
- 🎯 **Success Rate**: 95%+
- ⛽ **Gas Efficiency**: ~6.5M units per deployment
- 🔒 **Security**: Multi-layer verification system
- 💎 **Vanity Addresses**: 0x69 prefix generation

## 🚀 Features

### Core Features
- **🐦 Twitter Integration**: Deploy tokens by mentioning @DeployOnKlik
- **🤖 Telegram Bot**: Full wallet management and deployment system
- **🖼️ Auto Image Support**: Pulls images from tweets for token branding
- **💎 Tiered System**: Free, Holder, and Paid deployment options
- **🎯 Vanity Addresses**: Generate 0x69 prefixed addresses
- **📊 Real-time Monitoring**: WebSocket-based Twitter monitoring
- **🔄 Queue System**: Handles multiple deployments efficiently
- **🛡️ Security**: Wallet verification and balance protection

### Technical Features
- **EIP-1559 Support**: Optimized gas management
- **CREATE2 Deployment**: Predictable token addresses
- **Atomic Operations**: Race condition prevention
- **IPFS Integration**: Decentralized metadata storage
- **SQLite Database**: Reliable data persistence
- **Async Processing**: High-performance deployment queue

## 🎮 How It Works

### For Users

1. **Tweet to Deploy**
   ```
   @DeployOnKlik $TICKER - Token Name
   ```
   
2. **Bot Deploys Token**
   - Validates request and checks eligibility
   - Deploys via Klik Finance factory
   - Uploads metadata to IPFS
   - Links to original tweet

3. **Receive Confirmation**
   - Twitter reply with DexScreener link
   - Token address and transaction details
   - Telegram notification (if enabled)

### Example Deployments

```bash
# Basic deployment
@DeployOnKlik $MEME

# With custom name (using dash)
@DeployOnKlik $PEPE - Pepe Token

# With custom name (using plus)
@DeployOnKlik $DOGE + DogeCoin

# Reply with image (uses parent tweet's image)
@DeployOnKlik $CAT + CatCoin
```

## 💎 Deployment Tiers

### 🆓 FREE Tier
- **Requirements**: 
  - Gas ≤ 2 gwei
  - 250+ Twitter followers
  - 3 deployments per week
- **VIP Status**: 20k+ followers get gas ≤ 6 gwei
- **Cost**: Bot pays all gas fees

### 🎯 HOLDER Tier ($DOK)
- **Requirements**:
  - Hold 5M+ DOK tokens (0.5% of supply)
  - Verify wallet ownership (one-time deposit)
  - Gas ≤ 10 gwei
- **Benefits**:
  - 10 FREE deployments per week
  - NO platform fees (save 0.01 ETH)
  - Priority support
- **Token**: [0x69ca61398eCa94D880393522C1Ef5c3D8c058837](https://dexscreener.com/ethereum/0x69ca61398eca94d880393522c1ef5c3d8c058837)

### 💰 PAY-PER-DEPLOY Tier
- **Requirements**: Deposit ETH to bot wallet
- **Benefits**:
  - Unlimited deployments
  - No follower requirements
  - Works at any gas price
- **Cost**: Gas + 0.01 ETH fee (waived for holders)

## 🔧 Architecture

### System Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Twitter API    │────▶│  Token Deployer │────▶│  Klik Factory   │
│  (Monitoring)   │     │    (Python)     │     │  (Smart Contract)│
│                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼────────┐       ┌───────▼────────┐
            │                │       │                │
            │  Telegram Bot  │       │  SQLite DB     │
            │  (Management)  │       │  (Persistence) │
            │                │       │                │
            └────────────────┘       └────────────────┘
```

### Database Schema

```sql
-- Core Tables
deployments      -- Token deployment records
users            -- User accounts and balances
deposits         -- ETH deposit tracking
daily_limits     -- Rate limiting per user
withdrawals      -- Withdrawal history
```

### Security Layers

1. **Wallet Verification**: Deposit proof required for holders
2. **Balance Segregation**: User funds protected from bot operations
3. **Rate Limiting**: Multi-tier spam prevention
4. **Queue System**: Sequential processing prevents conflicts
5. **Atomic Operations**: Database integrity protection

## 🛠️ Setup Guide

### Prerequisites

- Python 3.9+
- Ethereum wallet with ETH
- Twitter Developer Account (for replies)
- TwitterAPI.io account (for monitoring)
- Telegram Bot Token
- Pinata or Web3.storage account (optional)

### Quick Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/klik-deploy.git
   cd klik-deploy
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run Both Bots**
   ```bash
   python run_both.py
   ```

### Environment Variables

```bash
# Wallet Configuration
PRIVATE_KEY=your_private_key
DEPLOYER_ADDRESS=your_wallet_address

# Blockchain
ALCHEMY_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
KLIK_FACTORY_ADDRESS=0x930f9FA91E1E46d8e44abC3517E2965C6F9c4763

# Twitter Monitoring (TwitterAPI.io)
TWITTERAPI_IO_KEY=your_key

# Twitter Replies (Optional)
TWITTER_API_KEY=your_key
TWITTER_API_SECRET=your_secret
TWITTER_ACCESS_TOKEN=your_token
TWITTER_ACCESS_TOKEN_SECRET=your_token_secret

# Telegram
TELEGRAM_DEPLOYER_BOT=your_bot_token
TELEGRAM_CHANNEL_ID=@YourChannel

# Bot Configuration
BOT_USERNAME=DeployOnKlik
MIN_FOLLOWER_COUNT=250
MAX_DEPLOYS_PER_HOUR=15
```

### Detailed Setup

See [Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md) for:
- Twitter API configuration
- Telegram bot creation
- IPFS service setup
- Production deployment

## 📚 API Documentation

### Twitter Mention Format

```
@DeployOnKlik $SYMBOL [- Token Name]
@DeployOnKlik $SYMBOL [+ Token Name]

Required:
- $ prefix for symbol
- Symbol: 1-16 alphanumeric characters
- Name: Optional, up to 30 characters
- Separator: Use - or + between symbol and name
```

### Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Open main menu |
| `/link <twitter>` | Link Twitter account |
| `/wallet <address>` | Register ETH wallet |
| `/withdraw` | Withdraw full balance |

### Deployment Response

```json
{
  "token_address": "0x69...",
  "tx_hash": "0x...",
  "symbol": "MEME",
  "name": "Meme Token",
  "deployer": "@username",
  "gas_used": "6500000",
  "cost": "0.0234 ETH"
}
```

## 🔒 Security

### Security Features

- ✅ **Private Key Protection**: Never exposed in logs
- ✅ **Balance Segregation**: User deposits protected
- ✅ **Atomic Operations**: Prevents race conditions
- ✅ **Input Validation**: Strict parameter checking
- ✅ **Rate Limiting**: Multi-layer spam protection
- ✅ **Wallet Verification**: Ownership proof required

### Best Practices

1. **Never commit `.env` file**
2. **Use separate wallet for bot operations**
3. **Monitor bot balance regularly**
4. **Keep minimal ETH in hot wallet**
5. **Regular security audits**

### Vulnerability Reporting

Found a security issue? Please email security@klikfinance.com

## 🔧 Troubleshooting

### Common Issues

**"No new deposits found"**
- Ensure sending from registered wallet
- Amount must be 0.03-1 ETH
- Wait for 3+ confirmations

**"Gas too high"**
- Free tier only works when gas ≤ 2 gwei (VIP: ≤ 6 gwei)
- Deposit ETH for paid deployments
- Check https://etherscan.io/gastracker

**Bot not responding**
- Check TwitterAPI.io connection
- Verify filter rules include mentions
- Ensure bot has sufficient balance

**Colors not showing**
- Windows: Use Windows Terminal
- Mac/Linux: Most terminals support colors

### Debug Mode

```bash
# Enable debug logging
DEBUG_MEDIA=true python klik_token_deployer.py

# Test deployment
python klik_token_deployer.py --test
```

## 🚀 Development

### Project Structure

```
klik-deploy/
├── klik_token_deployer.py    # Main Twitter bot
├── telegram_deposit_bot.py    # Telegram management bot
├── twitter_monitor.py         # Real-time monitoring
├── holder_verification.py     # $DOK holder checks
├── run_both.py               # Combined launcher
├── requirements.txt          # Python dependencies
├── deployments.db           # SQLite database
└── docs/                    # Documentation
    ├── COMPLETE_SETUP_GUIDE.md
    └── holder_system.md
```

### Running Tests

```bash
# Test token deployment
python klik_token_deployer.py --test

# Test holder verification
python holder_verification.py testuser

# Check gas prices
python -c "from klik_token_deployer import *; print(KlikTokenDeployer().get_eth_balance())"
```

### Monitoring

```bash
# Run with colored output
python run_both.py

# Background with screen
screen -S klik
python run_both.py
# Detach: Ctrl+A, D

# Background with tmux
tmux new -s klik
python run_both.py
# Detach: Ctrl+B, D
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add tests for new features
- Update documentation
- Check for security issues
- Test on testnet first

## 📊 Statistics & Performance

- **Average Deployment Time**: 12-15 seconds
- **Gas Usage**: 6.0-6.5M units
- **IPFS Upload**: <2 seconds
- **Queue Processing**: 1 deployment/3 seconds
- **Database Size**: ~100KB per 1000 deployments

## 🎯 Roadmap

- [ ] Multi-chain support (Base, Arbitrum)
- [ ] NFT collection deployment
- [ ] Advanced token features (tax, liquidity)
- [ ] Web dashboard
- [ ] Mobile app
- [ ] DAO governance

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Klik Finance](https://klik.finance) - Smart contract factory
- [TwitterAPI.io](https://twitterapi.io) - Real-time monitoring
- [Alchemy](https://alchemy.com) - Ethereum RPC
- Community contributors and testers

---

<div align="center">

**Built with ❤️ for the Ethereum community** 

[Website](https://klik.finance) • [Twitter](https://twitter.com/DeployOnKlik) • [Telegram](https://t.me/DeployOnKlik)

</div> 