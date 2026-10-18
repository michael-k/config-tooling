"""A package, so pytest names these modules ``tests.*`` rather than ``incus.tests.*``.

Under ``--import-mode=importlib`` a test module outside any package is named
after its path from the rootdir, and pytest would register this directory's
parent as a stand-in ``incus`` module that shadows the installed package.
"""
