# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string


from flask import (render_template, request) # pylint: disable=import-error

def init_remote_ui(app, db):

    @app.route('/ui')
    def home():

        template = '/remote_ui.html'

        ctx = {
            'ws_ip_port': "{}:{}".format(request.host.split(':')[0], 13000),
            'lang': 'en',
        }
        return render_template(template, **ctx)
