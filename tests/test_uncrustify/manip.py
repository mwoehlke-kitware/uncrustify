# Utilities for manipulating an output stream.
#
# * @author  Matthew Woehlke    September 2018
#

import re

RE_VERSION = re.compile(r'\buncrustify-[0-9a-g._-]+(-?dirty)?\b', re.I)


# =============================================================================
class Manipulators(object):
    # -------------------------------------------------------------------------
    @staticmethod
    def string_replace(text, old, new):
        return text.replace(old, new)

    # -------------------------------------------------------------------------
    @staticmethod
    def regex_replace(text, pattern, replacement):
        return re.sub(pattern, replacement, text)

    # -------------------------------------------------------------------------
    @staticmethod
    def normalize_version(text):
        return RE_VERSION.sub('Uncrustify-<VERSION>', text)
