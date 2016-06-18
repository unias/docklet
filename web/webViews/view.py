from flask import render_template, request, abort, session

import os, inspect
this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))

version_file = open(this_folder + '/../../VERSION')
version = version_file.read()
version_file.close()

class normalView():
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        return self.render(self.template_path)

    @classmethod
    def post(self):
        return self.render(self.template_path)

    @classmethod
    def error(self):
        abort(404)

    @classmethod
    def as_view(self):
        # type: () -> object
        if request.method == 'GET':
            return self.get()
        elif request.method == 'POST':
            return self.post()
        else:
            return self.error()

    @classmethod
    def render(self, *args, **kwargs):
        self.mysession = dict(session)
        kwargs['mysession'] = self.mysession
        kwargs['version'] = version
        return render_template(*args, **kwargs)
