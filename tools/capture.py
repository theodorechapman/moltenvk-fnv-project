#!/usr/bin/env python3
"""
Error Capture and Analysis Tool for MoltenVK Development

This tool:
1. Runs FNV (or other test apps) with full logging
2. Captures and categorizes errors
3. Identifies the next issue to fix
4. Tracks progress over time

Usage:
    ./capture.py run          # Run FNV and capture errors
    ./capture.py analyze      # Analyze existing logs
    ./capture.py progress     # Show progress over time
    ./capture.py next         # Show next issue to fix
"""

import subprocess
import re
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(os.environ.get('PROJECT_ROOT', Path.home() / 'Coding' / 'moltenvk-fnv-project'))
LOGS_DIR = PROJECT_ROOT / 'logs'
PROGRESS_FILE = PROJECT_ROOT / 'progress.json'

# Error categories and their priority
ERROR_CATEGORIES = {
    'extension_missing': {
        'patterns': [
            r'extension.*not.*support',
            r'VK_EXT_\w+ not available',
            r'required extension.*missing',
        ],
        'priority': 1,
        'description': 'Missing Vulkan extension',
    },
    'feature_unsupported': {
        'patterns': [
            r'feature.*not.*support',
            r'unsupported.*feature',
            r'geometryShader.*false',
            r'transformFeedback.*false',
        ],
        'priority': 2,
        'description': 'Unsupported Vulkan feature',
    },
    'shader_compilation': {
        'patterns': [
            r'shader.*compil.*fail',
            r'SPIR-V.*error',
            r'MSL.*error',
            r'shader.*invalid',
        ],
        'priority': 3,
        'description': 'Shader compilation failure',
    },
    'pipeline_creation': {
        'patterns': [
            r'pipeline.*fail',
            r'vkCreate.*Pipeline.*error',
            r'pipeline state.*invalid',
        ],
        'priority': 4,
        'description': 'Pipeline creation failure',
    },
    'memory_error': {
        'patterns': [
            r'memory.*fail',
            r'allocation.*fail',
            r'out of.*memory',
            r'VK_ERROR_OUT_OF.*MEMORY',
        ],
        'priority': 5,
        'description': 'Memory allocation error',
    },
    'validation_error': {
        'patterns': [
            r'validation.*error',
            r'VUID-',
            r'Validation Error',
        ],
        'priority': 6,
        'description': 'Vulkan validation error',
    },
    'general_error': {
        'patterns': [
            r'error',
            r'fail',
            r'crash',
        ],
        'priority': 10,
        'description': 'General error',
    },
}


