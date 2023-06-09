from setuptools import setup, Extension
from distutils.command.build_ext import build_ext as build_ext_orig


class build_ext(build_ext_orig):
    def build_extension(self, ext):
        self._ctypes = ext in ctype_ext
        return super().build_extension(ext)

    def get_export_symbols(self, ext):
        if self._ctypes:
            return ext.export_symbols
        return super().get_export_symbols(ext)

    def get_ext_filename(self, ext_name):
        if self._ctypes:
            return ext_name + ".so"
        return super().get_ext_filename(ext_name)


ctype_ext = [
    Extension(
        "fastqueue.cllqueue",
        ["src/cllqueue.cpp"],
    ),
    Extension(
        "fastqueue.ccqueue",
        ["src/ccqueue.cpp"],
    ),
]

setup(
    include_package_data=True,
    py_modules=['fastqueue'],
    packages=["fastqueue"],
    ext_modules=ctype_ext
    + [
        Extension(
            "_fastqueue",
            ["src/fastqueue.c"],
        )
    ],
    cmdclass={"build_ext": build_ext},
)
