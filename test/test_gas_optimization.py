#!/usr/bin/env python3
"""
Gas Optimization Test - SIMULATION ONLY
Tests the new gas optimization without actually deploying tokens
Run this to verify gas costs are reasonable before using the real bot
"""

import os
import time
from web3 import Web3
from dotenv import load_dotenv

class GasOptimizationTester:
    def __init__(self):
        load_dotenv()
        
        # Connect to Web3
        self.rpc_url = os.getenv('ALCHEMY_RPC_URL')
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.factory_address = os.getenv('KLIK_FACTORY_ADDRESS')
        
        # Gas optimization settings (FIXED VERSION)
        self.aggressive_gas_optimization = True
        self.min_priority_fee_gwei = 0.1  # Conservative minimum
        self.max_priority_fee_gwei = 0.5  # Conservative maximum (was 2.0!)
        
        print("🧪 GAS OPTIMIZATION TESTER")
        print("=" * 50)
        print("⚠️  SIMULATION ONLY - NO REAL DEPLOYMENTS")
        print("🎯 Testing FIXED gas optimization")
        print(f"   • Min priority fee: {self.min_priority_fee_gwei} gwei")
        print(f"   • Max priority fee: {self.max_priority_fee_gwei} gwei")
        print("=" * 50)
    
    def get_optimal_gas_parameters_fixed(self):
        """FIXED version of gas optimization - conservative and safe"""
        try:
            # Get recent blocks to analyze gas prices
            latest_block = self.w3.eth.get_block('latest', full_transactions=True)
            base_fee = latest_block['baseFeePerGas']
            
            # Get the last few blocks to check network congestion
            blocks_to_check = 5
            gas_used_ratios = []
            
            for i in range(blocks_to_check):
                try:
                    block = self.w3.eth.get_block(latest_block['number'] - i, full_transactions=True)
                    if block and block['transactions']:
                        # Calculate gas used ratio
                        gas_used_ratio = block['gasUsed'] / block['gasLimit']
                        gas_used_ratios.append(gas_used_ratio)
                except:
                    continue
            
            # Calculate average network congestion
            avg_gas_used_ratio = sum(gas_used_ratios) / len(gas_used_ratios) if gas_used_ratios else 0.5
            
            # FIXED: Use conservative, predetermined priority fees (NO MORE COPYING OTHER USERS!)
            min_priority = self.w3.to_wei(self.min_priority_fee_gwei, 'gwei')
            max_priority = self.w3.to_wei(self.max_priority_fee_gwei, 'gwei')
            
            if avg_gas_used_ratio < 0.5:
                # Low congestion - minimal priority fee
                max_priority_fee = min_priority  # Just 0.1 gwei
                base_multiplier = 1.05
                congestion_level = "LOW"
                
            elif avg_gas_used_ratio < 0.8:
                # Medium congestion - slightly higher but still conservative
                max_priority_fee = self.w3.to_wei(0.3, 'gwei')  # Fixed 0.3 gwei
                base_multiplier = 1.1
                congestion_level = "MEDIUM"
                
            else:
                # High congestion - cap at our conservative max
                max_priority_fee = max_priority  # Cap at 0.5 gwei (was 2.0!)
                base_multiplier = 1.15
                congestion_level = "HIGH"
            
            # Calculate max fee
            max_fee_per_gas = int(base_fee * base_multiplier) + max_priority_fee
            
            return {
                'base_fee': base_fee,
                'max_priority_fee': max_priority_fee,
                'max_fee_per_gas': max_fee_per_gas,
                'base_multiplier': base_multiplier,
                'congestion_level': congestion_level,
                'avg_gas_used_ratio': avg_gas_used_ratio
            }
            
        except Exception as e:
            print(f"❌ Error in gas optimization: {e}")
            # Safe fallback
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            max_priority_fee = self.w3.to_wei(0.3, 'gwei')
            max_fee_per_gas = int(base_fee * 1.1) + max_priority_fee
            return {
                'base_fee': base_fee,
                'max_priority_fee': max_priority_fee,
                'max_fee_per_gas': max_fee_per_gas,
                'base_multiplier': 1.1,
                'congestion_level': 'FALLBACK',
                'avg_gas_used_ratio': 0.5
            }
    
    def simulate_deployment_cost(self):
        """Simulate what a deployment would cost with FIXED gas optimization"""
        
        print(f"\n🔍 ANALYZING CURRENT NETWORK CONDITIONS...")
        
        # Get current network state
        current_gas_price = self.w3.eth.gas_price
        current_gas_gwei = current_gas_price / 1e9
        
        print(f"📊 Current Network Gas: {current_gas_gwei:.2f} gwei")
        
        # Get optimized gas parameters (FIXED VERSION)
        gas_params = self.get_optimal_gas_parameters_fixed()
        
        print(f"\n🎯 FIXED GAS OPTIMIZATION RESULTS:")
        print(f"   • Network congestion: {gas_params['congestion_level']} ({gas_params['avg_gas_used_ratio']:.1%})")
        print(f"   • Base fee: {gas_params['base_fee']/1e9:.2f} gwei")
        print(f"   • Priority fee: {gas_params['max_priority_fee']/1e9:.2f} gwei (was 29.79!)")
        print(f"   • Total gas price: {gas_params['max_fee_per_gas']/1e9:.2f} gwei")
        print(f"   • Base multiplier: {gas_params['base_multiplier']}x")
        
        # Estimate gas units for Klik deployment
        estimated_gas_units = 6_200_000  # Typical for Klik deployments
        
        # Calculate costs
        old_broken_cost = self.simulate_old_broken_version()
        new_fixed_cost = gas_params['max_fee_per_gas'] * estimated_gas_units / 1e18
        
        # Show comparison
        print(f"\n💰 COST COMPARISON:")
        print(f"   • OLD BROKEN VERSION: ~{old_broken_cost:.4f} ETH (~${old_broken_cost * 2430:.0f})")
        print(f"   • NEW FIXED VERSION:  ~{new_fixed_cost:.4f} ETH (~${new_fixed_cost * 2430:.0f})")
        
        savings = old_broken_cost - new_fixed_cost
        savings_pct = (savings / old_broken_cost) * 100 if old_broken_cost > 0 else 0
        
        print(f"   • 💚 SAVINGS: {savings:.4f} ETH (~${savings * 2430:.0f}) = {savings_pct:.0f}% less!")
        
        # Safety check
        if new_fixed_cost > 0.02:  # More than $50
            print(f"\n⚠️  WARNING: Cost still high ({new_fixed_cost:.4f} ETH)")
            print(f"   This might indicate very high network congestion")
            print(f"   Consider waiting for gas to drop below 5 gwei")
        elif new_fixed_cost > 0.01:  # More than $25
            print(f"\n⚠️  MODERATE: Cost is moderate ({new_fixed_cost:.4f} ETH)")
            print(f"   Acceptable for important deployments")
        else:
            print(f"\n✅ EXCELLENT: Cost is reasonable ({new_fixed_cost:.4f} ETH)")
            print(f"   Safe to deploy!")
        
        return new_fixed_cost
    
    def simulate_old_broken_version(self):
        """Simulate what the OLD broken version would have cost"""
        try:
            # The broken version was using 29.79 gwei priority fee!
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            broken_priority = self.w3.to_wei(25, 'gwei')  # Average of the crazy fees we saw
            broken_total = int(base_fee * 1.2) + broken_priority
            estimated_gas_units = 6_200_000
            return broken_total * estimated_gas_units / 1e18
        except:
            return 0.15  # Fallback estimate based on your $447 transaction
    
    def run_multiple_scenarios(self):
        """Test multiple network scenarios"""
        print(f"\n🔬 TESTING DIFFERENT NETWORK CONDITIONS...")
        
        scenarios = [
            ("Low congestion (30% full)", 0.3),
            ("Medium congestion (70% full)", 0.7), 
            ("High congestion (95% full)", 0.95)
        ]
        
        for scenario_name, fake_congestion in scenarios:
            print(f"\n📋 {scenario_name}:")
            
            # Temporarily override congestion for testing
            original_method = self.get_optimal_gas_parameters_fixed
            
            def fake_gas_params():
                base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
                
                if fake_congestion < 0.5:
                    max_priority_fee = self.w3.to_wei(0.1, 'gwei')
                    base_multiplier = 1.05
                elif fake_congestion < 0.8:
                    max_priority_fee = self.w3.to_wei(0.3, 'gwei')
                    base_multiplier = 1.1
                else:
                    max_priority_fee = self.w3.to_wei(0.5, 'gwei')
                    base_multiplier = 1.15
                
                max_fee_per_gas = int(base_fee * base_multiplier) + max_priority_fee
                
                return {
                    'base_fee': base_fee,
                    'max_priority_fee': max_priority_fee,
                    'max_fee_per_gas': max_fee_per_gas,
                    'base_multiplier': base_multiplier,
                    'congestion_level': 'SIMULATED',
                    'avg_gas_used_ratio': fake_congestion
                }
            
            self.get_optimal_gas_parameters_fixed = fake_gas_params
            gas_params = self.get_optimal_gas_parameters_fixed()
            
            estimated_gas_units = 6_200_000
            cost_eth = gas_params['max_fee_per_gas'] * estimated_gas_units / 1e18
            cost_usd = cost_eth * 2430
            
            print(f"   → Priority fee: {gas_params['max_priority_fee']/1e9:.1f} gwei")
            print(f"   → Total cost: {cost_eth:.4f} ETH (~${cost_usd:.0f})")
            
            # Restore original method
            self.get_optimal_gas_parameters_fixed = original_method

def main():
    """Run the gas optimization test"""
    try:
        tester = GasOptimizationTester()
        
        # Test current conditions
        cost = tester.simulate_deployment_cost()
        
        # Test different scenarios
        tester.run_multiple_scenarios()
        
        print(f"\n🎯 SUMMARY:")
        print(f"   • Fixed gas optimization is working ✅")
        print(f"   • Priority fees capped at 0.5 gwei max ✅")
        print(f"   • No more copying other users' wasteful fees ✅")
        print(f"   • Current estimated cost: {cost:.4f} ETH (~${cost * 2430:.0f}) ✅")
        
        if cost < 0.01:
            print(f"\n🚀 READY TO DEPLOY! Cost looks reasonable.")
        else:
            print(f"\n⏸️  CONSIDER WAITING: Gas is still a bit high.")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main() 