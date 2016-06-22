#!/usr/bin/env python

import logging
import logging.handlers
import argparse
import sys
import time  # this is only being used as part of the example
import os

import os, sys, inspect
this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
src_folder = os.path.realpath(os.path.abspath(os.path.join(this_folder,"../..", "src")))
if src_folder not in sys.path:
    sys.path.insert(0, src_folder)
import env

# logger should only be imported after initlogging has been called
logger = None

def initlogging(name='docklet'):
    # Deafults
    global logger

    homepath = env.getenv('FS_PREFIX')
    LOG_FILENAME = homepath + '/local/log/' + name + '.log'

    LOG_LEVEL = env.getenv('WEB_LOG_LEVEL')
    if LOG_LEVEL == "DEBUG":
        LOG_LEVEL = logging.DEBUG
    elif LOG_LEVEL == "INFO":
        LOG_LEVEL = logging.INFO
    elif LOG_LEVEL == "WARNING":
        LOG_LEVEL = logging.WARNING
    elif LOG_LEVEL == "ERROR":
        LOG_LEVEL = logging.ERROR
    elif LOG_LEVEL == "CRITICAL":
        LOG_LEVEL = logging.CRITIAL
    else:
        LOG_LEVEL = logging.DEBUG

    logger = logging.getLogger(name)
    # Configure logging to log to a file, making a new file at midnight and keeping the last 3 day's data
    # Give the logger a unique name (good practice)
    # Set the log level to LOG_LEVEL
    logger.setLevel(LOG_LEVEL)
    # Make a handler that writes to a file, making a new file at midnight and keeping 3 backups
    handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME,
            when="midnight", backupCount=0, encoding='utf-8')
    # Format each log message like this
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(module)s[%(lineno)d] %(message)s')
    # Attach the formatter to the handler
    handler.setFormatter(formatter)
    # Attach the handler to the logger
    logger.addHandler(handler)

    # Replace stdout with logging to file at INFO level
    sys.stdout = RedirectLogger(logger, logging.INFO)
    # Replace stderr with logging to file at ERROR level
    sys.stderr = RedirectLogger(logger, logging.ERROR)

    # Make a class we can use to capture stdout and sterr in the log
class RedirectLogger(object):
    def __init__(self, logger, level):
        """Needs a logger and a logger level."""
        self.logger = logger
        self.level = level

    def write(self, message):
        # Only log if there is a message (not just a new line)
        if message.rstrip() != "":
            self.logger.log(self.level, message.rstrip())

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()
