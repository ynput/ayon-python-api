from typing import Literal

ActivityType = Literal[
    "comment",
    "watch",
    "reviewable",
    "status.change",
    "assignee.add",
    "assignee.remove",
    "version.publish"
]

ActivityReferenceType = Literal[
    "origin",
    "mention",
    "author",
    "relation",
    "watching",
]
