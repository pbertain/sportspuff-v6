#!/usr/bin/env python3
"""
API Usage Tracker

This module tracks API usage for Tank01 APIs to stay within the 1000 queries/month limit.
It provides daily usage limits and tracking functionality.
"""

import json
import os
from datetime import datetime, date
from typing import Dict, Optional


class APIUsageTracker:
    """Tracks API usage for different services to stay within limits."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the API usage tracker.
        
        Args:
            data_dir: Directory to store usage data files
        """
        self.data_dir = data_dir
        self.usage_file = os.path.join(data_dir, "api_usage.json")
        self.monthly_limit = 1000
        # Calculate daily limit based on days in current month
        today = date.today()
        days_in_month = (date(today.year, today.month + 1, 1) - date(today.year, today.month, 1)).days
        self.daily_limit = max(1, self.monthly_limit // days_in_month)
        
        # RapidAPI subscription dates (when you subscribed - adjust these!)
        # These determine when the monthly limit resets
        self.subscription_dates = {
            'wnba': '2024-12-24',  # Adjust to your actual WNBA subscription date
            'nfl': '2024-12-24'    # Adjust to your actual NFL subscription date
        }
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Load existing usage data
        self.usage_data = self._load_usage_data()
    
    def _load_usage_data(self) -> Dict:
        """Load usage data from file."""
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_usage_data(self):
        """Save usage data to file."""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save usage data: {e}")
    
    def _get_today_key(self) -> str:
        """Get today's date as a string key."""
        return date.today().isoformat()
    
    def _get_subscription_period(self, service: str) -> str:
        """
        Get the current subscription period for a service.
        
        Args:
            service: Service name ('wnba', 'nfl')
            
        Returns:
            Subscription period string (e.g., '2024-12-24_to_2025-01-24')
        """
        if service not in self.subscription_dates:
            return "unknown"
        
        subscription_date = datetime.strptime(self.subscription_dates[service], '%Y-%m-%d').date()
        today = date.today()
        
        # Calculate how many months since subscription
        months_since_subscription = (today.year - subscription_date.year) * 12 + (today.month - subscription_date.month)
        
        # Calculate the current period start date
        period_start_year = subscription_date.year + (subscription_date.month + months_since_subscription - 1) // 12
        period_start_month = ((subscription_date.month + months_since_subscription - 1) % 12) + 1
        period_start = date(period_start_year, period_start_month, subscription_date.day)
        
        # Calculate the next period start date
        next_period_start_year = period_start_year + (period_start_month // 12)
        next_period_start_month = (period_start_month % 12) + 1
        next_period_start = date(next_period_start_year, next_period_start_month, subscription_date.day)
        
        return f"{period_start.isoformat()}_to_{next_period_start.isoformat()}"
    
    def _is_in_subscription_period(self, service: str, check_date: str) -> bool:
        """
        Check if a date falls within the current subscription period.
        
        Args:
            service: Service name ('wnba', 'nfl')
            check_date: Date string in YYYY-MM-DD format
            
        Returns:
            True if date is in current subscription period
        """
        if service not in self.subscription_dates:
            return False
        
        try:
            check_date_obj = datetime.strptime(check_date, '%Y-%m-%d').date()
            subscription_date = datetime.strptime(self.subscription_dates[service], '%Y-%m-%d').date()
            today = date.today()
            
            # Calculate current period start
            months_since_subscription = (today.year - subscription_date.year) * 12 + (today.month - subscription_date.month)
            period_start_year = subscription_date.year + (subscription_date.month + months_since_subscription - 1) // 12
            period_start_month = ((subscription_date.month + months_since_subscription - 1) % 12) + 1
            period_start = date(period_start_year, period_start_month, subscription_date.day)
            
            # Calculate next period start
            next_period_start_year = period_start_year + (period_start_month // 12)
            next_period_start_month = (period_start_month % 12) + 1
            next_period_start = date(next_period_start_year, next_period_start_month, subscription_date.day)
            
            return period_start <= check_date_obj < next_period_start
            
        except ValueError:
            return False
    
    def can_make_request(self, service: str) -> bool:
        """
        Check if we can make a request for the given service.
        
        Args:
            service: Service name ('wnba', 'nfl')
            
        Returns:
            True if request is allowed, False if limit exceeded
        """
        today_key = self._get_today_key()
        
        # Initialize today's usage if not exists
        if today_key not in self.usage_data:
            self.usage_data[today_key] = {}
        
        if service not in self.usage_data[today_key]:
            self.usage_data[today_key][service] = 0
        
        # Check if we're under the daily limit
        return self.usage_data[today_key][service] < self.daily_limit
    
    def record_request(self, service: str) -> bool:
        """
        Record a request for the given service.
        
        Args:
            service: Service name ('wnba', 'nfl')
            
        Returns:
            True if request was recorded, False if limit exceeded
        """
        if not self.can_make_request(service):
            return False
        
        today_key = self._get_today_key()
        self.usage_data[today_key][service] += 1
        self._save_usage_data()
        return True
    
    def get_usage_stats(self, service: Optional[str] = None) -> Dict:
        """
        Get usage statistics.
        
        Args:
            service: Optional service name to get stats for specific service
            
        Returns:
            Dictionary with usage statistics
        """
        today_key = self._get_today_key()
        
        if service:
            # Get stats for specific service
            if today_key in self.usage_data and service in self.usage_data[today_key]:
                used = self.usage_data[today_key][service]
            else:
                used = 0
            
            return {
                'service': service,
                'date': today_key,
                'used': used,
                'limit': self.daily_limit,
                'remaining': max(0, self.daily_limit - used),
                'percentage': min(100, (used / self.daily_limit) * 100)
            }
        else:
            # Get stats for all services
            stats = {
                'date': today_key,
                'daily_limit': self.daily_limit,
                'services': {}
            }
            
            if today_key in self.usage_data:
                for svc in self.usage_data[today_key]:
                    used = self.usage_data[today_key][svc]
                    stats['services'][svc] = {
                        'used': used,
                        'remaining': max(0, self.daily_limit - used),
                        'percentage': min(100, (used / self.daily_limit) * 100)
                    }
            
            return stats
    
    def get_monthly_usage(self) -> Dict:
        """
        Get subscription-based monthly usage statistics.
        
        Returns:
            Dictionary with monthly usage stats based on subscription periods
        """
        monthly_usage = {}
        subscription_periods = {}
        
        for service in ['wnba', 'nfl']:
            if service in self.subscription_dates:
                period = self._get_subscription_period(service)
                subscription_periods[service] = period
                monthly_usage[service] = 0
                
                # Sum usage for dates within current subscription period
                for date_key, daily_data in self.usage_data.items():
                    if self._is_in_subscription_period(service, date_key):
                        if service in daily_data:
                            monthly_usage[service] += daily_data[service]
        
        total_used = sum(monthly_usage.values())
        
        return {
            'subscription_periods': subscription_periods,
            'monthly_limit': self.monthly_limit,
            'usage': monthly_usage,
            'total_used': total_used,
            'remaining': self.monthly_limit - total_used
        }
    
    def print_usage_summary(self):
        """Print a summary of current usage."""
        today_stats = self.get_usage_stats()
        monthly_stats = self.get_monthly_usage()
        
        print("=== API Usage Summary ===")
        print(f"Date: {today_stats['date']}")
        print(f"Daily Limit: {today_stats['daily_limit']} queries")
        print()
        
        print("Today's Usage:")
        if today_stats['services']:
            for service, stats in today_stats['services'].items():
                print(f"  {service.upper()}: {stats['used']}/{today_stats['daily_limit']} "
                      f"({stats['percentage']:.1f}%) - {stats['remaining']} remaining")
        else:
            print("  No usage today")
        
        print()
        print("Subscription Period Usage:")
        print(f"  Total Used: {monthly_stats['total_used']}/{monthly_stats['monthly_limit']} "
              f"({monthly_stats['total_used']/monthly_stats['monthly_limit']*100:.1f}%)")
        print(f"  Remaining: {monthly_stats['remaining']} queries")
        
        if monthly_stats['usage']:
            print("  By Service:")
            for service, count in monthly_stats['usage'].items():
                period = monthly_stats['subscription_periods'].get(service, 'Unknown')
                print(f"    {service.upper()}: {count} queries (Period: {period})")
        
        print()
        print("Subscription Dates:")
        for service, sub_date in self.subscription_dates.items():
            print(f"  {service.upper()}: {sub_date}")


def main():
    """Test the API usage tracker."""
    tracker = APIUsageTracker()
    
    # Test WNBA usage
    print("Testing WNBA API usage...")
    if tracker.can_make_request('wnba'):
        tracker.record_request('wnba')
        print("✓ WNBA request recorded")
    else:
        print("✗ WNBA daily limit exceeded")
    
    # Test NFL usage
    print("Testing NFL API usage...")
    if tracker.can_make_request('nfl'):
        tracker.record_request('nfl')
        print("✓ NFL request recorded")
    else:
        print("✗ NFL daily limit exceeded")
    
    # Print usage summary
    tracker.print_usage_summary()


if __name__ == "__main__":
    main()
