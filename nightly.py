#!/usr/bin/env python

"""
This script is designed to: 
    1. Execute CISM's BATS
    1. Analyze the BATS output with LIVVkit
    3. Collate the new LIVVkit analysis with previous analyses
    4. Generate a webpage for all current analyses.

When combined with CRON, this will allow for nightly testing and analysis of
CISM with LIVVkit.
"""

import argparse
import subprocess


# setup our input argument parser
parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-c', '--cism', default='./cism',
        help='The location of CISM.')
parser.add_argument('-l', '--livv', default='./livv',
        help='The location of LIVVkit.')


args = parser.parse_args()

def main():
    livv_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=args.livv).strip()
    cism_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=args.cism).strip()
    
    print("LIVVkit commit hash: "+livv_hash)
    print("CISM commit hash:    "+cism_hash)


if __name__=='__main__':
    args = parser.parse_args()
    main()
