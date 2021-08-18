# Copyright (C) 2007, 2009, 2010, 2016 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Tests for bencode structured encoding"""

import copy
import sys

from unittest import TestCase, TestSuite


def get_named_object(module_name, member_name=None):
    """Get the Python object named by a given module and member name.

    This is usually much more convenient than dealing with ``__import__``
    directly::

        >>> doc = get_named_object('pyutils', 'get_named_object.__doc__')
        >>> doc.splitlines()[0]
        'Get the Python object named by a given module and member name.'

    :param module_name: a module name, as would be found in sys.modules if
        the module is already imported.  It may contain dots.  e.g. 'sys' or
        'os.path'.
    :param member_name: (optional) a name of an attribute in that module to
        return.  It may contain dots.  e.g. 'MyClass.some_method'.  If not
        given, the named module will be returned instead.
    :raises: ImportError or AttributeError.
    """
    # We may have just a module name, or a module name and a member name,
    # and either may contain dots.  __import__'s return value is a bit
    # unintuitive, so we need to take care to always return the object
    # specified by the full combination of module name + member name.
    if member_name:
        # Give __import__ a from_list.  It will return the last module in
        # the dotted module name.
        attr_chain = member_name.split('.')
        from_list = attr_chain[:1]
        obj = __import__(module_name, {}, {}, from_list)
        for attr in attr_chain:
            obj = getattr(obj, attr)
    else:
        # We're just importing a module, no attributes, so we have no
        # from_list.  __import__ will return the first module in the dotted
        # module name, so we look up the module from sys.modules.
        __import__(module_name, globals(), locals(), [])
        obj = sys.modules[module_name]
    return obj


def iter_suite_tests(suite):
    """Return all tests in a suite, recursing through nested suites"""
    if isinstance(suite, TestCase):
        yield suite
    elif isinstance(suite, TestSuite):
        for item in suite:
            for r in iter_suite_tests(item):
                yield r
    else:
        raise Exception('unknown type %r for object %r'
                        % (type(suite), suite))


def clone_test(test, new_id):
    """Clone a test giving it a new id.

    :param test: The test to clone.
    :param new_id: The id to assign to it.
    :return: The new test.
    """
    new_test = copy.copy(test)
    new_test.id = lambda: new_id
    # XXX: Workaround <https://bugs.launchpad.net/testtools/+bug/637725>, which
    # causes cloned tests to share the 'details' dict.  This makes it hard to
    # read the test output for parameterized tests, because tracebacks will be
    # associated with irrelevant tests.
    try:
        new_test._TestCase__details
    except AttributeError:
        # must be a different version of testtools than expected.  Do nothing.
        pass
    else:
        # Reset the '__details' dict.
        new_test._TestCase__details = {}
    return new_test


def apply_scenario(test, scenario):
    """Copy test and apply scenario to it.

    :param test: A test to adapt.
    :param scenario: A tuple describing the scenario.
        The first element of the tuple is the new test id.
        The second element is a dict containing attributes to set on the
        test.
    :return: The adapted test.
    """
    new_id = "%s(%s)" % (test.id(), scenario[0])
    new_test = clone_test(test, new_id)
    for name, value in scenario[1].items():
        setattr(new_test, name, value)
    return new_test


def apply_scenarios(test, scenarios, result):
    """Apply the scenarios in scenarios to test and add to result.

    :param test: The test to apply scenarios to.
    :param scenarios: An iterable of scenarios to apply to test.
    :return: result
    :seealso: apply_scenario
    """
    for scenario in scenarios:
        result.addTest(apply_scenario(test, scenario))
    return result


def multiply_tests(tests, scenarios, result):
    """Multiply tests_list by scenarios into result.

    This is the core workhorse for test parameterisation.

    Typically the load_tests() method for a per-implementation test suite will
    call multiply_tests and return the result.

    :param tests: The tests to parameterise.
    :param scenarios: The scenarios to apply: pairs of (scenario_name,
        scenario_param_dict).
    :param result: A TestSuite to add created tests to.

    This returns the passed in result TestSuite with the cross product of all
    the tests repeated once for each scenario.  Each test is adapted by adding
    the scenario name at the end of its id(), and updating the test object's
    __dict__ with the scenario_param_dict.

    >>> import tests.test_sampler
    >>> r = multiply_tests(
    ...     tests.test_sampler.DemoTest('test_nothing'),
    ...     [('one', dict(param=1)),
    ...      ('two', dict(param=2))],
    ...     TestUtil.TestSuite())
    >>> tests = list(iter_suite_tests(r))
    >>> len(tests)
    2
    >>> tests[0].id()
    'tests.test_sampler.DemoTest.test_nothing(one)'
    >>> tests[0].param
    1
    >>> tests[1].param
    2
    """
    for test in iter_suite_tests(tests):
        apply_scenarios(test, scenarios, result)
    return result


