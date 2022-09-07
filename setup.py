#!/usr/bin/python3

import os
import sys
from setuptools import setup
from distutils.version import LooseVersion

try:
    from Cython.Distutils import build_ext
    from Cython.Compiler.Version import version as cython_version
except ImportError:
    have_cython = False
    # try to build the extension from the prior generated source.
    print("")
    print("The python package 'Cython' is not available."
          " If the .c files are available,")
    print("they will be built,"
          " but modifying the .pyx files will not rebuild them.")
    print("")
    from distutils.command.build_ext import build_ext
else:
    minimum_cython_version = '0.29'
    cython_version_info = LooseVersion(cython_version)
    if cython_version_info < LooseVersion(minimum_cython_version):
        print("Version of Cython is too old. "
              "Current is %s, need at least %s."
              % (cython_version, minimum_cython_version))
        print("If the .c files are available, they will be built,"
              " but modifying the .pyx files will not rebuild them.")
        have_cython = False
    else:
        have_cython = True


from distutils import log
from distutils.errors import CCompilerError, DistutilsPlatformError
from distutils.extension import Extension


class build_ext_if_possible(build_ext):

    user_options = build_ext.user_options + [
        ('allow-python-fallback', None,
         "When an extension cannot be built, allow falling"
         " back to the pure-python implementation.")
        ]

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.allow_python_fallback = False

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            e = sys.exc_info()[1]
            if not self.allow_python_fallback:
                log.warn('\n  Cannot build extensions.\n'
                         '  Use "build_ext --allow-python-fallback" to use'
                         ' slower python implementations instead.\n')
                raise
            log.warn(str(e))
            log.warn('\n  Extensions cannot be built.\n'
                     '  Using the slower Python implementations instead.\n')

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except CCompilerError:
            if not self.allow_python_fallback:
                log.warn('\n  Cannot build extension "%s".\n'
                         '  Use "build_ext --allow-python-fallback" to use'
                         ' slower python implementations instead.\n'
                         % (ext.name,))
                raise
            log.warn('\n  Building of "%s" extension failed.\n'
                     '  Using the slower Python implementation instead.'
                     % (ext.name,))


# Override the build_ext if we have Cython available

ext_modules = []


def add_cython_extension(module_name, libraries=None, extra_source=[]):
    """Add a cython module to build.

    This will use Cython to auto-generate the .c file if it is available.
    Otherwise it will fall back on the .c file. If the .c file is not
    available, it will warn, and not add anything.

    You can pass any extra options to Extension through kwargs. One example is
    'libraries = []'.

    :param module_name: The python path to the module. This will be used to
        determine the .pyx and .c files to use.
    """
    path = module_name.replace('.', '/')
    cython_name = path + '.pyx'
    c_name = path + '.c'
    define_macros = []
    if sys.platform == 'win32':
        # cython uses the macro WIN32 to detect the platform, even though it
        # should be using something like _WIN32 or MS_WINDOWS, oh well, we can
        # give it the right value.
        define_macros.append(('WIN32', None))
    if have_cython:
        source = [cython_name]
    else:
        if not os.path.isfile(c_name):
            return
        else:
            source = [c_name]
    source.extend(extra_source)
    include_dirs = ['fastbencode']
    ext_modules.append(
        Extension(
            module_name, source, define_macros=define_macros,
            libraries=libraries, include_dirs=include_dirs))


add_cython_extension('fastbencode._bencode_pyx')

with open('README.md', 'r') as f:
    long_description = f.read()


setup(
    name="fastbencode",
    description="Implementation of bencode with optional fast C extensions",
    version="0.0.10",
    long_description=long_description,
    maintainer="Breezy Developers",
    maintainer_email="breezy-core@googlegroups.com",
    url="https://github.com/breezy-team/fastbencode",
    ext_modules=ext_modules,
    extras_require={'cext': ['cython>=0.29']},
    cmdclass={'build_ext': build_ext_if_possible},
    license="GPLv2 or later",
    test_suite="fastbencode.tests.test_suite",
    packages=["fastbencode"])
