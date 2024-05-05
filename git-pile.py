if __import__("platform").system() == "Windows":
    kernel32 = __import__("ctypes").windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    del kernel32

import os
import subprocess
import sys

from ghapi.all import GhApi

api = GhApi()

SPLIT_ON = "44f0da21-87ba-43ca-98d9-3b348d84e7c5"

ANSI_RED = "\033[0;31m"
ANSI_LIGHT_RED = "\033[1;31m"
ANSI_LIGHT_GREEN = "\033[1;32m"
ANSI_END = "\033[0m"


def log(*args):
    print("pile:", *args)


def get_username():
    ghu = os.environ.get("GITHUB_USERNAME")
    if ghu:
        return ghu
    u = os.environ.get("USERNAME")
    if u:
        return u
    log("unable to get a username")
    sys.exit(1)


USERNAME = get_username()


def username_prefixed_br(br):
    return USERNAME + "/" + br


def get_git(*args, ignore_errors=False):
    args = list(args)
    # print("git", args)
    proc = subprocess.run(["git"] + args, check=not ignore_errors, capture_output=True)
    return proc.stdout.decode("utf-8").strip()


def output_git(*args):
    args = list(args)
    # print("git", args)
    subprocess.run(["git"] + args, check=True)


def print_changes(ups, br, indent):
    output_git(
        "log",
        "--oneline",
        "--reverse",
        ups + ".." + br,
        "--no-decorate",
        "--pretty="
        + (" " * (indent + 4))
        + "│ … %C(yellow)%h%C(reset) %C(brightblack)%s%C(reset)",
    )


def get_current_branch():
    return get_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "HEAD")


def _walk_pile_impl(do_print):
    # Current branch.
    current = br = get_current_branch()
    branches = [br]

    # Walk tracking upwards.
    while br != "origin/main":
        br = get_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", br + "@{u}")
        branches.append(br)

    allbrs = get_git(
        "for-each-ref",
        "--format=%(refname:short)" + SPLIT_ON + "%(upstream:short)",
        "refs/heads/",
    )
    upstr = {}
    for line in allbrs.splitlines():
        br, _, ups = line.partition(SPLIT_ON)
        upstr[br] = ups

    pile = []
    indent = -4

    for i, br in enumerate(reversed(branches)):
        leader = " " * indent + "╰── " if i > 0 else ""
        prefix = ANSI_LIGHT_GREEN if br == current else ""
        suffix = " ←" + ANSI_END if br == current else ""
        pile.append((br, branches[-i]))
        if do_print:
            print(leader + prefix + br + suffix)
            print_changes(branches[-i], br, indent)
        indent += 4

    def walk_downstream_of(of, indent):
        for br, ups in upstr.items():
            if ups == of:
                if do_print:
                    print(" " * indent + "╰── " + br)
                    print_changes(ups, br, indent)
                pile.append((br, ups))
                walk_downstream_of(br, indent + 4)

    walk_downstream_of(current, indent)

    # Don't include origin/main.
    return pile[1:]


def get_pile():
    return _walk_pile_impl(False)


def print_pile():
    _walk_pile_impl(True)


def create_squash_commit(br, ups):
    latest_tree = get_git("rev-parse", br + ":")
    if ups != "origin/main":
        ups = "pr/" + ups
    return get_git("commit-tree", latest_tree, "-p", ups, "-m", br).strip()


def squash_to_pr_and_push(br, ups):
    commit = create_squash_commit(br, ups)
    pr_br = "pr/" + br
    get_git("branch", "--force", pr_br, commit)
    get_git("push", "origin", pr_br + ":" + username_prefixed_br(br), "-f")


def remove_pr_branch(br):
    pr_br = "pr/" + br
    get_git("branch", "-D", pr_br)


def push_pr_branches_for_pile(pile):
    log("snapshotting")

    for br, ups in pile:
        print("  " + br + "...", end="")
        squash_to_pr_and_push(br, ups)
        print(" %s" % get_br_pr_url(br))

    for br, _ in pile:
        remove_pr_branch(br)

    log("done")


def create_draft_pr(br, ups):
    url = get_git("remote", "get-url", "origin")
    before, _, path = url.partition(":")
    user, _, repo = path.partition("/")
    if not user or not repo or not repo.endswith(".git"):
        print("couldn't parse origin %s" % url)
        sys.exit(1)
    repo = repo[: -len(".git")]
    base = ups
    if base == "origin/main":
        base = "main"
    else:
        base = username_prefixed_br(base)
    data = api.pulls.create(
        owner=user,
        repo=repo,
        title=br,
        base=base,
        body="",
        draft=True,
        head=username_prefixed_br(br),
    )
    get_git(
        "config",
        "--local",
        "branch.%s.pile-pr-html-url" % br,
        data["_links"]["html"]["href"],
    )
    get_git("config", "--local", "branch.%s.pile-pr-number" % br, str(data["number"]))


def get_br_pr_url(br):
    return get_git("config", "--local", "branch.%s.pile-pr-html-url" % br)


def make_new_branch(br, ups):
    try:
        get_git("checkout", "-b", br, ups, "-t")
    except:
        print('failed, branch "%s" already exists?' % br)
        sys.exit(1)
    get_git("commit", "--allow-empty", "-m", br + " created")
    squash_to_pr_and_push(br, ups)
    create_draft_pr(br, ups)
    log('created "%s" and switched to it' % br)
    log("draft PR at %s" % get_br_pr_url(br))


def sync_pile(pile):
    log(ANSI_LIGHT_GREEN + "fetching from origin" + ANSI_END)
    get_git("fetch", "origin")
    for br, ups in pile:
        log(
            ANSI_LIGHT_GREEN
            + 'starting rebase of "%s", tracking is "%s"' % (br, ups)
            + ANSI_END
        )
        get_git("checkout", br)
        get_git("rebase", ups)


def usage(msg):
    print("git pile %s" % msg)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print_pile()
    elif sys.argv[1] == "register-aliases":
        get_git("config", "--global", "alias.new", "pile new")
        get_git("config", "--global", "alias.more", "pile more")
        get_git("config", "--global", "alias.snap", "pile snap")
        get_git("config", "--global", "alias.sync", "pile sync")
        log("aliases added")
    elif sys.argv[1] == "new":
        if len(sys.argv) < 3:
            usage("new <branch-name>")
        make_new_branch(sys.argv[2], "origin/main")
    elif sys.argv[1] == "more":
        if len(sys.argv) < 3:
            usage("more <branch-name>")
        make_new_branch(sys.argv[2], get_current_branch())
    elif sys.argv[1] == "snap":
        push_pr_branches_for_pile(get_pile())
    elif sys.argv[1] == "sync":
        sync_pile(get_pile())
    else:
        log('unknown command "%s"' % sys.argv[1])
        sys.exit(1)


if __name__ == "__main__":
    main()
