fastbencode
===========

fastbencode is an implementation of the bencode serialization format originally
used by BitTorrent.

The package includes both a pure-Python version and an optional Rust extension
based on PyO3. Both provide the same functionality, but the Rust extension
provides significantly better performance.

Example:

    >>> from fastbencode import bencode, bdecode
    >>> bencode([1, 2, b'a', {b'd': 3}])
    b'li1ei2e1:ad1:di3eee'
    >>> bdecode(bencode([1, 2, b'a', {b'd': 3}]))
    [1, 2, b'a', {b'd': 3}]

The default ``bencode``/``bdecode`` functions just operate on
bytestrings. Use ``bencode_utf8`` / ``bdecode_utf8`` to
serialize/deserialize all plain strings as UTF-8 bytestrings.
Note that for performance reasons, all dictionary keys still have to be
bytestrings.

License
=======
fastbencode is available under the GNU GPL, version 2 or later.

Copyright
=========

* Original Pure-Python bencoder © Petru Paler
* Split out from Bazaar/Breezy by Jelmer Vernooĳ
* Rust extension © Jelmer Vernooĳ
