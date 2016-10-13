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
import json
import numpy
import jinja2
import shutil
import fnmatch
import tarfile
import datetime
import argparse
import subprocess

from distutils import dir_util

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
    if not os.path.isdir(os.path.join(path,'.git')):
        print('Error! CISM directory is not a git repository: \n    '+path)
        print('Cannot determine current CISM commit hash.')
        sys.exit(1)
    if not os.path.isdir(os.path.join(path,'cism_driver')):
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
    if not os.path.isdir(os.path.join(path,'.git')):
        print('Error! LIVVkit directory is not a git repository: \n    '+path)
        print('Cannot determine current LIVVkit commit hash.')
        sys.exit(1)
    if not os.path.isfile(os.path.join(path,'livv')):
        print('Error! No livv.py script found in LIVVkit directory: \n    '+path)
        sys.exit(1)
    return path

parser.add_argument('-l', '--livv', default='./LIVVkit', type=livv_type,
        help='The location of LIVVkit.')
parser.add_argument('--livv-branch', default='develop',
        help='The LIVVkit branch to checkout.')
parser.add_argument('--bench-dir', default='./reg_bench', type=abs_existing_dir,
        help='The benchmark directory for LIVVkit.')
parser.add_argument('--bench-hash', default='unknown',
        help='The commit hash of CISM used to generate the benchmark data.')

# Nightly options
parser.add_argument('--keep-nights', default='4', type=unsigned_int,
        help='Number of previous nightly runs to keep.')
parser.add_argument('--keep-weeks', default='8', type=unsigned_int,
        help='Number of sunday runs to keep (will be kept in addition to the nightly runs).')
