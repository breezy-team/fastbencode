# bencode structured encoding
#
# Written by Petru Paler
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# Modifications copyright (C) 2008 Canonical Ltd
# Modifications copyright (C) 2021-2023 Jelmer Vernooĳ


from typing import Callable, Dict, List, Type


class BDecoder:
    def __init__(self, yield_tuples=False, bytestring_encoding=None) -> None:
        """Constructor.

        :param yield_tuples: if true, decode "l" elements as tuples rather than
            lists.
        """
        self.yield_tuples = yield_tuples
        self.bytestring_encoding = bytestring_encoding
        decode_func = {}
        decode_func[b"l"] = self.decode_list
        decode_func[b"d"] = self.decode_dict
        decode_func[b"i"] = self.decode_int
        decode_func[b"0"] = self.decode_bytes
        decode_func[b"1"] = self.decode_bytes
        decode_func[b"2"] = self.decode_bytes
        decode_func[b"3"] = self.decode_bytes
        decode_func[b"4"] = self.decode_bytes
        decode_func[b"5"] = self.decode_bytes
        decode_func[b"6"] = self.decode_bytes
        decode_func[b"7"] = self.decode_bytes
        decode_func[b"8"] = self.decode_bytes
        decode_func[b"9"] = self.decode_bytes
        self.decode_func = decode_func

    def decode_int(self, x, f):
        f += 1
        newf = x.index(b"e", f)
        n = int(x[f:newf])
        if x[f : f + 2] == b"-0":
            raise ValueError
        elif x[f : f + 1] == b"0" and newf != f + 1:
            raise ValueError
        return (n, newf + 1)

    def decode_bytes(self, x, f):
        colon = x.index(b":", f)
        n = int(x[f:colon])
        if x[f : f + 1] == b"0" and colon != f + 1:
            raise ValueError
        colon += 1
        d = x[colon : colon + n]
        if self.bytestring_encoding:
            d = d.decode(self.bytestring_encoding)
        return (d, colon + n)

    def decode_list(self, x, f):
        r, f = [], f + 1
        while x[f : f + 1] != b"e":
            v, f = self.decode_func[x[f : f + 1]](x, f)
            r.append(v)
        if self.yield_tuples:
            r = tuple(r)
        return (r, f + 1)

    def decode_dict(self, x, f):
        r, f = {}, f + 1
        lastkey = None
        while x[f : f + 1] != b"e":
            k, f = self.decode_bytes(x, f)
            if lastkey is not None and lastkey >= k:
                raise ValueError
            lastkey = k
            r[k], f = self.decode_func[x[f : f + 1]](x, f)
        return (r, f + 1)

    def bdecode(self, x):
        if not isinstance(x, bytes):
            raise TypeError
        try:
            r, l = self.decode_func[x[:1]](x, 0)  # noqa: E741
        except (IndexError, KeyError, OverflowError) as e:
            raise ValueError(str(e))
        if l != len(x):  # noqa: E741
            raise ValueError
        return r


_decoder = BDecoder()
bdecode = _decoder.bdecode

_tuple_decoder = BDecoder(True)
bdecode_as_tuple = _tuple_decoder.bdecode

_utf8_decoder = BDecoder(bytestring_encoding="utf-8")
bdecode_utf8 = _utf8_decoder.bdecode


class Bencached:
    __slots__ = ["bencoded"]

    def __init__(self, s) -> None:
        self.bencoded = s


class BEncoder:
    def __init__(self, bytestring_encoding=None):
        self.bytestring_encoding = bytestring_encoding
        self.encode_func: Dict[Type, Callable[[object, List[bytes]], None]] = {
            Bencached: self.encode_bencached,
            int: self.encode_int,
            bytes: self.encode_bytes,
            list: self.encode_list,
            tuple: self.encode_list,
            dict: self.encode_dict,
            bool: self.encode_bool,
            str: self.encode_str,
        }

    def encode_bencached(self, x, r):
        r.append(x.bencoded)

    def encode_bool(self, x, r):
        self.encode_int(int(x), r)

    def encode_int(self, x, r):
        r.extend((b"i", int_to_bytes(x), b"e"))

    def encode_bytes(self, x, r):
        r.extend((int_to_bytes(len(x)), b":", x))

    def encode_list(self, x, r):
        r.append(b"l")
        for i in x:
            self.encode(i, r)
        r.append(b"e")

    def encode_dict(self, x, r):
        r.append(b"d")
        ilist = sorted(x.items())
        for k, v in ilist:
            r.extend((int_to_bytes(len(k)), b":", k))
            self.encode(v, r)
        r.append(b"e")

    def encode_str(self, x, r):
        if self.bytestring_encoding is None:
            raise TypeError(
                "string found but no encoding specified. "
                "Use bencode_utf8 rather bencode?"
            )
        return self.encode_bytes(x.encode(self.bytestring_encoding), r)

    def encode(self, x, r):
        self.encode_func[type(x)](x, r)


def int_to_bytes(n):
    return b"%d" % n


def bencode(x):
    r = []
    encoder = BEncoder()
    encoder.encode(x, r)
    return b"".join(r)


def bencode_utf8(x):
    r = []
    encoder = BEncoder(bytestring_encoding="utf-8")
    encoder.encode(x, r)
    return b"".join(r)
