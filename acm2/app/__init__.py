"""ACM2 - API Cost Multiplier 2.0"""
import sys

# Windows requires ProactorEventLoop for subprocess support (used by FPF adapter)
# This must be set before any asyncio code runs
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
