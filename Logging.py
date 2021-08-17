"""Contains functions needed for logging"""
import os
import sys
import logging


def logging_formatter():
    """Enables console and log file logging; see test script for comments on functionality"""
    current_directory = os.getcwd()
    script_filename = os.path.basename(sys.argv[0])
    log_filename = os.path.splitext(script_filename)[0]
    log_file = os.path.join(current_directory, f"{log_filename}.log")
    if not os.path.exists(log_file):
        with open(log_file, "w"):
            pass
    message_formatting = "%(asctime)s - %(levelname)s - %(message)s"
    date_formatting = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=message_formatting, datefmt=date_formatting)
    logging_output = logging.getLogger(f"{log_filename}")
    logging_output.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logging_output.addHandler(console_handler)
    logging.basicConfig(format=message_formatting, datefmt=date_formatting, filename=log_file, filemode="w", level=logging.INFO)
    return logging_output


# Logging
def insert(name, level):
    """Use this wrapper to insert a message before and after the function for logging purposes
    1. name = message to add
    2, level = the number of times to insert triple dashes for formatting neatness"""
    if type(name) == str:
        def logging_decorator(function):
            def logging_wrapper(*exception):
                logger.info("---" * level + f"{name} Start")
                function(*exception)
                logger.info("---" * level + f"{name} Complete")
            return logging_wrapper
        return logging_decorator


logger = logging_formatter()
