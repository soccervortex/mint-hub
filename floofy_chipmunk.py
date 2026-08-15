#!/usr/bin/python3
"""Legacy entry point — redirects to mint_hub.py."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mint_hub import *
