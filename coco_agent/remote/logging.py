import json
import logging
import sys
import threading

import coco_agent
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler
from google.oauth2.service_account import Credentials

DEFAULT_LOG_FILE_NAME = "coco-agent"
DEFAULT_CLOUD_LOGGING_HANDLER_NAME = "coco-agent"
LOG_FORMAT = (
    "%(asctime)s.%(msecs)03d %(filename)s:%(lineno)d %(levelname)s: %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

# pre-python 3.8 workaround for catching in-thread unhandled exceptions - 3.8 has threading.excepthook()
def install_thread_excepthook():
    """
        Workaround for sys.excepthook thread bug
        From
    http://spyced.blogspot.com/2007/06/workaround-for-sysexcepthook-bug.html

    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
        Call once from __main__ before creating any threads.
        If using psyco, call psyco.cannotcompile(threading.Thread.run)
        since this replaces a new-style class method.
    """
    init_old = threading.Thread.__init__

    def init(self, *args, **kwargs):
        init_old(self, *args, **kwargs)
        run_old = self.run

        def run_with_except_hook(*args, **kw):
            try:
                run_old(*args, **kw)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init


def set_up_cloud_logging(
    credentials_file_path,
    module,
    cloud_logging_handler_name=DEFAULT_CLOUD_LOGGING_HANDLER_NAME,
):
    with open(credentials_file_path) as f:
        sa_info_creds = json.load(f)

    credentials = Credentials.from_service_account_info(sa_info_creds)
    client = google.cloud.logging.Client(credentials=credentials)

    handler = CloudLoggingHandler(client, name=cloud_logging_handler_name)
    logger = logging.getLogger(module)
    logger.addHandler(handler)


def apply_log_config(
    log_level_str=logging.INFO,
    log_to_file=True,
    log_file_name=DEFAULT_LOG_FILE_NAME,
    log_to_cloud=False,
    credentials_file_path=None,
    module=coco_agent.__name__,
):
    log_level_str = log_level_str.strip().upper()

    if not hasattr(logging, log_level_str):
        raise ValueError(f"Unknown log level: {log_level_str}")

    if log_to_cloud and not credentials_file_path:
        raise ValueError("Credentials file path required for logging to cloud")

    log_level = getattr(logging, log_level_str)
    log_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    logger = logging.getLogger(module)
    logger.setLevel(log_level)

    if log_to_file:
        log_path = "."
        file_name = log_file_name
        file_handler = logging.FileHandler(f"{log_path}/{file_name}.log")
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)

    if log_to_cloud:
        set_up_cloud_logging(credentials_file_path, module)
