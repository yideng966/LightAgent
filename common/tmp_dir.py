import os

from common.utils import expand_path
from config import conf


class TmpDir(object):
    """Temporary directory for transient artifacts (e.g. synthesized voice).

    Resolves to ``<agent_workspace>/tmp`` (default ``~/lightagent/tmp``) so temp files
    land inside the agent workspace instead of a CWD-relative ``./tmp``, which
    is unreliable for the packaged desktop app where CWD is undefined.
    """

    def __init__(self):
        ws_root = expand_path(conf().get("agent_workspace", "~/lightagent"))
        self.tmpFilePath = os.path.join(ws_root, "tmp")
        os.makedirs(self.tmpFilePath, exist_ok=True)

    def path(self):
        return str(self.tmpFilePath) + "/"
