#!/usr/bin/env python
#
# Reads tests from the .test files on the command line (or the built-in set)
# and runs them, or writes a CTest script to run them.
#
# * @author  Ben Gardner        October 2009
# * @author  Guy Maurel         October 2015
# * @author  Matthew Woehlke    June 2018
#

import argparse
import os
import sys

import test_uncrustify as tu


# -----------------------------------------------------------------------------
def main(argv):
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Run uncrustify front-end tests')
    tu.add_frontend_tests_arguments(parser)
    args = tu.parse_args(parser)

    # Read tests
    tests = []
    print('Tests: {!s}'.format(args.tests))
    for group in args.tests:
        tests_file = os.path.join(tu.test_dir, '{}.test'.format(group))
        tests += tu.read_frontend_tests(tests_file, group)

    # Set up test selector
    if args.select:
        s = tu.Selector(args.select)
    else:
        s = None

    # Resolve absolute path of uncrustify executable
    exe = tu.config.uncrustify_exe
    if not os.path.isabs(exe):
        exe = os.path.join(os.getcwd(), exe)
        tu.config.uncrustify_exe = exe

    # Change working directory; because some tests include the name of the
    # configuration file, it is critical that we do NOT pass full paths for
    # these, and thus, that we run the tests from the tests 'config' directory
    os.chdir(os.path.join(tu.test_dir, 'config'))

    # Run tests
    counts = tu.run_tests(tests, args, s)
    tu.report(counts)

    if counts['failing'] > 0:
        sys.exit(2)
    if counts['mismatch'] > 0 or counts['unstable'] > 0:
        sys.exit(1)


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

if __name__ == '__main__':
    sys.exit(main(sys.argv))
