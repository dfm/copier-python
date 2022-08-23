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
from pathlib import Path
from tempfile import TemporaryDirectory

import nox
from plumbum import local

cp = local["cp"]
git = local["git"]
rm = local["rm"]

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
            session.install(
                "--upgrade",
                "--upgrade-strategy",
                "eager",
                "--no-cache-dir",
                ".",
                silent=False,
            )

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
def setuptools(session):
    session.install("pytest")
    session.install("pip", "setuptools<58.3.0")  # Old version used on RTDs
    session.install(
        *"mock==1.0.1 pillow==5.4.1 alabaster>=0.7,<0.8,!=0.7.5 commonmark==0.8.1 recommonmark==0.5.0 sphinx<2 sphinx-rtd-theme<0.5 readthedocs-sphinx-ext<2.2 jinja2<3.1.0 setuptools<58.3.0".split()
    )
    session.run("pip", "--version")
    with install(session):
        session.run("pytest", "-v", "tests/test_basic.py")


@nox.session
def corner(session):
    session.install("pip", "setuptools<58.3.0")  # Old version used on RTDs
    session.install(
        *"mock==1.0.1 pillow==5.4.1 alabaster>=0.7,<0.8,!=0.7.5 commonmark==0.8.1 recommonmark==0.5.0 sphinx<2 sphinx-rtd-theme<0.5 readthedocs-sphinx-ext<2.2 jinja2<3.1.0 setuptools<58.3.0".split()
    )
    session.run("pip", "--version")
    with TemporaryDirectory() as d:
        git("clone", "https://github.com/dfm/corner.py", d)
        with local.cwd(d):
            git("checkout", "template")
            print(local["ls"]())
        with session.chdir(d):
            session.install(".", silent=False)


@nox.session
def generated(session):
    # Install actionlint in the virtualenv
    with local.cwd(session._runner.venv.bin):
        cmd = local["curl"][ACTIONLINT_URL] | local["bash"]
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
def old_setuptools(session):
    session.install("nox")
    with generate(session) as d:
        session.install("setuptools==57.4.0")
        with open(Path(d) / "tmp.py", "w") as f:
            f.write(
                """
import nox

@nox.session(venv_params=["--system-site-packages"])
def test(session):
    session.install("pytest")
    session.install(".")
    session.run("pytest", "-v")

"""
            )
        with session.chdir(d):
            session.run("nox", "--", "--noxfile", "tmp.py")


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
