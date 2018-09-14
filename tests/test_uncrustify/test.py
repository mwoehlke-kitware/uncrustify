# Class encapsulating a unit test.
#
# * @author  Ben Gardner        October 2009
# * @author  Guy Maurel         October 2015
# * @author  Matthew Woehlke    June 2018
#

import filecmp
import os
import subprocess
import sys

from .ansicolor import printc
from .config import (config, test_dir, FAIL_ATTRS,
                     MISMATCH_ATTRS, UNSTABLE_ATTRS)
from .failure import (ExecutionFailure, MissingFailure,
                      MismatchFailure, UnstableFailure)
from .manip import Manipulators

if os.name == 'nt':
    NULL_DEVICE = 'nul'
else:
    NULL_DEVICE = '/dev/null'


# =============================================================================
class Test(object):
    # -------------------------------------------------------------------------
    def __init__(self):
        self.test_result_dir = 'results'

        self.diff_text = 'MISMATCH'
        self.diff_attrs = MISMATCH_ATTRS
        self.diff_exception = MismatchFailure

    # -------------------------------------------------------------------------
    def _check_attr(self, name):
        if not hasattr(self, name) or getattr(self, name) is None:
            raise AttributeError(
                'Test is missing required attribute {!r}'.format(name))

    # -------------------------------------------------------------------------
    def _make_abs(self, name, base):
        path = getattr(self, name)
        if not os.path.isabs(path):
            setattr(self, name, os.path.join(test_dir, base, path))

    # -------------------------------------------------------------------------
    def _diff(self, expected, actual):
        sys.stdout.flush()
        cmd = [config.git_exe, 'diff', '--no-index', expected, actual]
        subprocess.call(cmd)

    # -------------------------------------------------------------------------
    def _compare(self, expected, actual, args):
        try:
            if not filecmp.cmp(expected, actual):
                printc('{}: '.format(self.diff_text),
                       self.test_name, **self.diff_attrs)
                if args.diff:
                    self._diff(expected, actual)
                raise self.diff_exception(expected, actual)
        except OSError as exc:
            printc('MISSING: ', self.test_name, **self.diff_attrs)
            raise MissingFailure(exc, expected)


