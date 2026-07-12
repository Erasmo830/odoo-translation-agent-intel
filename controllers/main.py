# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)

class AutoLoginHome(Home):
    @http.route('/web/login', type='http', auth='none')
    def web_login(self, redirect=None, **kw):
        _logger.info("AutoLoginHome: Intercepted /web/login request")
        # Bypass login page by automatically authenticating the admin user
        if not request.session.uid:
            try:
                # Standard developer auto-login bypass for admin user in odoo_traductor
                _logger.info("AutoLoginHome: Authenticating admin user...")
                request.session.authenticate('odoo_traductor_v2', 'admin', 'admin')
                _logger.info("AutoLoginHome: Authentication successful, redirecting to /web")
                return request.redirect(redirect or '/web')
            except Exception as e:
                _logger.exception("Bypass authentication failed:")
                pass
        return super(AutoLoginHome, self).web_login(redirect=redirect, **kw)
