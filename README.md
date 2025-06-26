# Klik Deploy - Twitter-Triggered Token Deployer 🚀

Deploy tokens on Ethereum instantly by tweeting! Just mention the bot with a $ symbol and watch your token launch in seconds.

## 🎯 Features

- **Twitter-Triggered Deployments**: Tweet `@DeployOnKlik $TICKER` to deploy
- **Tiered System**:
  - **FREE**: 1 deploy/day when gas ≤ 3 gwei (1500+ followers required)
  - **HOLDER**: 2 deploys/day for $DOK holders (5M+ tokens)
  - **PAID**: Unlimited deploys with ETH deposits
- **Telegram Bot Integration**: Manage deposits, withdrawals, and check balances
- **Real-time Monitoring**: 1-3 second response time via TwitterAPI.io
- **Automatic Image Support**: Pulls images from tweets for token branding
- **Vanity Addresses**: Generates 0x69 prefixed addresses for tokens

## 🚀 Quick Start

### Deploy a Token
```
Tweet: @DeployOnKlik $MEME - Meme Token
```

### Manage Your Account
1. Open [@DeployOnKlikBot](https://t.me/DeployOnKlikBot) on Telegram
2. Link your Twitter account
3. Register your wallet
4. Deposit ETH for paid deployments

## 💎 $DOK Token Holders

Hold 5,000,000+ DOK tokens (0.5% of supply) for:
- 2 FREE deployments per day
- Gas limit up to 15 gwei
- NO platform fees (save 0.01 ETH per deploy)
- Must deposit once to verify wallet ownership

**Token**: [0x69ca61398eCa94D880393522C1Ef5c3D8c058837](https://dexscreener.com/ethereum/0x69ca61398eca94d880393522c1ef5c3d8c058837)

## 🔧 Technical Stack

- **Smart Contracts**: Klik Finance factory on Ethereum
- **Twitter Integration**: Real-time WebSocket via TwitterAPI.io
- **Bot Framework**: Python with Web3.py
- **Database**: SQLite for user management
- **Telegram Bot**: Automated deposit/withdrawal system

## 📋 Setup

1. Clone the repository:
```bash
git clone https://github.com/back2matching/klikdeploy.git
cd klikdeploy
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure `.env` file with your API keys

4. Run both bots:
```bash
python run_both.py
```

## 🛡️ Security Features

- **Wallet Verification**: Users must deposit once to prove wallet ownership
- **Protected User Funds**: Bot balance segregated from user deposits
- **Automatic Safety Checks**: Monitors balance health every 5 minutes
- **Rate Limiting**: Prevents spam and abuse

## 📚 Documentation

- [Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md)
- [Holder System](docs/holder_system.md)

## ⚡ Live Stats

- Response Time: 1-3 seconds
- Gas Efficiency: ~6.5M units per deployment
- Success Rate: 95%+

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

---

**Built with ❤️ for the Ethereum community** 