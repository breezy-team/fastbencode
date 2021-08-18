fastbencode
===========

fastbencode is an implementation of the bencode serialization format originally
used by BitTorrent.

The package includes both a pure-Python version and an optional C extension
based on Cython.  Both provide the same functionality, but the C extension
provides significantly better performance.

Copyright
=========

Original Pure-Python bencoder (c) Petru Paler
Cython version and modifications (c) Canonical Ltd
Split out from Bazaar/Breezy by Jelmer Vernooĳ
