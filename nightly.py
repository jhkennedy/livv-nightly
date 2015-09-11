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
import shutil
import tarfile
import argparse
import subprocess

from datetime import datetime

# Parse the command line options
# ==============================
parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

def abs_existing_dir(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        print('Error! Directory does not exist: \n    '+path)
        sys.exit(1)
    return path

# CISM options
def cism_type(path):
    path = abs_existing_dir(path)
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
parser.add_argument('--timing', action='store_true',
        help='Run tests 10x to get timing information.')

# LIVV options
def livv_type(path):
    path = abs_existing_dir(path)
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
parser.add_argument('--bench-dir', default='./reg_bench', type=abs_existing_dir,
        help='The benchmark directory for LIVVkit.')


# The main script function
# ========================
def main():

    # get directory *this* script is in
    install_dir = os.path.dirname(os.path.realpath(__file__))
    
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    # get the latest version of CISM
    print('\nUpdating CISM:')
    print(  '==============')
    subprocess.check_call(['git', 'checkout', args.cism_branch], cwd=args.cism)
    subprocess.check_call(['git', 'pull', '--ff-only'], cwd=args.cism)
    
    cism_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=args.cism).strip()
    print("CISM commit hash:    "+cism_hash)


    # get the latest version of LIVVkit
    print('\nUpdating LIVVkit:')
    print(  '=================')
    subprocess.check_call(['git', 'checkout', args.livv_branch], cwd=args.livv)
    subprocess.check_call(['git', 'pull', '--ff-only'], cwd=args.livv)
    
    livv_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=args.livv).strip()
    print("LIVVkit commit hash: "+livv_hash)


    # Run BATS
    print('\nRunning BATS:')
    print(  '=============')
    build_dir = install_dir+os.sep+'cism_build'
    test_dir = install_dir+os.sep+'test_'+timestamp+'_'+cism_hash
    bats_command = ['./build_and_test.py', 
                        '-b', build_dir, 
                        '-o', test_dir,
                    ]
    
    if args.timing:
        bats_command.extend(['--timing', '--sleep', '360'])

    subprocess.check_call(bats_command,cwd=args.cism+os.sep+'tests'+os.sep+'regression')


    # run LIVV
    print('\nRunning LIVVkit:')
    print(  '================')
    out_dir = install_dir+os.sep+'www_'+timestamp+'_'+livv_hash
    livv_comment = 'Nightly regression test of CISM on '+timestamp \
                    +', using CISM commit '+cism_hash \
                    +', and LIVVkit commit '+livv_hash+'.'

    livv_command = ['./livv.py',
                        '-b', args.bench_dir+os.sep+'linux-gnu',
                        '-t', test_dir+os.sep+'linux-gnu',
                        '-o', out_dir,
                        '-c', livv_comment,
                        '--performance'
                    ]

    subprocess.check_call(livv_command,cwd=args.livv)

    # tar reg_test directory
    with tarfile.open(test_dir+".tar.gz","w:gz") as tar:
        tar.add(test_dir, arcname=os.path.basename(test_dir))

    # remove build and reg_test directory
    shutil.rmtree(build_dir)
    shutil.rmtree(test_dir)

    # make/update website

if __name__=='__main__':
    args = parser.parse_args()
    main()
