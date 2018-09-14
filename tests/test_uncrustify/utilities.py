# Logic for listing and running tests.
#
# * @author  Ben Gardner        October 2009
# * @author  Guy Maurel         October 2015
# * @author  Matthew Woehlke    June 2018
#

import argparse
import os
import subprocess
import sys
import yaml

from .ansicolor import printc
from .config import (config, frontend_tests, parse_tests, format_tests,
                     FAIL_ATTRS, PASS_ATTRS, SKIP_ATTRS)
from .failure import Failure, MismatchFailure, UnstableFailure
from .test import FrontEndTest, FormatTest # TODO ParseTest


# -----------------------------------------------------------------------------
def _add_common_arguments(parser, debuggable=True,
                          single=False, selectable=True):

    parser.add_argument('-c', '--show-commands', action='store_true',
                        help='show commands')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show detailed test information')

    parser.add_argument('-d', '--diff', action='store_true',
                        help='show diff on failure')

    if debuggable:
        parser.add_argument('-g', '--debug', action='store_true',
                            help='generate debug files (.log, .unc)')

    if not single:
        parser.add_argument('-p', '--show-all', action='store_true',
                            help='show passed/skipped tests')

    if selectable and not single:
        parser.add_argument('-r', '--select', metavar='CASE(S)', type=str,
                            help='select tests to be executed')

    parser.add_argument('-e', '--executable', type=str, required=True,
                        metavar='PATH',
                        help='uncrustify executable to test')

    parser.add_argument('--git', type=str, default=config.git_exe,
                        metavar='PATH',
                        help='git executable to use to generate diffs')

    parser.add_argument('--result-dir', type=str, default=os.getcwd(),
                        metavar='DIR',
                        help='location to which results will be written')


# -----------------------------------------------------------------------------
def add_test_arguments(parser):
    _add_common_arguments(parser, single=True)

    parser.add_argument("name",                 type=str, metavar='NAME')
    parser.add_argument("--lang",               type=str, required=True)
    parser.add_argument("--input",              type=str, required=True)
    parser.add_argument("--config",             type=str, required=True)
    parser.add_argument("--expected",           type=str, required=True)
    parser.add_argument("--rerun-config",       type=str, metavar='INPUT')
    parser.add_argument("--rerun-expected",     type=str, metavar='CONFIG')


# -----------------------------------------------------------------------------
def add_source_tests_arguments(parser):
    _add_common_arguments(parser, selectable=False)


# -----------------------------------------------------------------------------
def add_frontend_tests_arguments(parser):
    _add_common_arguments(parser, debuggable=False)

    parser.add_argument('tests', metavar='TEST', type=str, nargs='*',
                        default=frontend_tests,
                        help='test(s) to run (default all)')


# -----------------------------------------------------------------------------
def add_parse_tests_arguments(parser):
    _add_common_arguments(parser, debuggable=False)

    parser.add_argument('tests', metavar='TEST', type=str, nargs='*',
                        default=parse_tests,
                        help='test(s) to run (default all)')


# -----------------------------------------------------------------------------
def add_format_tests_arguments(parser):
    _add_common_arguments(parser)

    parser.add_argument('tests', metavar='TEST', type=str, nargs='*',
                        default=format_tests,
                        help='test(s) to run (default all)')

    # Arguments for generating the CTest script; users should not use these
    # directly
    parser.add_argument("--write-ctest", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--cmake-config", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--python", type=str, help=argparse.SUPPRESS)


# -----------------------------------------------------------------------------
def parse_args(parser):
    args = parser.parse_args()

    if args.git is not None:
        config.git_exe = args.git

    config.uncrustify_exe = args.executable
    if not os.path.exists(config.uncrustify_exe):
        msg = 'Specified uncrustify executable {!r} does not exist'.format(
            config.uncrustify_exe)
        printc("FAILED: ", msg, **FAIL_ATTRS)
        sys.exit(-1)

    # Do a sanity check on the executable
    try:
        with open(os.devnull, 'w') as bitbucket:
            subprocess.check_call([config.uncrustify_exe, '--help'],
                                  stdout=bitbucket)
    except Exception as exc:
        msg = ('Specified uncrustify executable {!r} ' +
               'does not appear to be usable: {!s}').format(
            config.uncrustify_exe, exc)
        printc("FAILED: ", msg, **FAIL_ATTRS)
        sys.exit(-1)

    return args


# -----------------------------------------------------------------------------
def run_tests(tests, args, selector=None):
    pass_count = 0
    fail_count = 0
    mismatch_count = 0
    unstable_count = 0

    for test in tests:
        if selector is not None and not selector.test(test.test_name):
            if args.show_all:
                printc("SKIPPED: ", test.test_name, **SKIP_ATTRS)
            continue

        try:
            test.run(args)
            if args.show_all:
                printc('PASSED: ', test.test_name, **PASS_ATTRS)
            pass_count += 1
        except UnstableFailure:
            unstable_count += 1
        except MismatchFailure:
            mismatch_count += 1
        except Failure:
            fail_count += 1

    return {
        'passing': pass_count,
        'failing': fail_count,
        'mismatch': mismatch_count,
        'unstable': unstable_count
    }


# -----------------------------------------------------------------------------
def report(counts):
    total = sum(counts.values())
    print('{passing} / {total} tests passed'.format(total=total, **counts))
    if counts['failing'] > 0:
        printc('{failing} tests failed to execute'.format(**counts),
               **FAIL_ATTRS)
    if counts['mismatch'] > 0:
        printc(
            '{mismatch} tests did not match the expected output'.format(
                **counts),
            **FAIL_ATTRS)
    if counts['unstable'] > 0:
        printc('{unstable} tests were unstable'.format(**counts),
               **FAIL_ATTRS)


# -----------------------------------------------------------------------------
def read_frontend_tests(filename, group):
    tests = []

    print("Processing " + filename)
    with open(filename, 'rt') as f:
        for block in yaml.safe_load_all(f):
            base = block.get('.', {})
            for num, detail in block.items():
                if num == '.':
                    continue

                conf = dict(base)
                conf.update(detail)

                name = '{}:{}'.format(group, num)
                test = FrontEndTest(name, conf)
                tests.append(test)

    return tests

# -----------------------------------------------------------------------------
def read_parse_tests(filename, group):
    pass # TODO

# -----------------------------------------------------------------------------
def read_format_tests(filename, group):
    tests = []

    print("Processing " + filename)
    with open(filename, 'rt') as f:
        for line in f:
            line = line.strip()
            if not len(line):
                continue
            if line.startswith('#'):
                continue

            test = FormatTest()
            test.build_from_declaration(line, group)
            tests.append(test)

    return tests


# -----------------------------------------------------------------------------
def fixup_ctest_path(path, config):
    if config is None:
        return path

    dirname, basename = os.path.split(path)
    if os.path.basename(dirname).lower() == config.lower():
        dirname, junk = os.path.split(dirname)
        return os.path.join(dirname, '${CTEST_CONFIGURATION_TYPE}', basename)

    return path
