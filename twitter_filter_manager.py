#!/usr/bin/env python3
"""
Twitter Filter Rule Manager for TwitterAPI.io
Manages filter rules for real-time WebSocket monitoring
"""

import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Optional
from dotenv import load_dotenv


class TwitterFilterManager:
    """Manages Twitter filter rules for WebSocket monitoring"""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('TWITTERAPI_IO_KEY')
        self.base_url = "https://api.twitterapi.io"
        self.bot_username = os.getenv('BOT_USERNAME', 'DeployOnKlik')
        
        if not self.api_key:
            raise ValueError("Missing TWITTERAPI_IO_KEY in .env")
    
    async def get_rules(self) -> List[Dict]:
        """Get all existing filter rules"""
        url = f"{self.base_url}/oapi/tweet_filter/get_rules"
        headers = {"X-API-Key": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('rules', [])
                else:
                    error = await response.text()
                    print(f"❌ Failed to get rules: {error}")
                    return []
    
    async def add_rule(self, tag: str, value: str, interval_seconds: float = 0.1) -> Optional[str]:
        """Add a new filter rule"""
        url = f"{self.base_url}/oapi/tweet_filter/add_rule"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "tag": tag,
            "value": value,
            "interval_seconds": interval_seconds  # 0.1 seconds for real-time
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    rule_id = data.get('rule_id')
                    print(f"✅ Rule added: {tag} (ID: {rule_id})")
                    return rule_id
                else:
                    error = await response.text()
                    print(f"❌ Failed to add rule: {error}")
                    return None
    
    async def update_rule(self, rule_id: str, tag: str, value: str, 
                         interval_seconds: float = 0.1, is_effect: int = 1) -> bool:
        """Update an existing rule and activate it"""
        url = f"{self.base_url}/oapi/tweet_filter/update_rule"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "rule_id": rule_id,
            "tag": tag,
            "value": value,
            "interval_seconds": interval_seconds,
            "is_effect": is_effect  # 1 = active, 0 = inactive
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    status = "activated" if is_effect == 1 else "deactivated"
                    print(f"✅ Rule {status}: {tag} (ID: {rule_id})")
                    return True
                else:
                    error = await response.text()
                    print(f"❌ Failed to update rule: {error}")
                    return False
    
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a filter rule"""
        url = f"{self.base_url}/oapi/tweet_filter/delete_rule"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {"rule_id": rule_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    print(f"✅ Rule deleted: {rule_id}")
                    return True
                else:
                    error = await response.text()
                    print(f"❌ Failed to delete rule: {error}")
                    return False
    
    async def setup_deployment_rule(self, interval_seconds: float = 1.5) -> bool:
        """Set up the main rule for deployment mentions"""
        # Check existing rules
        existing_rules = await self.get_rules()
        
        # Look for our deployment rule
        deployment_rule = None
        for rule in existing_rules:
            if rule['tag'] == f"{self.bot_username}_mentions":
                deployment_rule = rule
                break
        
        # The filter value to monitor mentions with $ symbol
        filter_value = f"@{self.bot_username} ($)"
        
        if deployment_rule:
            # Update existing rule and ensure it's active
            print(f"📝 Found existing rule: {deployment_rule['tag']}")
            success = await self.update_rule(
                rule_id=deployment_rule['rule_id'],
                tag=deployment_rule['tag'],
                value=filter_value,
                interval_seconds=interval_seconds,  # Custom interval
                is_effect=1  # Activate it
            )
            return success
        else:
            # Create new rule
            print(f"🆕 Creating new rule for @{self.bot_username} mentions...")
            rule_id = await self.add_rule(
                tag=f"{self.bot_username}_mentions",
                value=filter_value,
                interval_seconds=interval_seconds
            )
            
            if rule_id:
                # Activate the rule
                return await self.update_rule(
                    rule_id=rule_id,
                    tag=f"{self.bot_username}_mentions",
                    value=filter_value,
                    interval_seconds=interval_seconds,
                    is_effect=1
                )
            return False
    
    async def setup_verification_rule(self, interval_seconds: float = 15.0) -> bool:
        """Set up a separate rule for verification tweets (less frequent)"""
        # Check existing rules
        existing_rules = await self.get_rules()
        
        # Look for our verification rule
        verification_rule = None
        for rule in existing_rules:
            if rule['tag'] == f"{self.bot_username}_verification":
                verification_rule = rule
                break
        
        # The filter value to monitor verification tweets
        # Pattern: "@DeployOnKlik !verify user [CODE] in order to use start claiming fees from @[username]"
        filter_value = f"@{self.bot_username} !verify user"
        
        if verification_rule:
            # Update existing rule and ensure it's active
            print(f"📝 Found existing verification rule: {verification_rule['tag']}")
            success = await self.update_rule(
                rule_id=verification_rule['rule_id'],
                tag=verification_rule['tag'],
                value=filter_value,
                interval_seconds=interval_seconds,  # Higher interval for verification
                is_effect=1  # Activate it
            )
            return success
        else:
            # Create new rule
            print(f"🆕 Creating new verification rule for @{self.bot_username}...")
            rule_id = await self.add_rule(
                tag=f"{self.bot_username}_verification",
                value=filter_value,
                interval_seconds=interval_seconds
            )
            
            if rule_id:
                # Activate the rule
                return await self.update_rule(
                    rule_id=rule_id,
                    tag=f"{self.bot_username}_verification",
                    value=filter_value,
                    interval_seconds=interval_seconds,
                    is_effect=1
                )
            return False
    
    async def delete_verification_rule(self) -> bool:
        """Delete the verification rule to avoid duplicate processing"""
        existing_rules = await self.get_rules()
        
        # Look for our verification rule
        verification_rule = None
        for rule in existing_rules:
            if rule['tag'] == f"{self.bot_username}_verification":
                verification_rule = rule
                break
        
        if verification_rule:
            print(f"🗑️  Found verification rule to delete: {verification_rule['tag']}")
            success = await self.delete_rule(verification_rule['rule_id'])
            if success:
                print(f"✅ Deleted verification rule - deployment rule will handle all tweets")
            return success
        else:
            print(f"ℹ️  No verification rule found to delete")
            return True
    
    async def setup_deployment_only(self) -> bool:
        """Set up only the deployment rule (handles both deployments and verification)"""
        print("🔧 Setting up deployment rule only...")
        print("💡 This rule will handle both deployments AND verification tweets")
        
        # First, delete any existing verification rule to avoid duplicates
        await self.delete_verification_rule()
        
        # Set up only the deployment rule
        deployment_success = await self.setup_deployment_rule(interval_seconds=3.0)
        
        return deployment_success
    
    async def show_all_rules(self):
        """Display all current filter rules"""
        rules = await self.get_rules()
        
        if not rules:
            print("📭 No filter rules found")
            return
        
        print(f"\n📋 CURRENT FILTER RULES ({len(rules)} total)")
        print("=" * 60)
        
        for rule in rules:
            rule_id = rule['rule_id']
            tag = rule['tag']
            value = rule['value']
            interval = rule['interval_seconds']
            is_active = rule.get('is_effect', 0) == 1
            
            status = "🟢 ACTIVE" if is_active else "🔴 INACTIVE"
            
            print(f"\n{status} Rule: {tag}")
            print(f"   ID: {rule_id}")
            print(f"   Filter: {value}")
            print(f"   Interval: {interval}s")
    
    async def cleanup_inactive_rules(self):
        """Remove all inactive rules"""
        rules = await self.get_rules()
        inactive_count = 0
        
        for rule in rules:
            if rule.get('is_effect', 0) == 0:
                await self.delete_rule(rule['rule_id'])
                inactive_count += 1
        
        if inactive_count > 0:
            print(f"🧹 Cleaned up {inactive_count} inactive rules")
        else:
            print("✨ No inactive rules to clean up")


async def main():
    """Main function to manage filter rules"""
    manager = TwitterFilterManager()
    
    print("🚀 TWITTER FILTER RULE MANAGER")
    print("=" * 50)
    
    # Show current rules
    await manager.show_all_rules()
    
    # Option to delete all rules
    if await manager.get_rules():
        print("\n🗑️  Would you like to delete ALL existing rules? (y/N): ", end="")
        if input().lower() == 'y':
            rules = await manager.get_rules()
            for rule in rules:
                await manager.delete_rule(rule['rule_id'])
            print(f"✅ Deleted {len(rules)} rules")
    
    # Set up only deployment rule (handles both deployments and verification)
    print(f"\n⚙️  Setting up filter rule for: @{manager.bot_username}")
    print(f"📦 Deployment rule: @{manager.bot_username} ($) - 3s interval")
    print(f"🔐 This rule will also handle verification tweets automatically")
    
    success = await manager.setup_deployment_only()
    
    if success:
        print("\n✅ Deployment filter rule is active and ready for WebSocket monitoring!")
        print(f"📡 Single rule handles: @{manager.bot_username} ($) - 3s interval")
        print(f"📡 Processes: Deployments + Verification tweets")
        print("\n💡 Remember: Billing starts when rules are active!")
        print("💰 Cost savings: Using 1 rule instead of 2!")
    else:
        print("\n❌ Failed to set up deployment filter rule")
    
    # Show final state
    print("\n📊 FINAL RULE STATUS:")
    await manager.show_all_rules()


if __name__ == "__main__":
    asyncio.run(main()) 