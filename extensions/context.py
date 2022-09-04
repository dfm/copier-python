from datetime import datetime

from copier_templates_extensions import ContextHook


class ContextUpdater(ContextHook):
    def hook(self, context):
        year = context["copyright_year"]
        return {"copyright_range": f"{year}-{datetime.today().year}"}
