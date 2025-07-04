# Sphinx documentation scaffold for music-automation-toolkit

# To build docs:
# 1. cd docs
# 2. make html

project = 'music-automation-toolkit'
author = 'Georgie'
release = '2.0.0'
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
html_theme = 'alabaster'
