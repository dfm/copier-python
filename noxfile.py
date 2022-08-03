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

from contextlib import contextmanager
from tempfile import TemporaryDirectory

import nox
from plumbum import local
from plumbum.cmd import cp, git, rm

ACTIONLINT_URL = "https://raw.githubusercontent.com/rhysd/actionlint/v1.6.15/scripts/download-actionlint.bash"


def generate_in(session, target, *args):
    session.install("copier")
    all_files = git("ls-tree", "--name-only", "HEAD").splitlines()
    # First copy the template to a temporary directory and install from there
    with TemporaryDirectory() as template:
        for file in all_files:
            cp("-r", file, template)

        # Tag a 'test' release in this temporary directory
        with local.cwd(template):
            git("init", ".")
            git("add", ".")
            git(
                "commit",
                "--message=test",
                "--author=Test<test@test>",
                "--no-verify",
            )
            git("tag", "--force", "test")

        # Generate the copy from the temporary copy
        session.run(
            "copier",
            "-f",
            template,
            target,
            "-d",
            'project_name="dfm test package"',
            *args
        )

    # Set up the copy as a git repository for SCM purposes
    with local.cwd(target):
        git("init", ".")
        git("add", ".")


@contextmanager
def generate(session, *args):
    with TemporaryDirectory() as d:
        generate_in(session, d, *args)
        yield d


@contextmanager
def install(session, *args):
    with generate(session, *args) as d:
        with session.chdir(d):
            session.install("-e", ".")
        yield d


@nox.session
def tests(session):
    session.install("pytest")
    with install(session):
        session.run("pytest", "-v", "tests/test_basic.py")


@nox.session
def compiled(session):
    session.install("pytest")
    with install(session, "-d", "enable_pybind11=yes"):
        session.run("pytest", "-v", "tests/test_compiled.py")


@nox.session
def generated(session):
    # Install actionlint in the virtualenv
    from plumbum.cmd import bash, curl

    with local.cwd(session._runner.venv.bin):
        cmd = curl[ACTIONLINT_URL] | bash
        cmd()

    # Run the tests in the generated project
    session.install("nox")
    with generate(session) as d:
        with session.chdir(d):
            session.run("actionlint", external="error")
            session.run("nox")


@nox.session
@nox.parametrize("compiled", [True, False])
def build(session, compiled):
    session.install("build", "twine")
    args = ("-d", "enable_pybind11=yes") if compiled else ()
    with generate(session, *args) as d:
        with session.chdir(d):
            session.run("python", "-m", "build")
            session.run("python", "-m", "twine", "check", "--strict", "dist/*")

    with generate(session) as d:
        with session.chdir(d):
            session.run("python", "-m", "build")
            session.run("python", "-m", "twine", "check", "--strict", "dist/*")


@nox.session
def lint(session):
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files")


@nox.session
def update_pre_commit(session):
    session.install("pre-commit")
    session.run(
        "pre-commit", "autoupdate", "-c", "template/.pre-commit-config.yaml"
    )


@nox.session
def demo(session):
    rm("-rf", "demo.generated")
    generate_in(session, "demo.generated", *session.posargs)
