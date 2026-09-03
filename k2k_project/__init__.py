# k2k_project/__init__.py
"""
Initialize PyMySQL as MySQLdb for seamless MySQL integration across OS environments.
"""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct script/WSGI execution
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
