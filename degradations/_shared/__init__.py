"""Helpers shared by several degradation bundles.

One bundle per operator means the kernels and filters that several operators build on
have no single bundle to live in. They live here instead. The leading underscore keeps
the package out of the registry's discovery walk, which skips any module or package whose
name starts with one, so nothing here is ever mistaken for an operator.
"""