parser.add_argument('-o', '--nightly-output-dir', default=os.path.join(install_dir,'current'), type=abs_creation_dir,
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
    fn_time_stamp = os.path.basename(fn).split('_')[1]
    return datetime.datetime.strptime(fn_time_stamp, '%Y-%m-%d')

def timestamp_sort_key(ts):
    return datetime.datetime.strptime(ts, '%Y-%m-%d')

def sorted_tarballs(look_dir):
    test_tarballs =recursive_glob(look_dir, 'test_*.tar.gz')
    bench_tarballs =recursive_glob(look_dir, 'bench_*.tar.gz')
    web_tarballs = recursive_glob(look_dir, 'www_*.tar.gz')
    
    web_dirs = []
    for wd in web_tarballs:
        head, tail = os.path.split(wd)
        web_dirs.append(os.path.join(head, tail.strip('.tar.gz')))

    test_tarballs = sorted(test_tarballs, key=filenames_sort_key, reverse=True)
    bench_tarballs = sorted(bench_tarballs, key=filenames_sort_key, reverse=True)
    web_tarballs = sorted(web_tarballs, key=filenames_sort_key, reverse=True)
    web_dirs = sorted(web_dirs, key=filenames_sort_key, reverse=True)

    return test_tarballs, bench_tarballs, web_tarballs, web_dirs


def choose_tarballs(look_dir, args):
    test_tarballs, bench_tarballs, web_tarballs, web_dirs = sorted_tarballs(look_dir)
   
    details = {}
    for idx, wd in enumerate(web_dirs):
        wd_time_stamp = os.path.basename(wd).split('_')[1]
        matching_test = os.path.basename( next((x for x in test_tarballs if wd_time_stamp in x),'MISSING') )
        matching_bench = os.path.basename( next((x for x in bench_tarballs if wd_time_stamp in x),'MISSING') )
        details[wd_time_stamp] = [os.path.basename(wd), os.path.basename(web_tarballs[idx]), matching_test, matching_bench]

    nights_min_time = args.start_time-datetime.timedelta(days=args.keep_nights)
    weeks_min_time = args.start_time-datetime.timedelta(days=args.keep_weeks*7)
    
    nights_details = {key:val for (key,val) in details.iteritems() if datetime.datetime.strptime(key, '%Y-%m-%d') >= nights_min_time }
    weeks_details = {key:val for (key,val) in details.iteritems() if (datetime.datetime.strptime(key, '%Y-%m-%d') >= weeks_min_time) and
                                                                     (datetime.datetime.strptime(key, '%Y-%m-%d').weekday() == 6) }
    
    nights_delete = {key:val for (key,val) in details.iteritems() if (datetime.datetime.strptime(key, '%Y-%m-%d') < nights_min_time) and
                                                                     (datetime.datetime.strptime(key, '%Y-%m-%d').weekday() != 6) }
    nights_delete.update( {key:val for (key,val) in details.iteritems() if datetime.datetime.strptime(key, '%Y-%m-%d') < weeks_min_time } )
    
    
    for key, val in nights_delete.iteritems():
        shutil.rmtree(os.path.join(look_dir, val[0]))
        for f in val[1:]:
            os.remove(os.path.join(look_dir, f))

    return nights_details, weeks_details




# The main script function
# ========================
def main():
    args.start_time = datetime.datetime.now()
    time_stamp = args.start_time.strftime('%Y-%m-%d')
    
    data_dir = abs_creation_dir(os.path.join(args.nightly_output_dir,'data'))


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
    build_dir = os.path.join(install_dir, 'cism_build')
    test_dir = os.path.join(data_dir, 'test_'+time_stamp+'_'+cism_hash)
    bats_command = ['source deactivate;',
                    'source activate BATS;',
                    './build_and_test.py', 
                        '-b', build_dir, 
                        '-o', test_dir,
                    ]
    
    if args.timing:
        bats_command.extend(['--timing', '--sleep', '360'])

    subprocess.check_call(' '.join(bats_command), cwd=os.path.join(args.cism,'tests','regression'), 
            shell=True, executable='/bin/bash')


    # run LIVV
    print('\nRunning LIVVkit:')
    print(  '================')
    out_dir = os.path.join(data_dir,'www_'+time_stamp+'_'+livv_hash)
    livv_comment = 'Nightly regression test of CISM using commit '+cism_hash \
                    +', and LIVVkit commit '+livv_hash+'.'

    livv_command = ['source deactivate;',
                    'source activate LIVVkit;',
                    './livv',
                        '-v', os.path.join(test_dir, 'linux-gnu', 'CISM-glissade'), args.bench_dir, 
                        '-o', out_dir
                    ]
                    #    '-c', livv_comment,

    subprocess.check_call(' '.join(livv_command), cwd=args.livv, 
            shell=True, executable='/bin/bash')

    # tar directories
    print('\nCleaning up the data:')
    print(  '=====================')
    
    with tarfile.open(test_dir+".tar.gz","w:gz", dereference=True) as tar:
        tar.add(test_dir, arcname=os.path.basename(test_dir))
    
    bench_name = os.path.join(data_dir,'bench_'+time_stamp+'_'+args.bench_hash)
    with tarfile.open(bench_name+".tar.gz","w:gz", dereference=True) as tar:
        tar.add(args.bench_dir, arcname=os.path.basename(bench_name))
    
    with tarfile.open(out_dir+".tar.gz","w:gz", dereference=True) as tar:
        tar.add(out_dir, arcname=os.path.basename(out_dir))

    # remove build and reg_test directory
    shutil.rmtree(build_dir)
    shutil.rmtree(test_dir)


    # make/update website
    # -------------------
    print('\nMaking the website:')
    print(  '===================')
    nights_details, weeks_details = choose_tarballs(data_dir, args)


    nights_date_list = sorted(nights_details.keys(), key=timestamp_sort_key, reverse=True) 
    nights_livv_hash_list = []
    nights_test_hash_list = []
    nights_bench_hash_list = []
    nights_b4b = {}
    for ndl in nights_date_list:
        nights_livv_hash_list.append(nights_details[ndl][1].split('_')[2].strip('.tar.gz'))
        nights_test_hash_list.append(nights_details[ndl][2].split('_')[2].strip('.tar.gz'))
        nights_bench_hash_list.append(nights_details[ndl][3].split('_')[2].strip('.tar.gz'))
    
        # get data from Previous LIVVkit runs:
        night_data = {}
        with open(os.path.join(data_dir, nights_details[ndl][0], 'index.json')) as nd:
            night_data = json.load(nd)
        
        # The b4b-ness for all tests. 
        b4b_details = numpy.array([0, 0])
        for element in night_data['Data']['Elements']:
            if element['Title'] == 'Verification':
                for test in element['Data'].values():
                    for scale in test.values():
                        b4b_details += numpy.array(scale['Bit for Bit'])

        nights_b4b[ndl] = (str(b4b_details[0]), str(b4b_details[1]))

    weeks_date_list = sorted(weeks_details.keys(), key=timestamp_sort_key, reverse=True) 
    weeks_livv_hash_list = []
    weeks_test_hash_list = []
    weeks_bench_hash_list = []
    weeks_b4b = {}
    for wdl in weeks_date_list:
        weeks_livv_hash_list.append(weeks_details[wdl][1].split('_')[2].strip('.tar.gz'))
        weeks_test_hash_list.append(weeks_details[wdl][2].split('_')[2].strip('.tar.gz'))
        weeks_bench_hash_list.append(weeks_details[wdl][3].split('_')[2].strip('.tar.gz'))
    
        # get data from Previous LIVVkit runs:
        weeks_data = {}
        with open(os.path.join(data_dir, weeks_details[ndl][0], 'index.json')) as wd:
            weeks_data = json.load(wd)
        
        # The b4b-ness for all tests. 
        b4b_details = numpy.array([0, 0])
        for element in weeks_data['Data']['Elements']:
            if element['Title'] == 'Verification':
                for test in element['Data'].values():
                    for scale in test.values():
                        b4b_details += numpy.array(scale['Bit for Bit'])

        weeks_b4b[ndl] = (str(b4b_details[0]), str(b4b_details[1]))


    # start generating website
    dir_util.copy_tree(abs_existing_dir(os.path.join('web','imgs')), 
            os.path.join(args.nightly_output_dir,'imgs'))
    dir_util.copy_tree(abs_existing_dir(os.path.join('web','css')), 
            os.path.join(args.nightly_output_dir,'css'))
   
    template_dir = abs_existing_dir(os.path.join('web','templates'))
    template_loader = jinja2.FileSystemLoader([template_dir, install_dir])
    template_env = jinja2.Environment(loader=template_loader)
    template_vars = {'index_dir' : '.',
                     'css_dir' : 'css',
                     'img_dir' : 'imgs',
                     'nights_date_list' : nights_date_list,
                     'nights_details' : nights_details,
                     'nights_b4b' : nights_b4b,
                     'nights_test_hash_list' : nights_test_hash_list, 
                     'nights_bench_hash_list' : nights_bench_hash_list, 
                     'nights_livv_hash_list' : nights_livv_hash_list, 
                     'weeks_date_list' : weeks_date_list,
                     'weeks_details' : weeks_details,
                     'weeks_b4b' : weeks_b4b,
                     'weeks_test_hash_list' : weeks_test_hash_list, 
                     'weeks_bench_hash_list' : weeks_bench_hash_list, 
                     'weeks_livv_hash_list' : weeks_livv_hash_list, 
                     }

    template = template_env.get_template('index-template.html')
    template_output = template.render(template_vars)

    with open(os.path.join(args.nightly_output_dir,'index.html'), 'w') as index:
        index.write(template_output)

    print('\nFinished!\n')


if __name__=='__main__':
    args = parser.parse_args()
    main()
