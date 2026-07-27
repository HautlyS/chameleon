#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bridge.orchestrator import BotOrchestrator
from bridge.config import BridgeConfig


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    ap = argparse.ArgumentParser(description="Chameleon Bot Bridge — unified bot interface")
    ap.add_argument("--rss", action="store_true", help="Start RSS scanner daemon")
    ap.add_argument("--scan", action="store_true", help="Run one scan cycle and exit")
    ap.add_argument("--query", "-q", default="", help="Search query for scan")
    ap.add_argument("--platforms", "-p", default="", help="Platforms for scan")

    args = ap.parse_args()

    orch = BotOrchestrator()

    if args.scan:
        jobs = orch.scan_now(query=args.query, platforms=args.platforms)
        print(f"Found {len(jobs)} jobs")
        return

    if args.rss:
        print("Starting RSS scanner...")
        orch.start_rss()
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping RSS scanner...")
            orch.stop_rss()
        return

    ap.print_help()


if __name__ == "__main__":
    main()
