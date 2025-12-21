import sys
import os
import threading
import time
import traceback
import inspect
import json
import datetime
import platform
import gc
import socket
import logging

def dump_system_diagnostics(label="sys_diag"):
    """Dump 50+ system diagnostic metrics."""
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pid = os.getpid()
        filename = f"logs/diag_{label}_{pid}_{ts}.txt"
        os.makedirs("logs", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"System Diagnostics at {ts}\n")
            f.write("="*80 + "\n")
            
            # 1. Basic Process Info
            f.write(f"1. PID: {os.getpid()}\n")
            f.write(f"2. PPID: {os.getppid() if hasattr(os, 'getppid') else 'N/A'}\n")
            f.write(f"3. CWD: {os.getcwd()}\n")
            f.write(f"4. Executable: {sys.executable}\n")
            f.write(f"5. Cmdline: {sys.argv}\n")
            
            # 2. Python Info
            f.write(f"6. Python Version: {sys.version}\n")
            f.write(f"7. Hexversion: {sys.hexversion}\n")
            f.write(f"8. API Version: {sys.api_version}\n")
            f.write(f"9. Version Info: {sys.version_info}\n")
            f.write(f"10. Platform: {sys.platform}\n")
            f.write(f"11. Prefix: {sys.prefix}\n")
            f.write(f"12. Base Prefix: {getattr(sys, 'base_prefix', 'N/A')}\n")
            f.write(f"13. Exec Prefix: {sys.exec_prefix}\n")
            f.write(f"14. Base Exec Prefix: {getattr(sys, 'base_exec_prefix', 'N/A')}\n")
            f.write(f"15. Implementation: {sys.implementation}\n")
            f.write(f"16. Byteorder: {sys.byteorder}\n")
            f.write(f"17. Default Encoding: {sys.getdefaultencoding()}\n")
            f.write(f"18. Filesystem Encoding: {sys.getfilesystemencoding()}\n")
            f.write(f"19. Recursion Limit: {sys.getrecursionlimit()}\n")
            f.write(f"20. Int Max Str Digits: {sys.get_int_max_str_digits() if hasattr(sys, 'get_int_max_str_digits') else 'N/A'}\n")
            f.write(f"21. Float Info: {sys.float_info}\n")
            f.write(f"22. Float Repr Style: {sys.float_repr_style}\n")
            f.write(f"23. Hash Randomization: {sys.flags.hash_randomization}\n")
            f.write(f"24. Switch Interval: {sys.getswitchinterval()}\n")
            f.write(f"25. Dont Write Bytecode: {sys.dont_write_bytecode}\n")
            
            # 3. Platform Info
            f.write(f"26. System: {platform.system()}\n")
            f.write(f"27. Node: {platform.node()}\n")
            f.write(f"28. Release: {platform.release()}\n")
            f.write(f"29. Version: {platform.version()}\n")
            f.write(f"30. Machine: {platform.machine()}\n")
            f.write(f"31. Processor: {platform.processor()}\n")
            f.write(f"32. Architecture: {platform.architecture()}\n")
            f.write(f"33. Python Build: {platform.python_build()}\n")
            f.write(f"34. Python Compiler: {platform.python_compiler()}\n")
            f.write(f"35. Uname: {platform.uname()}\n")
            
            # 4. Time Info
            f.write(f"36. Time (time): {time.get_clock_info('time')}\n")
            f.write(f"37. Time (monotonic): {time.get_clock_info('monotonic')}\n")
            f.write(f"38. Time (perf_counter): {time.get_clock_info('perf_counter')}\n")
            f.write(f"39. Time (process_time): {time.get_clock_info('process_time')}\n")
            
            # 5. Network/Socket Info
            f.write(f"40. Hostname: {socket.gethostname()}\n")
            f.write(f"41. Default Socket Timeout: {socket.getdefaulttimeout()}\n")
            try:
                f.write(f"42. FQDN: {socket.getfqdn()}\n")
            except:
                f.write("42. FQDN: <error>\n")
                
            # 6. Threading/GC
            f.write(f"43. Active Thread Count: {threading.active_count()}\n")
            f.write(f"44. Current Thread: {threading.current_thread().name} ({threading.get_ident()})\n")
            f.write(f"45. GC Enabled: {gc.isenabled()}\n")
            f.write(f"46. GC Threshold: {gc.get_threshold()}\n")
            f.write(f"47. GC Count: {gc.get_count()}\n")
            f.write(f"48. GC Stats: {gc.get_stats() if hasattr(gc, 'get_stats') else 'N/A'}\n")
            
            # 7. Environment
            f.write(f"49. Env Var Count: {len(os.environ)}\n")
            f.write(f"50. Path Entries: {len(sys.path)}\n")
            f.write(f"51. Loaded Modules: {len(sys.modules)}\n")
            
            # 8. Windows Specific
            if sys.platform == 'win32':
                try:
                    f.write(f"52. Win32 Ver: {sys.getwindowsversion()}\n")
                except:
                    pass
            
            f.write("-" * 40 + "\n")
            f.write("Environment Variables:\n")
            for k, v in os.environ.items():
                f.write(f"  {k}={v}\n")
                
            f.write("-" * 40 + "\n")
            f.write("Sys Path:\n")
            for p in sys.path:
                f.write(f"  {p}\n")

        return filename
    except Exception as e:
        return f"Error dumping diagnostics: {e}"

