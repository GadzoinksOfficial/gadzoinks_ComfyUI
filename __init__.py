"""
@author: gadzoinksofficial
@title: Gadzoinks
@nickname: Gadzoinks
@description: Custom node for integrating with gadzoinks iPhone app
"""

import sys, os

sys.path.insert(0,os.path.dirname(os.path.realpath(__file__)))
from .gadzoinks_image_save import SaveImageGadzoinks
module_root_directory = os.path.dirname(os.path.realpath(__file__))
module_js_directory = os.path.join(module_root_directory, "js")


WEB_DIRECTORY = "./js"
NODE_CLASS_MAPPINGS = { 
    "Gadzoinks" : SaveImageGadzoinks,
                      }

__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
IP_VERSION = "2.12"

