import logging
import sys
from pathlib import Path

def get_run_logger(run_id: str, log_file_path: Path, level_name: str = "INFO") -> logging.Logger:
    """
    Creates a private, non-propagating logger for a specific run.
    
    Args:
        run_id: The unique identifier for the run.
        log_file_path: The absolute path to the log file.
        level_name: The logging level (e.g., "DEBUG", "INFO").
        
    Returns:
        A configured logging.Logger instance that writes ONLY to the specified file
        and does not bubble up to the root logger.
    """
    # 1. Create a unique logger name. Using 'run.' prefix helps identify them,
    #    but the key is that we will detach it from the parent.
    logger_name = f"run.{run_id}"
    logger = logging.getLogger(logger_name)
    
    # 2. CRITICAL: Prevent logs from propagating to the root logger (and thus console/other files)
    logger.propagate = False
    
    # 3. Set the level explicitly. This overrides any global setting.
    #    If the user wants DEBUG, this logger will be DEBUG, even if root is INFO.
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)
    
    # 4. Clear existing handlers to prevent duplicate logging if get_run_logger is called twice
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
            
    # 5. Create the FileHandler
    #    Ensure the directory exists
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(str(log_file_path), mode='a', encoding='utf-8')
    file_handler.setLevel(level)
    
    # 6. Set a formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # 7. Add the handler
    logger.addHandler(file_handler)
    
    return logger

