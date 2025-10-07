import logging
import os

def setup_logging():
    """
    Setup logging configuration for the APC mini mk2 custom script.
    Logs are written to the Desktop folder with timestamp-based filenames.
    """
    # Get the this file's folder + logs folder
    logs_folder_path = os.path.join(os.path.dirname(__file__), "logs")

    # Create log filename with timestamp
    log_filename = "apc_mini_mk2_custom.log"
    log_filepath = os.path.join(logs_folder_path, log_filename)

    # Create logger
    logger = logging.getLogger('apc_mini_mk2_custom')
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create file handler
    file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Create console handler for real-time debugging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Only show INFO and above in console

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Add formatter to handlers
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log initial setup
    logger.info(f"Logging initialized. Log file: {log_filepath}")
    logger.info("APC mini mk2 custom MIDI Remote Script starting...")

    return logger

def get_logger(name=None):
    """
    Get a logger instance for the given name.
    If no name is provided, returns the main logger.
    """
    if name is None:
        return logging.getLogger('apc_mini_mk2_custom')
    return logging.getLogger(f'apc_mini_mk2_custom.{name}')

# Initialize logging when this module is imported
main_logger = setup_logging()
