import os
import subprocess
import sys

SELF = os.path.abspath(os.path.dirname(__file__))


def git(*args):
    args = list(args)
    print("git", args)
    subprocess.run(["git"] + args, check=True)


def write(contents, name):
    if contents[0] == "\n":
        contents = contents[1:]
    if contents[-1] != "\n":
        contents += "\n"
    with open(name, "w", encoding="utf-8", newline="\n") as f:
        f.write(contents)


def main():
    if len(sys.argv) != 2:
        print("usage: make_test_repo.py <step>")
        exit(1)

    if sys.argv[1] == "initial":
        initial()
    elif sys.argv[1] == "amend_first":
        amend_first()
    else:
        print("unknown step")
        exit(1)


def pile(*args):
    subprocess.run(
        [sys.executable, os.path.join(SELF, "git-pile.py")] + list(args), check=True
    )


def initial():
    if os.path.isdir(".git"):
        print("should not be a .git dir here already")
        exit(1)

    git("init")
    write("hi\n", "README.md")
    git("add", "README.md")
    git("commit", "-m", "Initial commit")
    git("branch", "-M", "main")
    git("remote", "add", "origin", "git@github.com:sgraham/git-pile-test.git")
    git("push", "-u", "origin", "main", "-f")

    pile("new", "feature1")
    write(
        """\
int main(void) {
}
""",
        "a.c",
    )
    git("add", "a.c")
    git("commit", "-m", "start feature")
    write(
        """\
int func(void) {
    return 4;
}
int main(void) {
    func();
}
""",
        "a.c",
    )
    git("add", "a.c")
    git("commit", "-m", "call func helper")

    pile("more", "part2")
    write(
        """\
extern int func();
int main(void) {
    func();
}
""",
        "a.c",
    )
    write(
        """\
int func(void) {
  return 4;
}
""",
        "b.c",
    )
    git("add", "a.c")
    git("add", "b.c")
    git("commit", "-m", "refactor func into separate file")

    write(
        """int func() {
  return 2+2;
}""",
        "b.c",
    )
    git("add", "b.c")
    git("commit", "-m", "improve func to be more clear")

    pile("more", "third_part")
    write("int stuff() { return 4;}", "c.c")
    git("add", "c.c")
    git("commit", "-m", "start on third part")

    write(
        """\
extern int stuff();
int func(void) {
  return stuff();
}
""",
        "b.c",
    )
    git("add", "b.c")
    git("commit", "-m", "use new c for implementing func")

    git("checkout", "part2")
    pile("more", "try_again_third_part")
    write("int stuff() { return 43; }", "c.c")
    git("add", "c.c")
    git("commit", "-m", "another attempt at c")


def amend_first():
    git("checkout", "feature1")
    write(
        """\
int func(void) {
    // secret value.
    return 4;
}
int main(void) {
    // call func
    func();
}
""",
        "a.c",
    )
    git("add", "a.c")
    git("commit", "-m", "update comments in a")


if __name__ == "__main__":
    main()
