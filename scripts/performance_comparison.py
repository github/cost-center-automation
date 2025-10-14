#!/usr/bin/env python3
"""
Performance comparison script to demonstrate cost center caching benefits.

This script simulates the performance difference between cached and non-cached
cost center operations by creating mock API calls and measuring execution time.
"""

import time
from typing import Set
import json
from src.cost_center_cache import CostCenterCache


class MockGitHubManager:
    """Mock GitHub manager that simulates API call delays."""
    
    def __init__(self, api_delay: float = 0.1):
        self.api_delay = api_delay
        self.api_calls = 0
        
    def create_cost_center(self, name: str) -> str:
        """Simulate API call delay and return mock cost center ID."""
        time.sleep(self.api_delay)  # Simulate network delay
        self.api_calls += 1
        return f"cc_{hash(name) % 100000:05d}"


def simulate_without_cache(cost_centers: Set[str], github_manager: MockGitHubManager) -> dict:
    """Simulate cost center resolution without caching."""
    start_time = time.time()
    
    cost_center_map = {}
    for cost_center_name in cost_centers:
        cost_center_id = github_manager.create_cost_center(cost_center_name)
        cost_center_map[cost_center_name] = cost_center_id
    
    end_time = time.time()
    return {
        'duration': end_time - start_time,
        'api_calls': github_manager.api_calls,
        'mappings': cost_center_map
    }


def simulate_with_cache(cost_centers: Set[str], github_manager: MockGitHubManager, cache: CostCenterCache) -> dict:
    """Simulate cost center resolution with caching."""
    start_time = time.time()
    
    cost_center_map = {}
    cache_hits = 0
    api_calls_before = github_manager.api_calls
    
    for cost_center_name in cost_centers:
        # Check cache first
        cached_id = cache.get_cost_center_id(cost_center_name)
        
        if cached_id:
            cost_center_map[cost_center_name] = cached_id
            cache_hits += 1
        else:
            # Cache miss - make API call
            cost_center_id = github_manager.create_cost_center(cost_center_name)
            cost_center_map[cost_center_name] = cost_center_id
            # Cache the result
            cache.set_cost_center_id(cost_center_name, cost_center_id)
    
    end_time = time.time()
    api_calls_made = github_manager.api_calls - api_calls_before
    
    return {
        'duration': end_time - start_time,
        'api_calls': api_calls_made,
        'cache_hits': cache_hits,
        'mappings': cost_center_map
    }


def main():
    print("🚀 Cost Center Caching Performance Comparison")
    print("=" * 50)
    
    # Test data - simulate 20 cost centers (typical enterprise scenario)
    cost_centers = {
        "Engineering - Backend", "Engineering - Frontend", "Engineering - Mobile",
        "Engineering - DevOps", "Engineering - Security", "Product - Core",
        "Product - Growth", "Product - Analytics", "Design - UX", "Design - Visual",
        "Marketing - Growth", "Marketing - Content", "Sales - Enterprise",
        "Sales - SMB", "Customer Success", "Support", "HR", "Finance",
        "Legal", "Operations"
    }
    
    print(f"📊 Testing with {len(cost_centers)} cost centers")
    print(f"🌐 Simulating 100ms API delay per call (typical network latency)")
    print()
    
    # Initialize cache (but don't clear it initially)
    cache = CostCenterCache()
    cache.clear_cache()  # Start with clean slate for fair comparison
    
    # Test 1: Without cache (cold start)
    print("🥶 Test 1: Cold start (no cache)")
    github_manager1 = MockGitHubManager(api_delay=0.1)
    result1 = simulate_without_cache(cost_centers.copy(), github_manager1)
    
    print(f"   Duration: {result1['duration']:.2f} seconds")
    print(f"   API calls: {result1['api_calls']}")
    print(f"   Avg per cost center: {result1['duration']/len(cost_centers)*1000:.0f}ms")
    print()
    
    # Pre-populate cache with first run's data
    for name, cost_center_id in result1['mappings'].items():
        cache.set_cost_center_id(name, cost_center_id)
    
    # Test 2: With cache (warm cache - simulate second run)
    print("🔥 Test 2: Warm cache (second run)")
    github_manager2 = MockGitHubManager(api_delay=0.1)
    result2 = simulate_with_cache(cost_centers.copy(), github_manager2, cache)
    
    print(f"   Duration: {result2['duration']:.2f} seconds")
    print(f"   API calls: {result2['api_calls']}")
    print(f"   Cache hits: {result2['cache_hits']}")
    print(f"   Cache hit rate: {result2['cache_hits']/len(cost_centers)*100:.1f}%")
    print(f"   Avg per cost center: {result2['duration']/len(cost_centers)*1000:.0f}ms")
    print()
    
    # Performance comparison
    speedup = result1['duration'] / result2['duration'] if result2['duration'] > 0 else float('inf')
    api_reduction = ((result1['api_calls'] - result2['api_calls']) / result1['api_calls'] * 100) if result1['api_calls'] > 0 else 0
    time_saved = result1['duration'] - result2['duration']
    
    print("📈 Performance Improvement")
    print("-" * 30)
    print(f"   Speed improvement: {speedup:.1f}x faster")
    print(f"   Time saved: {time_saved:.2f} seconds ({time_saved*1000:.0f}ms)")
    print(f"   API calls reduced: {api_reduction:.1f}%")
    print(f"   Network requests saved: {result1['api_calls'] - result2['api_calls']}")
    print()
    
    # Cache statistics
    stats = cache.get_cache_stats()
    print("💾 Final Cache Statistics")
    print("-" * 30)
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Valid entries: {stats['valid_entries']}")
    print(f"   Cache efficiency: {stats['valid_entries']/stats['total_entries']*100:.1f}%")
    print(f"   Storage: {stats['cache_file']}")
    print()
    
    print("💡 Key Takeaways:")
    print("   • Caching provides significant performance improvements")
    print("   • Especially beneficial for large teams with many cost centers") 
    print("   • Essential for CI/CD pipelines and automated workflows")
    print("   • Reduces GitHub API rate limit consumption")
    
    # Test 3: Mixed scenario (some cached, some new)
    print()
    print("🎯 Test 3: Mixed scenario (adding 5 new cost centers)")
    new_cost_centers = cost_centers | {"New Team 1", "New Team 2", "New Team 3", "New Team 4", "New Team 5"}
    
    github_manager3 = MockGitHubManager(api_delay=0.1)
    result3 = simulate_with_cache(new_cost_centers, github_manager3, cache)
    
    print(f"   Duration: {result3['duration']:.2f} seconds")
    print(f"   API calls: {result3['api_calls']} (only for new cost centers)")
    print(f"   Cache hits: {result3['cache_hits']}")
    print(f"   Cache hit rate: {result3['cache_hits']/len(new_cost_centers)*100:.1f}%")
    print(f"   Avg per cost center: {result3['duration']/len(new_cost_centers)*1000:.0f}ms")
    
    print("\n✅ Performance comparison complete!")


if __name__ == "__main__":
    main()