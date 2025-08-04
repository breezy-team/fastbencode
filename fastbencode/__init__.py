# Copyright (C) 2021-2023 Jelmer Vernooĳ <jelmer@jelmer.uk>
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

"""Wrapper around the bencode Rust and Python implementations."""

from typing import Type

__version__ = (0, 3, 4)


Bencached: Type

try:
    from fastbencode._bencode_rs import (
        Bencached,
        bdecode,
        bdecode_as_tuple,
        bdecode_utf8,
        bencode,
        bencode_utf8,
    )
except ModuleNotFoundError as e:
    import warnings

    warnings.warn(f"failed to load compiled extension: {e}", UserWarning)

    # Fall back to pure Python implementation
    from ._bencode_py import (  # noqa: F401
        Bencached,
        bdecode,
        bdecode_as_tuple,
        bdecode_utf8,
        bencode,
        bencode_utf8,
    )
