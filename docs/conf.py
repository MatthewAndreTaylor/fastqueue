import os
import sys

sys.path.insert(0, os.path.abspath("."))

project = "fastqueue"
copyright = "2023, Matthew Taylor"
author = "Matthew Taylor"

extensions = ["sphinx.ext.autodoc", "m2r2"]

source_suffix = [".rst", ".md"]

templates_path = ["_templates"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
