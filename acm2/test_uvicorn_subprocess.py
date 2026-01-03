"""Test subprocess from within uvicorn context"""
import asyncio
import sys
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup():
    print(f'Platform: {sys.platform}')
    print(f'Python: {sys.version}')
    
    # Check event loop
    loop = asyncio.get_running_loop()
    print(f'Running loop type: {type(loop).__name__}')
    
    policy = asyncio.get_event_loop_policy()
    print(f'Event loop policy: {type(policy).__name__}')
    
    # Test subprocess
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-c', 'print("hello from subprocess")',
            stdout=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        print(f'Subprocess output: {out.decode().strip()}')
        print('SUBPROCESS WORKS IN UVICORN!')
    except NotImplementedError as e:
        print(f'NotImplementedError: {e}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9999)
