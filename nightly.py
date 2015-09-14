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
import glob
import fnmatch
import jinja2
import shutil
import tarfile
import argparse
import subprocess

from distutils import dir_util
from datetime import datetime

# get directory *this* script is in
install_dir = os.path.dirname(os.path.realpath(__file__))
    
# Parse the command line options
# ==============================
parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

def unsigned_int(x):
    """
    Small helper function so argparse will understand unsigned integers.
    """
    x = int(x)
    if x < 1:
        raise argparse.ArgumentTypeError("This argument is an unsigned int type! Should be an integer greater than zero.")
    return x

def mkdir_p(path):
    """
    Make parent directories as needed and no error if existing. Works like `mkdir -p`.
    """
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def abs_existing_dir(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        print('Error! Directory does not exist: \n    '+path)
        sys.exit(1)
    return path

def abs_creation_dir(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        mkdir_p(path)
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

# Nightly options
parser.add_argument('-k', '--keep', default='10', type=unsigned_int,
        help='The location of LIVVkit.')
parser.add_argument('-o', '--nightly-output-dir', default=install_dir+os.sep+'current', type=abs_creation_dir,
        help='The directory to output the nightly test results summary and all data.')


# Some useful functions
# =====================
def recursive_glob(tree, pattern):
    matches = []
    for base, dirs, files in os.walk(tree):
        goodfiles = fnmatch.filter(files, pattern)
        matches.extend(os.path.join(base, f) for f in goodfiles)
    return matches

def filenames_sort_key(fn):
    fn_timestamp = os.path.basename(fn).split('_')[1]
    return datetime.strptime(fn_timestamp, '%Y-%m-%d')


def sorted_tarballs(look_dir, keep):
    test_tarballs =recursive_glob(look_dir, 'test_*.tar.gz')
    web_tarballs = recursive_glob(look_dir, 'www_*.tar.gz')
    
    web_dirs = []
    for wd in web_tarballs:
        head, tail = os.path.split(wd)
        web_dirs.append(os.path.join(head, tail.strip('.tar.gz')))


    test_tarballs = sorted(test_tarballs, key=filenames_sort_key, reverse=True)
    web_tarballs = sorted(web_tarballs, key=filenames_sort_key, reverse=True)
    web_dirs = sorted(web_dirs, key=filenames_sort_key, reverse=True)
   
    if len(test_tarballs) > keep:
        remove_files = test_tarballs[keep:]
        remove_files.extend(web_tarballs[keep:])
        for rf in remove_files:
            os.remove(rf)

        for rd in web_dirs[keep:]:
            shutil.rmtree(rd)

        del test_tarballs[keep:]
        del web_tarballs[keep:]
        del web_dirs[keep:]

    return test_tarballs, web_tarballs, web_dirs


# The main script function
# ========================
def main():
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    data_dir = abs_creation_dir(args.nightly_output_dir+os.sep+'data')


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
    test_dir = data_dir+os.sep+'test_'+timestamp+'_'+cism_hash
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
    out_dir = data_dir+os.sep+'www_'+timestamp+'_'+livv_hash
    livv_comment = 'Nightly regression test of CISM using commit '+cism_hash \
                    +', and LIVVkit commit '+livv_hash+'.'

    livv_command = ['./livv.py',
                        '-b', args.bench_dir+os.sep+'linux-gnu',
                        '-t', test_dir+os.sep+'linux-gnu',
                        '-o', out_dir,
                        '-c', livv_comment,
                        '--performance'
                    ]

    subprocess.check_call(livv_command,cwd=args.livv)

    # tar directories
    with tarfile.open(test_dir+".tar.gz","w:gz") as tar:
        tar.add(test_dir, arcname=os.path.basename(test_dir))
    
    with tarfile.open(out_dir+".tar.gz","w:gz") as tar:
        tar.add(out_dir, arcname=os.path.basename(out_dir))

    # remove build and reg_test directory
    shutil.rmtree(build_dir)
    shutil.rmtree(test_dir)


    # make/update website
    # -------------------
    test_tarballs, web_tarballs, web_dirs = sorted_tarballs(data_dir, args.keep)
    
    dir_util.copy_tree(abs_existing_dir(args.livv+'/web/imgs'), args.nightly_output_dir+os.sep+'imgs')
    dir_util.copy_tree(abs_existing_dir(args.livv+'/web/css'), args.nightly_output_dir+os.sep+'css')
    
    template_dir = abs_existing_dir(args.livv+'/web/templates')
    template_loader = jinja2.FileSystemLoader([template_dir, install_dir])
    template_env = jinja2.Environment(loader=template_loader)
    template_vars = {'index_dir' : '.',
                     'css_dir' : 'css',
                     'img_dir' : 'imgs'}

    template = template_env.get_template('index-template.html')
    template_output = template.render(template_vars)

    with open(args.nightly_output_dir+os.sep+'index.html', 'w') as index:
        index.write(template_output)


if __name__=='__main__':
    args = parser.parse_args()
    main()
