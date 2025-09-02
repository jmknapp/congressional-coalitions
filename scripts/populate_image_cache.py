#!/usr/bin/env python3
"""
Script to populate the image cache for all members.
This pre-fetches member images from Congress.gov and caches them locally
through our Flask caching system.
"""

import os
import sys
import time
import requests
from datetime import datetime

# Add the parent directory to sys.path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member

def populate_image_cache(base_url="http://localhost:5000", delay=0.1, limit=None):
    """
    Populate the image cache for all members by making requests to our caching endpoint.
    
    Args:
        base_url: Base URL of the Flask application
        delay: Delay between requests to avoid overwhelming the server (seconds)
        limit: Maximum number of members to process (None for all)
    """
    print("Starting image cache population...")
    print(f"Target server: {base_url}")
    print(f"Delay between requests: {delay}s")
    print()
    
    # Get all members from the database
    with get_db_session() as session:
        query = session.query(Member).filter(
            Member.member_id_bioguide.isnot(None)
        ).order_by(Member.last, Member.first)
        
        if limit:
            members = query.limit(limit).all()
            total_in_db = query.count()
            print(f"Found {total_in_db} members in database, processing first {len(members)} (limit: {limit})")
        else:
            members = query.all()
            print(f"Found {len(members)} members to cache images for")
        
        total_members = len(members)
        print()
        
        successful_caches = 0
        failed_caches = 0
        actual_images = 0
        svg_fallbacks = 0
        
        start_time = datetime.now()
        
        for i, member in enumerate(members, 1):
            member_id = member.member_id_bioguide
            member_name = f"{member.first} {member.last}"
            
            try:
                # Make request to our caching endpoint
                response = requests.get(
                    f"{base_url}/api/member-image/{member_id}",
                    timeout=15
                )
                
                if response.status_code == 200:
                    successful_caches += 1
                    
                    # Check if we got an actual image or SVG fallback
                    content_type = response.headers.get('content-type', '')
                    if 'image/jpeg' in content_type or 'image/png' in content_type:
                        actual_images += 1
                        status = "✓ Real photo"
                    elif 'image/svg' in content_type:
                        svg_fallbacks += 1
                        status = "○ SVG avatar"
                    else:
                        status = f"? {content_type}"
                    
                    print(f"[{i:3d}/{total_members}] {status} - {member_name} ({member_id})")
                else:
                    failed_caches += 1
                    print(f"[{i:3d}/{total_members}] ✗ Failed ({response.status_code}) - {member_name} ({member_id})")
                    
            except requests.RequestException as e:
                failed_caches += 1
                print(f"[{i:3d}/{total_members}] ✗ Error - {member_name} ({member_id}): {e}")
            
            # Add delay between requests to be respectful to the server
            if delay > 0 and i < total_members:
                time.sleep(delay)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print()
        print("=" * 60)
        print("CACHE POPULATION SUMMARY")
        print("=" * 60)
        print(f"Total members:        {total_members}")
        print(f"Successful caches:    {successful_caches}")
        print(f"Failed caches:        {failed_caches}")
        print(f"Real photos cached:   {actual_images}")
        print(f"SVG fallbacks:        {svg_fallbacks}")
        print(f"Duration:             {duration}")
        print(f"Average per member:   {duration.total_seconds() / total_members:.2f}s")
        
        if successful_caches == total_members:
            print("\n🎉 All member images successfully cached!")
        elif failed_caches == 0:
            print("\n✅ All requests successful!")
        else:
            print(f"\n⚠️  {failed_caches} requests failed - check server logs")

def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate image cache for all members')
    parser.add_argument('--base-url', default='http://localhost:5000',
                       help='Base URL of the Flask application (default: http://localhost:5000)')
    parser.add_argument('--delay', type=float, default=0.1,
                       help='Delay between requests in seconds (default: 0.1)')
    parser.add_argument('--fast', action='store_true',
                       help='Fast mode with no delay between requests')
    parser.add_argument('--limit', type=int,
                       help='Limit number of members to process (for testing)')
    
    args = parser.parse_args()
    
    if args.fast:
        delay = 0
    else:
        delay = args.delay
    
    try:
        populate_image_cache(args.base_url, delay, args.limit)
    except KeyboardInterrupt:
        print("\n\nCache population interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during cache population: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
