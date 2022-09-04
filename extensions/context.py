# Copyright 2022 Dan Foreman-Mackey
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime

from copier_templates_extensions import ContextHook


class ContextUpdater(ContextHook):
    def hook(self, context):
        try:
            start_year = int(context["copyright_year"])
        except ValueError:
            return {"copyright_range": context["copyright_year"]}
        end_year = datetime.now().year
        if start_year >= end_year:
            return {"copyright_range": f"{start_year}"}
        return {"copyright_range": f"{start_year}-{end_year}"}