def log_call(func):
    """Decorator to log function entry, exit, and args."""
    def wrapper(*args, **kwargs):
        ts = time.time()
        pid = os.getpid()
        tid = threading.get_ident()
        name = func.__name__
        
        # Log Entry
        try:
            with open(f"logs/calls_{pid}.log", "a", encoding="utf-8") as f:
                f.write(f"[{ts:.6f}] [T{tid}] ENTER {name} args={len(args)} kwargs={len(kwargs)}\n")
        except: pass
        
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            # Log Exit
            try:
                with open(f"logs/calls_{pid}.log", "a", encoding="utf-8") as f:
                    f.write(f"[{time.time():.6f}] [T{tid}] EXIT {name} duration={duration:.6f}s\n")
            except: pass
            
            return result
        except Exception as e:
            duration = time.time() - start
            # Log Exception
            try:
                with open(f"logs/calls_{pid}.log", "a", encoding="utf-8") as f:
                    f.write(f"[{time.time():.6f}] [T{tid}] ERROR {name} duration={duration:.6f}s error={e}\n")
            except: pass
            raise
    return wrapper

def dump_stack_traces(label="stack_dump"):
    """Dump stack traces of all threads to a file."""
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pid = os.getpid()
        filename = f"logs/stack_{label}_{pid}_{ts}.txt"
        os.makedirs("logs", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Stack Dump at {ts}\n")
            f.write("="*80 + "\n")
            
            for thread_id, frame in sys._current_frames().items():
                f.write(f"\nThread ID: {thread_id}\n")
                traceback.print_stack(frame, file=f)
                f.write("-" * 40 + "\n")
                
                # Dump local variables in each frame (Extreme Mode)
                f.write("  Local Variables:\n")
                for key, value in frame.f_locals.items():
                    try:
                        val_str = str(value)[:200] # Truncate slightly to avoid infinite loops
                        f.write(f"    {key} = {val_str}\n")
                    except:
                        f.write(f"    {key} = <error printing value>\n")
                f.write("." * 40 + "\n")

        return filename
    except Exception as e:
        return f"Error dumping stack: {e}"

def dump_heap_stats(label="heap_stats"):
    """Dump basic heap statistics (simulated memory dump)."""
    try:
        import gc
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pid = os.getpid()
        filename = f"logs/heap_{label}_{pid}_{ts}.txt"
        os.makedirs("logs", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Heap Stats at {ts}\n")
            f.write(f"GC Counts: {gc.get_count()}\n")
            f.write(f"GC Threshold: {gc.get_threshold()}\n")
            f.write("="*80 + "\n")
            
            # Count objects by type
            type_counts = {}
            for obj in gc.get_objects():
                t = type(obj).__name__
                type_counts[t] = type_counts.get(t, 0) + 1
            
            for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                f.write(f"{t}: {count}\n")
                
        return filename
    except Exception as e:
        return f"Error dumping heap: {e}"

class ExtremeLogger(threading.Thread):
    """Background thread that logs furiously."""
    def __init__(self, interval=0.01):
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_event = threading.Event()
        self.logger = logging.getLogger("extreme_logger")
        
    def run(self):
        import logging
        counter = 0
        while not self.stop_event.is_set():
            counter += 1
            # Log a heartbeat
            ts = time.time()
            # We use print directly to stderr/file to bypass logging locks if needed, 
            # but here we'll use the logger to respect the setup.
            # However, to ensure volume, we'll write to a dedicated file too.
            try:
                with open(f"logs/extreme_stream_{os.getpid()}.log", "a") as f:
                    f.write(f"[{ts:.6f}] HEARTBEAT {counter} - CPU ACTIVE - MEMORY OK\n")
            except:
                pass
            
            if counter % 100 == 0:
                dump_stack_traces(f"heartbeat_{counter}")
                
            time.sleep(self.interval)

    def stop(self):
        self.stop_event.set()
