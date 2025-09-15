#!/usr/bin/python3


from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    rust_extensions=[
        RustExtension(
            "fastbencode._bencode_rs",
            binding=Binding.PyO3,
            py_limited_api=False,
            optional=True,
        )
    ],
)