# =============================================================================
class FrontEndTest(Test):
    # -------------------------------------------------------------------------
    def __init__(self, name, conf):
        super(FrontEndTest, self).__init__()

        self.test_name = name

        self.test_args = conf.get('args', [])
        self.test_config = conf.get('config')

        self._build(conf, 'out', 'stdout', True)
        self._build(conf, 'err', 'stderr', True)
        self._build(conf, 'gen', 'output', False)

    # -------------------------------------------------------------------------
    def _build(self, conf, prefix, name, implicit):
        empty = not (prefix in conf or implicit)
        conf = conf.get(prefix) or {}

        # Set path to expected
        _expected = prefix + '_expected'
        name_parts = self.test_name.split(':')

        if 'expected' in conf:
            setattr(self, _expected, conf['expected'])
            self._make_abs(_expected, os.path.join('expected', name_parts[0]))

        elif not empty:
            setattr(self, _expected, '{}-{}.txt'.format(name_parts[1], name))
            self._make_abs(_expected, os.path.join('expected', name_parts[0]))

            if not os.path.exists(getattr(self, _expected)):
                setattr(self, _expected, None)

        else:
            setattr(self, _expected, None)

        # Set base name of result; used later to build full path
        setattr(self, prefix + '_result', name if not empty else None)

        # Set manipulators
        manip = []
        ms = conf.get('manip')
        if ms is not None:
            if type(ms) is not list:
                ms = [ms]

            for m in ms:
                if type(m) is dict:
                    for mf, ma in m.items():
                        mf = getattr(Manipulators, mf)
                        manip.append([mf] + (ma or []))
                else:
                    manip.append([getattr(Manipulators, m)])

        setattr(self, prefix + '_manip', manip)

    # -------------------------------------------------------------------------
    def _paths(self, prefix, args):
        name_parts = self.test_name.split(':')

        expected = getattr(self, '{}_expected'.format(prefix))
        result_name = getattr(self, '{}_result'.format(prefix))

        if result_name is None:
            result = None

        else:
            result = os.path.join(
                args.result_dir, self.test_result_dir, name_parts[0],
                '{}-{}.txt'.format(name_parts[1], result_name))

            if not os.path.exists(os.path.dirname(result)):
                os.makedirs(os.path.dirname(result))

        return expected, result

    # -------------------------------------------------------------------------
    def _purge(self, path):
        if path is not None and os.path.exists(path):
            os.unlink(path)

    # -------------------------------------------------------------------------
    def _mangle(self, path, prefix):
        # Get manipulators
        manip = getattr(self, prefix + '_manip')

        if not len(manip):
            return

        # Rename original so we can write the mangled version in its place
        path_orig = path + '.orig'
        os.rename(path, path_orig)

        with open(path, 'wb') as out:
            with open(path_orig, 'rb') as f:
                # Iterate over lines in original
                for line in f:
                    line = line.decode('utf-8')

                    # Apply manipulators
                    for m in manip:
                        line = m[0](line, *m[1:])

                    # Write result
                    out.write(line.encode('utf-8'))

    # -------------------------------------------------------------------------
    def _compare(self, expected, actual, args):
        # Expected might be None if we expect "no output"
        if expected is None:
            # If we didn't produce an output (only applies to 'gen', not 'out'
            # or 'err'), then we have nothing to do
            if actual is None:
                return

            # If the actual output is empty, that's a pass
            if os.stat(actual).st_size == 0:
                return

            # If we got unexpected output, compare against the null device
            expected = NULL_DEVICE

        # Hand off to base implementation
        super(FrontEndTest, self)._compare(expected, actual, args)

    # -------------------------------------------------------------------------
    def run(self, args):
        # Get paths of expected outputs
        _expected_out, _result_out = self._paths('out', args)
        _expected_err, _result_err = self._paths('err', args)
        _expected_gen, _result_gen = self._paths('gen', args)

        # Ensure no stale results are present
        self._purge(_result_out)
        self._purge(_result_err)
        self._purge(_result_gen)

        # Show test information, if requested
        if args.verbose:
            print(self.test_name)
            print('       Arguments : {!r}'.format(self.test_args))
            print(' Expected stdout : {}'.format(_expected_out))
            print(' Expected stderr : {}'.format(_expected_err))
            print(' Expected Output : {}'.format(_expected_gen))
            print('   Result stdout : {}'.format(_result_out))
            print('   Result stderr : {}'.format(_result_err))
            print('   Result Output : {}'.format(_result_gen))

        # Open files to receive stdout, stderr
        stdout = open(_result_out, 'wb')
        stderr = open(_result_err, 'wb')

        # Build command
        cmd = [config.uncrustify_exe] + self.test_args
        if self.test_config is not None:
            cmd += ['-c', self.test_config]
        if _result_gen is not None:
            cmd += ['-o', _result_gen]

        if args.show_commands:
            printc('RUN: ', repr(cmd))

        # Execute uncrustify
        try:
            subprocess.check_call(cmd, stdout=stdout, stderr=stderr)
        except subprocess.CalledProcessError as exc:
            msg = '{}: Uncrustify error code {}'
            msg = msg.format(self.test_name, exc.returncode)
            printc('FAILED: ', msg, **FAIL_ATTRS)
            raise ExecutionFailure(exc)
        finally:
            del stdout
            del stderr

        # Apply manipulators to outputs
        self._mangle(_result_out, 'out')
        self._mangle(_result_err, 'err')
        self._mangle(_result_gen, 'gen')

        # Compare outputs
        self._compare(_expected_out, _result_out, args)
        self._compare(_expected_err, _result_err, args)
        self._compare(_expected_gen, _result_gen, args)


# =============================================================================
class SourceTest(Test):
    # -------------------------------------------------------------------------
    def build(self, test_input, test_lang, test_config):
        self.test_name = os.path.basename(test_input)
        self.test_lang = test_lang
        self.test_input = test_input
        self.test_config = test_config
        self.test_expected = test_input

    # -------------------------------------------------------------------------
    def _check(self):
        self._check_attr('test_name')
        self._check_attr('test_lang')
        self._check_attr('test_input')
        self._check_attr('test_config')
        self._check_attr('test_expected')

    # -------------------------------------------------------------------------
    def run(self, args):
        self._check()

        _expected = self.test_expected
        _result = os.path.join(args.result_dir, self.test_result_dir,
                               os.path.basename(os.path.dirname(_expected)),
                               os.path.basename(_expected))

        if args.verbose:
            print(self.test_name)
            print('  Language : {}'.format(self.test_lang))
            print('     Input : {}'.format(self.test_input))
            print('    Config : {}'.format(self.test_config))
            print('  Expected : {}'.format(_expected))
            print('    Result : {}'.format(_result))

        if not os.path.exists(os.path.dirname(_result)):
            os.makedirs(os.path.dirname(_result))

        cmd = [
            config.uncrustify_exe,
            '-q',
            '-l', self.test_lang,
            '-c', self.test_config,
            '-f', self.test_input,
            '-o', _result
        ]
        if args.debug:
            cmd += [
                '-LA',
                '-p', _result + '.unc'
            ]
            stderr = open(_result + '.log', 'wb')

        else:
            cmd += ['-L1,2']
            stderr = None

        if args.show_commands:
            printc('RUN: ', repr(cmd))

        try:
            subprocess.check_call(cmd, stderr=stderr)
        except subprocess.CalledProcessError as exc:
            msg = '{}: Uncrustify error code {}'
            msg = msg.format(self.test_name, exc.returncode)
            printc('FAILED: ', msg, **FAIL_ATTRS)
            raise ExecutionFailure(exc)
        finally:
            del stderr

        self._compare(_expected, _result, args)


