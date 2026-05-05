#!/usr/bin/env bash
# Live MI300X dashboard — runs in a side terminal during the demo.
# Refreshes once per second; -d highlights changes.
exec watch -n 1 -d rocm-smi --showuse --showmemuse --showtemp --showpower
