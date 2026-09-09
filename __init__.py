# -*- coding: utf-8 -*-
try:
    from . import models
    from . import wizards
    from . import controllers
except (ImportError, ModuleNotFoundError):
    # Running outside Odoo daemon runtime (e.g. standalone adapter tests)
    pass

from . import adapter
