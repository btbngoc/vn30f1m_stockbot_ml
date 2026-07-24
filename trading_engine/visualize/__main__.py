import argparse
import sys
from .chart import main as chart_main

def main():
    parser = argparse.ArgumentParser(description="Run the backtest visualizer.")
    parser.add_argument('args', nargs=argparse.REMAINDER, help='Arguments for the visualizer')
    parsed = parser.parse_args()
    # Forward remaining args to chart.main()
    sys.argv = [sys.argv[0]] + parsed.args
    chart_main()

if __name__ == "__main__":
    main()
