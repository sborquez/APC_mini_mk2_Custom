from __future__ import absolute_import, print_function, unicode_literals
try:
    from ableton.v3.control_surface.capabilities import CONTROLLER_ID_KEY, HIDDEN, NOTES_CC, PORTS_KEY, SCRIPT, SYNC, controller_id, inport, outport
except ImportError:
    from .ableton.v3.control_surface.capabilities import CONTROLLER_ID_KEY, HIDDEN, NOTES_CC, PORTS_KEY, SCRIPT, SYNC, controller_id, inport, outport
from .logger_config import get_logger
from .apc_mini_mk2 import APC_mini_mk2

# Initialize logger for this module
logger = get_logger('main')

def get_capabilities():
    capabilities = {CONTROLLER_ID_KEY: (controller_id(vendor_id=2536,
                          product_ids=[79],
                          model_name=["APC mini mk2"])),

     PORTS_KEY: [
                 inport(props=[NOTES_CC, SCRIPT]),
                 inport(props=[NOTES_CC]),
                 outport(props=[NOTES_CC, SCRIPT, SYNC, HIDDEN]),
                 outport(props=[NOTES_CC])]}
    logger.info(f"Controller capabilities: {capabilities}")
    return capabilities


def create_instance(c_instance):
    logger.info("================================================")
    logger.info("=========Creating APC mini mk2 instance=========")
    logger.info("================================================")
    instance = APC_mini_mk2(c_instance=c_instance)
    logger.info("================================================")
    logger.info("===APC mini mk2 instance created successfully===")
    logger.info("================================================")
    return instance
