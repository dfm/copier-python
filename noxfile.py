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
from functools import partial
from tempfile import TemporaryDirectory

import nox


@contextmanager
def generate(session, *args):
    with TemporaryDirectory() as d:
        session.install("copier")
        session.run(
            "copier",
            "-f",
            ".",
            d,
            "-d",
            'project_name="dfm test package"',
            *args
        )
        with session.chdir(d):
            session.run("git", "init", ".", external=True)
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
