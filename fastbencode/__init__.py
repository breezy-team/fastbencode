# Copyright (C) 2007, 2009 Canonical Ltd
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

"""Wrapper around the bencode cython and python implementation"""

from typing import Type


__version__ = (0, 1)


_extension_load_failures = []


def failed_to_load_extension(exception):
    """Handle failing to load a binary extension.

    This should be called from the ImportError block guarding the attempt to
    import the native extension.  If this function returns, the pure-Python
    implementation should be loaded instead::

    >>> try:
    >>>     import _fictional_extension_pyx
    >>> except ImportError, e:
    >>>     failed_to_load_extension(e)
    >>>     import _fictional_extension_py
    """
    # NB: This docstring is just an example, not a doctest, because doctest
    # currently can't cope with the use of lazy imports in this namespace --
    # mbp 20090729

    # This currently doesn't report the failure at the time it occurs, because
    # they tend to happen very early in startup when we can't check config
    # files etc, and also we want to report all failures but not spam the user
    # with 10 warnings.
    exception_str = str(exception)
    if exception_str not in _extension_load_failures:
        import warnings
        warnings.warn(
            'failed to load compiled extension: %s' % exception_str,
            UserWarning)
        _extension_load_failures.append(exception_str)


Bencached: Type

try:
    from ._bencode_pyx import bdecode, bdecode_as_tuple, bencode, Bencached
except ImportError as e:
    failed_to_load_extension(e)
    from ._bencode_py import (  # noqa: F401
        bdecode,
        bdecode_as_tuple,
        bencode,
        Bencached,
        )
