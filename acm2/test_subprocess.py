import asyncio
import sys

print(f'Platform: {sys.platform}')
print(f'Python: {sys.version}')
policy = asyncio.get_event_loop_policy()
print(f'Event loop policy: {type(policy).__name__}')

async def test():
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-c', 'print("hello")',
            stdout=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        print(f'Subprocess output: {out.decode().strip()}')
        print('Subprocess WORKS!')
    except NotImplementedError as e:
        print(f'NotImplementedError: {e}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

asyncio.run(test())
