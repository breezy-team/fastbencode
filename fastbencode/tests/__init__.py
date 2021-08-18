# Copyright (C) 2007, 2009, 2010 Canonical Ltd
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
#

"""Tests for fastbencode."""

import unittest


def test_suite():
    names = [
        'test_bencode',
        ]
    module_names = ['fastbencode.tests.' + name for name in names]
    result = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(module_names)
    result.addTests(suite)

    return result
