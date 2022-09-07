fastbencode
===========

fastbencode is an implementation of the bencode serialization format originally
used by BitTorrent.

The package includes both a pure-Python version and an optional C extension
based on Cython.  Both provide the same functionality, but the C extension
provides significantly better performance.

Example:

    >>> from fastbencode import bencode, bdecode
    >>> bencode([1, 2, b'a', {b'd': 3}])
    b'li1ei2e1:ad1:di3eee'
    >>> bdecode(bencode([1, 2, b'a', {b'd': 3}]))
    [1, 2, b'a', {b'd': 3}]

License
=======
fastbencode is available under the GNU GPL, version 2 or later.

Copyright
=========

* Original Pure-Python bencoder (c) Petru Paler
* Cython version and modifications (c) Canonical Ltd
* Split out from Bazaar/Breezy by Jelmer Vernooĳ