class ErrorCapture:
    def __init__(self):
        self.errors = []
        self.categorized = defaultdict(list)
        
    def parse_logs(self):
        """Parse all log files and extract errors."""
        log_files = list(LOGS_DIR.glob('*.log'))
        
        for log_file in log_files:
            source = log_file.stem
            with open(log_file, 'r', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    error = self._categorize_line(line, source, line_num)
                    if error:
                        self.errors.append(error)
                        self.categorized[error['category']].append(error)
        
        return self
    
    def _categorize_line(self, line, source, line_num):
        """Categorize a log line if it's an error."""
        line_lower = line.lower()
        
        # Skip non-error lines
        if not any(word in line_lower for word in ['error', 'fail', 'unsupport', 'missing', 'invalid']):
            return None
        
        for category, info in ERROR_CATEGORIES.items():
            for pattern in info['patterns']:
                if re.search(pattern, line_lower):
                    return {
                        'category': category,
                        'priority': info['priority'],
                        'description': info['description'],
                        'source': source,
                        'line_num': line_num,
                        'message': line.strip(),
                        'timestamp': datetime.now().isoformat(),
                    }
        
        return None
    
    def get_summary(self):
        """Get a summary of all errors."""
        summary = {
            'total_errors': len(self.errors),
            'by_category': {},
            'unique_messages': set(),
        }
        
        for category, errors in self.categorized.items():
            summary['by_category'][category] = {
                'count': len(errors),
                'priority': ERROR_CATEGORIES[category]['priority'],
                'description': ERROR_CATEGORIES[category]['description'],
            }
            for error in errors:
                summary['unique_messages'].add(error['message'][:100])
        
        summary['unique_messages'] = list(summary['unique_messages'])
        return summary
    
    def get_next_to_fix(self):
        """Get the highest priority error to fix next."""
        if not self.errors:
            return None
        
        # Sort by priority, then by frequency
        category_counts = [(cat, len(errs), ERROR_CATEGORIES[cat]['priority']) 
                          for cat, errs in self.categorized.items()]
        category_counts.sort(key=lambda x: (x[2], -x[1]))  # priority asc, count desc
        
        if category_counts:
            top_category = category_counts[0][0]
            top_errors = self.categorized[top_category]
            
            # Return most frequent error in top category
            message_counts = defaultdict(int)
            for error in top_errors:
                # Normalize message for counting
                normalized = re.sub(r'0x[0-9a-fA-F]+', '0x...', error['message'])
                normalized = re.sub(r'\d+', 'N', normalized)
                message_counts[normalized] += 1
            
            most_common = max(message_counts.items(), key=lambda x: x[1])
            
            return {
                'category': top_category,
                'description': ERROR_CATEGORIES[top_category]['description'],
                'priority': ERROR_CATEGORIES[top_category]['priority'],
                'message_pattern': most_common[0],
                'occurrences': most_common[1],
                'example': top_errors[0]['message'],
            }
        
        return None


def run_fnv():
    """Run FNV with logging enabled."""
    print("Running Fallout New Vegas with full logging...")
    print("=" * 60)
    
    # Clear old logs
    for log_file in LOGS_DIR.glob('*.log'):
        log_file.unlink()
    
    env = os.environ.copy()
    env.update({
        'MVK_CONFIG_LOG_LEVEL': '2',
        'MVK_CONFIG_DEBUG': '1',
        'DXVK_LOG_LEVEL': 'debug',
        'DXVK_LOG_PATH': str(LOGS_DIR),
        'VK_INSTANCE_LAYERS': 'VK_LAYER_KHRONOS_validation',
    })
    
    wine_prefix = Path.home() / '.wine-fnv-mo2'
    fnv_exe = wine_prefix / 'drive_c' / 'Games' / 'Steam' / 'steamapps' / 'common' / 'Fallout New Vegas' / 'FalloutNV.exe'
    
    if not fnv_exe.exists():
        print(f"ERROR: FNV not found at {fnv_exe}")
        print("Copy Fallout New Vegas to that location first.")
        return False
    
    try:
        result = subprocess.run(
            ['wine64', str(fnv_exe)],
            env=env,
            cwd=str(PROJECT_ROOT),
            capture_output=False,
            timeout=300,  # 5 minute timeout
        )
    except subprocess.TimeoutExpired:
        print("\nGame timed out (5 minutes)")
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    print("=" * 60)
    print("Run complete. Analyzing logs...")
    analyze_logs()
    return True


def analyze_logs():
    """Analyze existing log files."""
    if not LOGS_DIR.exists():
        print("No logs directory found. Run 'capture.py run' first.")
        return
    
    capture = ErrorCapture().parse_logs()
    summary = capture.get_summary()
    
    print("\n" + "=" * 60)
    print("ERROR ANALYSIS")
    print("=" * 60)
    
    print(f"\nTotal errors found: {summary['total_errors']}")
    
    if summary['by_category']:
        print("\nBy category:")
        sorted_cats = sorted(summary['by_category'].items(), 
                           key=lambda x: x[1]['priority'])
        for cat, info in sorted_cats:
            print(f"  [{info['priority']}] {cat}: {info['count']} ({info['description']})")
    
    next_fix = capture.get_next_to_fix()
    if next_fix:
        print("\n" + "-" * 60)
        print("NEXT ISSUE TO FIX:")
        print("-" * 60)
        print(f"Category: {next_fix['category']}")
        print(f"Description: {next_fix['description']}")
        print(f"Occurrences: {next_fix['occurrences']}")
        print(f"Example:\n  {next_fix['example'][:200]}")
    else:
        print("\nNo errors found! 🎉")
    
    # Save progress
    save_progress(summary)


def save_progress(summary):
    """Save progress to JSON file."""
    progress = []
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'total_errors': summary['total_errors'],
        'by_category': {k: v['count'] for k, v in summary['by_category'].items()},
    }
    progress.append(entry)
    
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def show_progress():
    """Show progress over time."""
    if not PROGRESS_FILE.exists():
        print("No progress data yet. Run 'capture.py run' first.")
        return
    
    with open(PROGRESS_FILE, 'r') as f:
        progress = json.load(f)
    
    print("\n" + "=" * 60)
    print("PROGRESS OVER TIME")
    print("=" * 60)
    
    for entry in progress[-10:]:  # Last 10 entries
        ts = entry['timestamp'][:19]
        total = entry['total_errors']
        cats = ', '.join(f"{k}:{v}" for k, v in entry['by_category'].items())
        print(f"{ts}  Total: {total:4d}  ({cats})")
    
    if len(progress) >= 2:
        first = progress[0]['total_errors']
        last = progress[-1]['total_errors']
        diff = first - last
        if diff > 0:
            print(f"\n✅ Fixed {diff} errors since start!")
        elif diff < 0:
            print(f"\n⚠️  {-diff} more errors than start (might be new features)")
        else:
            print("\n📊 Same error count as start")


def main():
    LOGS_DIR.mkdir(exist_ok=True)
    
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1]
    
    if command == 'run':
        run_fnv()
    elif command == 'analyze':
        analyze_logs()
    elif command == 'progress':
        show_progress()
    elif command == 'next':
        capture = ErrorCapture().parse_logs()
        next_fix = capture.get_next_to_fix()
        if next_fix:
            print(json.dumps(next_fix, indent=2))
        else:
            print("No errors to fix!")
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == '__main__':
    main()
