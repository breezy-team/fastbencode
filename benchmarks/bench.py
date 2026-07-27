"""Benchmark the fastbencode encode/decode implementations.

Times the pure-Python implementation and, if the compiled extension is
available, the Rust implementation, across a handful of representative
payloads. Run with no arguments for a summary:

    python benchmarks/bench.py

Use --json to emit machine-readable results instead.
"""

import argparse
import json
import timeit

from fastbencode import _bencode_py

try:
    from fastbencode import _bencode_rs
except ModuleNotFoundError:
    _bencode_rs = None


def payloads():
    """Return named sample structures covering common shapes."""
    return {
        "flat_list": list(range(1000)),
        "flat_dict": {b"key%04d" % i: i for i in range(1000)},
        "strings": [b"x" * 20 for _ in range(1000)],
        "nested": {
            b"meta": {b"a": list(range(50)), b"b": [b"y" * 10] * 50},
            b"items": [{b"id": i, b"name": b"n" * 8} for i in range(200)],
        },
        "ints": list(range(-500, 500)),
    }


def time_ms(fn, number, repeat):
    """Return the fastest per-call time in milliseconds over repeat runs."""
    best = min(timeit.repeat(fn, number=number, repeat=repeat))
    return best / number * 1000


def measure(module, number, repeat):
    """Time encode and decode of every payload for one implementation."""
    result = {}
    for name, value in payloads().items():
        encoded = module.bencode(value)
        result[name] = {
            "encode": time_ms(lambda: module.bencode(value), number, repeat),
            "decode": time_ms(lambda: module.bdecode(encoded), number, repeat),
        }
    return result


def implementations():
    impls = {"python": _bencode_py}
    if _bencode_rs is not None:
        impls["rust"] = _bencode_rs
    return impls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--number", type=int, default=3000, help="calls per timing run"
    )
    parser.add_argument(
        "--repeat", type=int, default=5, help="timing runs to take the min of"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit results as JSON"
    )
    args = parser.parse_args()

    impls = implementations()
    results = {
        name: measure(module, args.number, args.repeat)
        for name, module in impls.items()
    }

    if args.json:
        print(json.dumps(results, indent=2))
        return

    for name in impls:
        print(f"\n{name} (ms per call, lower is better)")
        print(f"  {'payload':12s} {'encode':>9s} {'decode':>9s}")
        for payload, timings in results[name].items():
            print(
                f"  {payload:12s} {timings['encode']:9.4f} "
                f"{timings['decode']:9.4f}"
            )

    if "rust" in results and "python" in results:
        print("\npython / rust ratio (higher means Python is slower)")
        print(f"  {'payload':12s} {'encode':>9s} {'decode':>9s}")
        for payload in results["python"]:
            enc = results["python"][payload]["encode"] / (
                results["rust"][payload]["encode"] or float("inf")
            )
            dec = results["python"][payload]["decode"] / (
                results["rust"][payload]["decode"] or float("inf")
            )
            print(f"  {payload:12s} {enc:8.1f}x {dec:8.1f}x")


if __name__ == "__main__":
    main()
