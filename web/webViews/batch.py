from flask import session, redirect, request
from webViews.view import normalView
from webViews.checkname import checkname
from webViews.dockletrequest import dockletRequest

class batchJobListView(normalView):
    template_path = "batch/batch_list.html"

    @classmethod
    def get(self):
        if True:
            return self.render(self.template_path)
        else:
            return self.error()

class createBatchJobView(normalView):
    template_path = "batch/batch_create.html"
    
    @classmethod
    def get(self):
        masterips = dockletRequest.post_to_all()
        images = dockletRequest.post("/image/list/",{},masterips[0].split("@")[0]).get("images")
        if True:
            return self.render(self.template_path, masterips=masterips, images=images)
        else:
            return self.error()

class stateBatchJobView(normalView):
    template_path = "batch/batch_state.html"

    @classmethod
    def get(self):
        if True:
            return self.render(self.template_path)
        else:
            return self.error()

class addBatchJobView(normalView):
    template_path = "batch/batch_list.html"

    @classmethod
    def post(self):
        if True:
            return self.render(self.template_path)
        else:
            return self.error()