# =============================================================================
class FormatTest(SourceTest):
    pass_config = ['test_config', 'test_rerun_config']
    pass_input = ['test_input', 'test_expected']
    pass_expected = ['test_expected', 'test_rerun_expected']

    # -------------------------------------------------------------------------
    def _build_pass(self, i):
        p = SourceTest()

        p.test_name = self.test_name
        p.test_lang = self.test_lang
        p.test_config = getattr(self, self.pass_config[i])
        p.test_input = getattr(self, self.pass_input[i])
        p.test_expected = getattr(self, self.pass_expected[i])
        if i == 1 and not os.path.exists(p.test_expected):
            p.test_expected = getattr(self, self.pass_expected[0])

        return p

    # -------------------------------------------------------------------------
    def _build_passes(self):
        self._check()
        self._check_attr('test_rerun_config')
        self._check_attr('test_rerun_expected')

        self._make_abs('test_input', 'input')
        self._make_abs('test_config', 'config')
        self._make_abs('test_expected', 'expected')
        self._make_abs('test_rerun_config', 'config')
        self._make_abs('test_rerun_expected', 'expected')

        self.test_passes = [
            self._build_pass(0),
            self._build_pass(1)]

        self.test_passes[1].test_name = self.test_name + ' (re-run)'
        self.test_passes[1].test_result_dir = 'results_2'
        self.test_passes[1].diff_text = 'UNSTABLE'
        self.test_passes[1].diff_attrs = UNSTABLE_ATTRS
        self.test_passes[1].diff_exception = UnstableFailure

    # -------------------------------------------------------------------------
    def build_from_declaration(self, decl, group):
        parts = decl.split()
        test_dir = os.path.dirname(parts[2])

        if len(parts) == 4:
            self.test_lang = parts[3]
        else:
            self.test_lang = test_dir

        if parts[0].endswith('!'):
            num = parts[0][:-1]
        else:
            num = parts[0]

        self.test_config = parts[1]
        self.test_input = parts[2]
        self.test_expected = os.path.join(
            test_dir, '{}-{}'.format(num, os.path.basename(parts[2])))

        def rerun_file(name):
            parts = name.split('.')
            return '.'.join(parts[:-1] + ['rerun'] + parts[-1:])

        if parts[0].endswith('!'):
            self.test_rerun_config = rerun_file(self.test_config)
            self.test_rerun_expected = rerun_file(self.test_expected)
        else:
            self.test_rerun_config = self.test_config
            self.test_rerun_expected = self.test_expected

        self.test_name = '{}:{}'.format(group, num)

        self._build_passes()

    # -------------------------------------------------------------------------
    def build_from_args(self, args):
        self.test_name = args.name
        self.test_lang = args.lang
        self.test_input = args.input
        self.test_config = args.config
        self.test_expected = args.expected
        self.test_rerun_config = args.rerun_config or args.config
        self.test_rerun_expected = args.rerun_expected or args.expected

        self._build_passes()

    # -------------------------------------------------------------------------
    def print_as_ctest(self, out_file=sys.stdout):
        self._check()

        def to_cmake_path(path):
            if type(path) is dict:
                return {k: to_cmake_path(v) for k, v in path.items()}
            return path.replace(os.sep, '/')

        runner = os.path.join(test_dir, 'run_test.py')

        out_file.write(
            ('add_test({test_name}\n' +
             '  "{python_exe}" -S "{test_runner}" "{test_name}"\n' +
             '    --executable     "{uncrustify_exe}"\n' +
             '    --lang           "{test_lang}"\n' +
             '    --input          "{test_input}"\n' +
             '    --config         "{test_config}"\n' +
             '    --expected       "{test_expected}"\n' +
             '    --rerun-config   "{test_rerun_config}"\n' +
             '    --rerun-expected "{test_rerun_expected}"\n' +
             '    -d --git         "{git_exe}"\n' +
             ')\n').format(
                 test_runner=to_cmake_path(runner),
                 python_exe=to_cmake_path(config.python_exe),
                 uncrustify_exe=to_cmake_path(config.uncrustify_exe),
                 git_exe=to_cmake_path(config.git_exe),
                 **to_cmake_path(self.__dict__)))
        out_file.write(
            ('set_tests_properties({}\n' +
             '  PROPERTIES LABELS "{}"\n)\n').format(
                 self.test_name, self.test_name.split(':')[0]))

    # -------------------------------------------------------------------------
    def run(self, args):
        for p in self.test_passes:
            p.run(args)
