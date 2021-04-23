#!/usr/bin/env python3
import sys
import src.chaintool
if "dev" in src.chaintool.__version__:
    print("current version is a \"dev\" version")
    sys.exit(1)
sys.exit(0)
