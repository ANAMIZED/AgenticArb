#!/usr/bin/env python3
"""Thin wrapper so `python scripts/verify_system.py` works from repo root."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agenticarb.cli import cmd_verify
import argparse
cmd_verify(argparse.Namespace())
