#!/usr/bin/python3

import os
import sys
from setuptools import setup, Extension
try:
    from packaging.version import Version
except ImportError:
    from distutils.version import LooseVersion as Version

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
    cython_version_info = Version(cython_version)
    if cython_version_info < Version(minimum_cython_version):
        print("Version of Cython is too old. "
              "Current is %s, need at least %s."
              % (cython_version, minimum_cython_version))
        print("If the .c files are available, they will be built,"
              " but modifying the .pyx files will not rebuild them.")
        have_cython = False
    else:
        have_cython = True


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
            libraries=libraries, include_dirs=include_dirs,
            optional=os.environ.get('CIBUILDWHEEL', '0') != '1'))


add_cython_extension('fastbencode._bencode_pyx')


setup(ext_modules=ext_modules, cmdclass={'build_ext': build_ext})
