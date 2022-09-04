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

import os
import re
from tempfile import TemporaryDirectory

import github
import plumbum
from plumbum import local

git = local["git"]
python = local["python"]
api = github.Github(os.environ["GITHUB_PAT"])


def search_repos():
    done = set()
    for file in api.search_code('"gh:dfm/copier-python"'):
        if file.path != ".copier-answers.yml":
            continue
        repo = file.repository
        name = repo.full_name
        if name in done:
            continue
        done.add(name)
        update_repo(file.repository)


def has_diff(*args):
    try:
        git("diff", "--quiet", *args, retcode=1)
    except plumbum.ProcessExecutionError:
        return False
    else:
        return True


def is_dirty():
    if git("status", "--porcelain", "-unormal").strip():
        return True
    if has_diff():
        return True
    if has_diff("--staged"):
        return True
    return False


def update_branch(clone_url):
    with TemporaryDirectory() as d:
        clone_url = clone_url.replace(
            "https://", f"https://dfm:{os.environ['GITHUB_PAT']}@"
        )
        git("clone", clone_url, d)
        with local.cwd(d):
            # Force update of the template
            result = python["-m", "copier", "--force", "update"].run()
            assert result[0] == 0
            copier_log = result[2]

            # Parse the log to find the updated version number
            versions = re.findall(
                "Updating to template version (.*)", copier_log
            )
            if not versions:
                raise RuntimeError(
                    f"Could not find version in copier log:\n{copier_log}"
                )
            version = versions[0]

            if not is_dirty():
                print("No changes.")
                return None

            # Check out the new branch
            branch = f"copier/{version}"
            git("checkout", "-b", branch)
            git("add", ".")
            git("config", "user.email", "dfm@dfm.io")
            git("config", "user.name", "Dan F-M")
            git(
                "commit",
                f"--message=Updating template to {version}\n\n{copier_log}",
            )
            git("push", "--force", "origin", branch)
    return version, branch, copier_log


def update_repo(repo):
    print(f"Updating {repo.full_name}...")
    if not repo.permissions.push:
        print("Don't have push access; skipping.")

    update = update_branch(repo.clone_url)
    if update is None:
        return
    version, branch, log = update

    try:
        repo.create_pull(
            title=f"[copier] Updating template to version {version}",
            body=f"""**This is an automated PR from https://github.com/dfm/copier-python**

This updates the template to version {version}. If there are merge conflicts,
they will be indicated with `*.rej` files that will be committed to this branch.
In this case, the `lint` workflow will fail, and you will need to resolve these
conflicts manually:

```bash
git checkout -b {branch} origin/{branch}
# Fix the conflicts and commit
git push origin {branch}
```

Full update log below:

<details>
<summary>Copier log</summary>

```
{log}
```
</details>
""",
            base=repo.default_branch,
            head=branch,
        )
    except github.GithubException.GithubException:
        print("PR already exists; skipping.")


if __name__ == "__main__":
    search_repos()