def permute_tests_for_extension(standard_tests, loader, py_module_name,
                                ext_module_name):
    """Helper for permutating tests against an extension module.

    This is meant to be used inside a modules 'load_tests()' function. It will
    create 2 scenarios, and cause all tests in the 'standard_tests' to be run
    against both implementations. Setting 'test.module' to the appropriate
    module. See tests.test__chk_map.load_tests as an example.

    :param standard_tests: A test suite to permute
    :param loader: A TestLoader
    :param py_module_name: The python path to a python module that can always
        be loaded, and will be considered the 'python' implementation. (eg
        '_chk_map_py')
    :param ext_module_name: The python path to an extension module. If the
        module cannot be loaded, a single test will be added, which notes that
        the module is not available. If it can be loaded, all standard_tests
        will be run against that module.
    :return: (suite, feature) suite is a test-suite that has all the permuted
        tests. feature is the Feature object that can be used to determine if
        the module is available.
    """

    py_module = get_named_object(py_module_name)
    scenarios = [
        ('python', {'module': py_module}),
    ]
    suite = loader.suiteClass()
    try:
        __import__(ext_module_name)
    except ModuleNotFoundError:
        pass
    else:
        scenarios.append(('C', {'module': get_named_object(ext_module_name)}))
    result = multiply_tests(standard_tests, scenarios, suite)
    return result


def load_tests(loader, standard_tests, pattern):
    return permute_tests_for_extension(
        standard_tests, loader, 'fastbencode._bencode_py',
        'fastbencode._bencode_pyx')


class RecursionLimit(object):
    """Context manager that lowers recursion limit for testing."""

    def __init__(self, limit=100):
        self._new_limit = limit
        self._old_limit = sys.getrecursionlimit()

    def __enter__(self):
        sys.setrecursionlimit(self._new_limit)
        return self

    def __exit__(self, *exc_info):
        sys.setrecursionlimit(self._old_limit)


