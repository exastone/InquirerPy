"""Servers as another entry point for `InquirerPy`.

See Also:
    :ref:`index:Alternate Syntax`.

`inquirer` directly interact with individual prompt classes. It’s more flexible, easier to customise and also provides IDE type hintings/completions.
"""

__all__ = [
    "checkbox",
    "fuzzy",
]

from term_mark.InquirerPy.InquirerPy.prompts import CheckboxPrompt as checkbox
from term_mark.InquirerPy.InquirerPy.prompts import FuzzyPrompt as fuzzy
