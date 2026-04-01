# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=invalid-name

from flask import render_template, request  # pylint: disable=import-error


def init_views(app):

    @app.route('/settings')
    def settings():
        ctx = {
            'ws_ip_port': "{}:{}".format(request.host.split(':')[0], 13000),
            'lang': 'en',
        }
        return render_template('settings.html', **ctx)
