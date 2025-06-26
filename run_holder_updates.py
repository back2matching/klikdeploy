#!/usr/bin/env python3
"""
Run periodic $DOK holder status updates
Can be run as a cron job or scheduled task
"""

import time
import sys
from datetime import datetime
from holder_verification import update_all_holder_statuses

def main():
    """Run holder updates periodically"""
    print(f"\n{'='*60}")
    print(f"🎯 $DOK HOLDER UPDATE SERVICE")
    print(f"{'='*60}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run once and exit
        print("\nRunning single update...")
        update_all_holder_statuses()
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        # Run continuously
        print("\nRunning continuous updates every 30 minutes...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                print(f"\n🔄 Starting update at {datetime.now().strftime('%H:%M:%S')}")
                update_all_holder_statuses()
                
                # Wait 30 minutes
                print(f"\n⏰ Next update in 30 minutes...")
                time.sleep(1800)  # 30 minutes
                
            except KeyboardInterrupt:
                print("\n\n👋 Holder update service stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Error during update: {e}")
                print("Retrying in 5 minutes...")
                time.sleep(300)  # 5 minutes on error

if __name__ == "__main__":
    main() 