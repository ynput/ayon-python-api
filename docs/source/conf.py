import os
import sys
sys.path.insert(0, os.path.abspath('../../'))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

current_dir = os.path.dirname(os.path.abspath(__file__))
ayon_api_version_path = os.path.join(
    os.path.dirname(os.path.dirname(current_dir)),
    "ayon_api",
    "version.py"
)
version_content = {}
with open(ayon_api_version_path, "r") as stream:
    exec(stream.read(), version_content)
project = 'ayon-python-api'
copyright = '2024, ynput.io <info@ynput.io>'
author = 'ynput.io <info@ynput.io>'
release = version_content["__version__"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.mathjax',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx.ext.napoleon',
    'revitron_sphinx_theme',
]

# -- Napoleon settings -------------------------------------------------------
add_module_names = False

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_attr_annotations = True

templates_path = ['_templates']
exclude_patterns = ['tests', 'venv', 'build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "revitron_sphinx_theme"
html_static_path = ['_static']
html_logo = './_static/AYON_blackG_dot.svg'
html_favicon = './_static/favicon.ico'

html_context = {
    'landing_page': {
    }
}
myst_footnote_transition = False
html_sidebars = {}

html_theme_options = {
    'color_scheme': '',
    'canonical_url': 'https://github.com/ynput/ayon-python-api',
    'style_external_links': False,
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': False,
    'titles_only': False,
    'github_url': 'https://github.com/ynput/ayon-python-api',
}
