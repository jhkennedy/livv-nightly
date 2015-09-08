#!/usr/bin/env python

"""
This script is designed to: 
    1. Execute CISM's BATS
    1. Analyze the BATS output with LIVVkit
    3. Collate the new LIVVkit analysis with previous analyses
    4. Generate a webpage for all current analyses.

When combined with CRON, this will allow for nightly testing and analysis of
CISM with LIVVkit.

@authors: jhkennedy
"""

import os
import sys
import argparse
import subprocess

# Parse the command line options
# ------------------------------
parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

def normal_existing_dir(path):
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        print('Error! Directory does not exist: \n    '+path)
        sys.exit(1)
    return path

# CISM options
def cism_type(path):
    path = normal_existing_dir(path)
    if not os.path.isdir(path+os.sep+'.git'):
        print('Error! CISM directory is not a git repository: \n    '+path)
        print('Cannot determine current CISM commit hash.')
        sys.exit(1)
    if not os.path.isdir(path+os.sep+'cism_driver'):
        print('Error! CISM directory does not contain a cism_driver subdirectory: \n    '+path)
        print('Cannot build CISM.')
        sys.exit(1)
    return path

parser.add_argument('-c', '--cism', default='./cism', type=cism_type,
        help='The location of CISM.')
parser.add_argument('--cism-branch', default='develop',
        help='The CISM branch to checkout.')

# LIVV options
def livv_type(path):
    path = normal_existing_dir(path)
    if not os.path.isdir(path+os.sep+'.git'):
        print('Error! LIVVkit directory is not a git repository: \n    '+path)
        print('Cannot determine current LIVVkit commit hash.')
        sys.exit(1)
    if not (os.path.isfile(path+os.sep+'livv.py')):
        print('Error! No livv.py script found in LIVVkit directory: \n    '+path)
        sys.exit(1)
    return path

parser.add_argument('-l', '--livv', default='./livv', type=livv_type,
        help='The location of LIVVkit.')
parser.add_argument('--livv-branch', default='develop',
        help='The LIVVkit branch to checkout.')


# The main script function
# ------------------------
def main():
    
    # get the latest version of CISM
    print('\nUpdating CISM:')
    print(  '--------------')
    subprocess.check_call(['git', 'checkout', args.cism_branch], cwd=args.cism)
    subprocess.check_call(['git', 'pull', '--ff-only'], cwd=args.cism)
    
    cism_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=args.cism).strip()
    print("CISM commit hash:    "+cism_hash)


    # get the latest version of LIVVkit
    print('\nUpdating LIVVkit:')
    print(  '-----------------')
    subprocess.check_call(['git', 'checkout', args.livv_branch], cwd=args.livv)
    subprocess.check_call(['git', 'pull', '--ff-only'], cwd=args.livv)
    
    livv_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=args.livv).strip()
    print("LIVVkit commit hash: "+livv_hash)


    # Run BATS
    print('\nRunning BATS:')
    print(  '-------------')
    subprocess.check_call(['./build_and_test.py','-h'],cwd=args.cism+os.sep+'tests'+os.sep+'regression')



if __name__=='__main__':
    args = parser.parse_args()
    main()