class TestBencodeDecode(TestCase):

    module = None

    def _check(self, expected, source):
        self.assertEqual(expected, self.module.bdecode(source))

    def _run_check_error(self, exc, bad):
        """Check that bdecoding a string raises a particular exception."""
        self.assertRaises(exc, self.module.bdecode, bad)

    def test_int(self):
        self._check(0, b'i0e')
        self._check(4, b'i4e')
        self._check(123456789, b'i123456789e')
        self._check(-10, b'i-10e')
        self._check(int('1' * 1000), b'i' + (b'1' * 1000) + b'e')

    def test_long(self):
        self._check(12345678901234567890, b'i12345678901234567890e')
        self._check(-12345678901234567890, b'i-12345678901234567890e')

    def test_malformed_int(self):
        self._run_check_error(ValueError, b'ie')
        self._run_check_error(ValueError, b'i-e')
        self._run_check_error(ValueError, b'i-010e')
        self._run_check_error(ValueError, b'i-0e')
        self._run_check_error(ValueError, b'i00e')
        self._run_check_error(ValueError, b'i01e')
        self._run_check_error(ValueError, b'i-03e')
        self._run_check_error(ValueError, b'i')
        self._run_check_error(ValueError, b'i123')
        self._run_check_error(ValueError, b'i341foo382e')

    def test_string(self):
        self._check(b'', b'0:')
        self._check(b'abc', b'3:abc')
        self._check(b'1234567890', b'10:1234567890')

    def test_large_string(self):
        self.assertRaises(ValueError, self.module.bdecode, b"2147483639:foo")

    def test_malformed_string(self):
        self._run_check_error(ValueError, b'10:x')
        self._run_check_error(ValueError, b'10:')
        self._run_check_error(ValueError, b'10')
        self._run_check_error(ValueError, b'01:x')
        self._run_check_error(ValueError, b'00:')
        self._run_check_error(ValueError, b'35208734823ljdahflajhdf')
        self._run_check_error(ValueError, b'432432432432432:foo')
        self._run_check_error(ValueError, b' 1:x')  # leading whitespace
        self._run_check_error(ValueError, b'-1:x')  # negative
        self._run_check_error(ValueError, b'1 x')  # space vs colon
        self._run_check_error(ValueError, b'1x')  # missing colon
        self._run_check_error(ValueError, (b'1' * 1000) + b':')

    def test_list(self):
        self._check([], b'le')
        self._check([b'', b'', b''], b'l0:0:0:e')
        self._check([1, 2, 3], b'li1ei2ei3ee')
        self._check([b'asd', b'xy'], b'l3:asd2:xye')
        self._check([[b'Alice', b'Bob'], [2, 3]], b'll5:Alice3:Bobeli2ei3eee')

    def test_list_deepnested(self):
        import platform
        if platform.python_implementation() == 'PyPy':
            self.skipTest('recursion not an issue on pypy')
        with RecursionLimit():
            self._run_check_error(RuntimeError, (b"l" * 100) + (b"e" * 100))

    def test_malformed_list(self):
        self._run_check_error(ValueError, b'l')
        self._run_check_error(ValueError, b'l01:ae')
        self._run_check_error(ValueError, b'l0:')
        self._run_check_error(ValueError, b'li1e')
        self._run_check_error(ValueError, b'l-3:e')

    def test_dict(self):
        self._check({}, b'de')
        self._check({b'': 3}, b'd0:i3ee')
        self._check({b'age': 25, b'eyes': b'blue'}, b'd3:agei25e4:eyes4:bluee')
        self._check({b'spam.mp3': {b'author': b'Alice', b'length': 100000}},
                    b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee')

    def test_dict_deepnested(self):
        with RecursionLimit():
            self._run_check_error(
                RuntimeError, (b"d0:" * 1000) + b'i1e' + (b"e" * 1000))

    def test_malformed_dict(self):
        self._run_check_error(ValueError, b'd')
        self._run_check_error(ValueError, b'defoobar')
        self._run_check_error(ValueError, b'd3:fooe')
        self._run_check_error(ValueError, b'di1e0:e')
        self._run_check_error(ValueError, b'd1:b0:1:a0:e')
        self._run_check_error(ValueError, b'd1:a0:1:a0:e')
        self._run_check_error(ValueError, b'd0:0:')
        self._run_check_error(ValueError, b'd0:')
        self._run_check_error(ValueError, b'd432432432432432432:e')

    def test_empty_string(self):
        self.assertRaises(ValueError, self.module.bdecode, b'')

    def test_junk(self):
        self._run_check_error(ValueError, b'i6easd')
        self._run_check_error(ValueError, b'2:abfdjslhfld')
        self._run_check_error(ValueError, b'0:0:')
        self._run_check_error(ValueError, b'leanfdldjfh')

    def test_unknown_object(self):
        self.assertRaises(ValueError, self.module.bdecode, b'relwjhrlewjh')

    def test_unsupported_type(self):
        self._run_check_error(TypeError, float(1.5))
        self._run_check_error(TypeError, None)
        self._run_check_error(TypeError, lambda x: x)
        self._run_check_error(TypeError, object)
        self._run_check_error(TypeError, u"ie")

    def test_decoder_type_error(self):
        self.assertRaises(TypeError, self.module.bdecode, 1)


class TestBencodeEncode(TestCase):

    module = None

    def _check(self, expected, source):
        self.assertEqual(expected, self.module.bencode(source))

    def test_int(self):
        self._check(b'i4e', 4)
        self._check(b'i0e', 0)
        self._check(b'i-10e', -10)

    def test_long(self):
        self._check(b'i12345678901234567890e', 12345678901234567890)
        self._check(b'i-12345678901234567890e', -12345678901234567890)

    def test_string(self):
        self._check(b'0:', b'')
        self._check(b'3:abc', b'abc')
        self._check(b'10:1234567890', b'1234567890')

    def test_list(self):
        self._check(b'le', [])
        self._check(b'li1ei2ei3ee', [1, 2, 3])
        self._check(b'll5:Alice3:Bobeli2ei3eee', [[b'Alice', b'Bob'], [2, 3]])

    def test_list_as_tuple(self):
        self._check(b'le', ())
        self._check(b'li1ei2ei3ee', (1, 2, 3))
        self._check(b'll5:Alice3:Bobeli2ei3eee', ((b'Alice', b'Bob'), (2, 3)))

    def test_list_deep_nested(self):
        top = []
        lst = top
        for unused_i in range(1000):
            lst.append([])
            lst = lst[0]
        with RecursionLimit():
            self.assertRaises(RuntimeError, self.module.bencode, top)

    def test_dict(self):
        self._check(b'de', {})
        self._check(b'd3:agei25e4:eyes4:bluee', {b'age': 25, b'eyes': b'blue'})
        self._check(b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee',
                    {b'spam.mp3': {b'author': b'Alice', b'length': 100000}})

    def test_dict_deep_nested(self):
        d = top = {}
        for i in range(1000):
            d[b''] = {}
            d = d[b'']
        with RecursionLimit():
            self.assertRaises(RuntimeError, self.module.bencode, top)

    def test_bencached(self):
        self._check(b'i3e', self.module.Bencached(self.module.bencode(3)))

    def test_invalid_dict(self):
        self.assertRaises(TypeError, self.module.bencode, {1: b"foo"})

    def test_bool(self):
        self._check(b'i1e', True)
        self._check(b'i0e', False)
