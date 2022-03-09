import tempfile
from .github_client import create_authenticated_repo_url
from typing import Tuple, Set, Dict, Iterable, Optional
from urllib import parse
from git import Git, Repo
GONE_SHA = '0000000000000000000000000000000000000000'

def prune_dotgit_suffix(s: str) -> str:
    'if the string ends with .git, remove that'
    if s.endswith('.git'):
        return s[:-4]
    return s

def sha_doesnt_exist(sha: str) -> bool:
    return sha == GONE_SHA

class CommitRange(object):
    repo: Optional[Repo]
    tmpdir: Optional[tempfile.TemporaryDirectory[str]]

    def __init__(self, repo_url: str, start: str, end: str) -> None:
        self.repo_url = repo_url
        # GitHub sends 0000 when the branch is new, for instance.
        if start == GONE_SHA:
            self.start = None
        else:
            self.start = start
        self.end = end
        self.repo = None
        self.tmpdir = None

    @property
    def owner_repo(self) -> Tuple[str, str]:
        parts = parse.urlparse(self.repo_url)
        (_, owner, repo, *rest) = parts.path.split('/')
        return (owner, prune_dotgit_suffix(repo))

    @property
    def head_sha(self) -> str:
        return self.end

    def _get_git_repo(self) -> Repo:
        if not self.repo:
            # setup clone stuff.
            self.tmpdir = tempfile.TemporaryDirectory()

            # TODO: shallower clone, ideally.
            self.repo = Repo.clone_from(
                # Auth needs to happen here so we don't send repo url to
                # upstreams
                create_authenticated_repo_url(self.repo_url),
                self.tmpdir.name
            )
        return self.repo

    def files_changed(self) -> Set[str]:
        repo = self._get_git_repo()
        head_commit = repo.commit(self.end)
        base_commit = repo.commit(self.start)

        changed = set()
        diffs = head_commit.diff(base_commit)
        for diff in diffs:
            # in the case of a rename, we want to know if either side has
            # the file name we care about.
            changed |= {diff.a_path, diff.b_path}

        return changed

    def get_file_contents_at_latest(self, filenames: Iterable[str]) -> Dict[str, str]:
        repo = self._get_git_repo()
        output = {}
        commit = repo.commit(self.end)
        for f in filenames:
            blob = commit.tree.join(f)
            # TODO: NPE?
            data = ''.join([x.decode('utf-8') for x in blob.data_stream.stream.readlines()])
            output[f] = data
        return output

    def __del__(self) -> None:
        del self.tmpdir  # not sure if this is necessary to clean up the temp file