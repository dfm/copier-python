import os
import re
from tempfile import TemporaryDirectory

import github
import plumbum
from plumbum import local
from plumbum.cmd import git, python

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
            git(
                "commit",
                "--author=Dan F-M <dfm@dfm.io>",
                "--no-verify",
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

    if list(repo.get_pulls(state="open", base=branch)):
        print("Pull request already exists; skipping.")
        return

    repo.create_pull(
        title=f"[copier] Updating template to version {version}",
        body=f"""**This is an automated PR from https://github.com/dfm/copier-python**

This updates the template to version {version}. If there are merge conflicts,
they will be indicated with `*.rej` files that will be committed to this branch.
In this case, the `lint` workflow will fail, and you will need to resolve these
conflicts manually:

```
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


if __name__ == "__main__":
    search_repos()
