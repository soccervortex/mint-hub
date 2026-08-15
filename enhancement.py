"""Enhancement data model — works with both API responses and local scan results."""


class Enhancement:
    __slots__ = (
        "id", "slug", "name", "version", "author", "category", "summary",
        "description", "thumbnail_url", "thumbnail_local", "download_url",
        "file_size", "install_path", "apply_command", "revert_command",
        "dependencies", "tags", "screenshots", "downloads", "avg_rating",
        "num_reviews", "score", "featured", "mint_versions", "license",
        "homepage", "changelog", "status", "created_at", "updated_at",
        "installed", "installed_version", "applied", "source", "writable",
    )

    def __init__(self):
        self.id = ""
        self.slug = ""
        self.name = ""
        self.version = "1.0.0"
        self.author = ""
        self.category = ""
        self.summary = ""
        self.description = ""
        self.thumbnail_url = ""
        self.thumbnail_local = ""
        self.download_url = ""
        self.file_size = 0
        self.install_path = ""
        self.apply_command = ""
        self.revert_command = ""
        self.dependencies = []
        self.tags = []
        self.screenshots = []
        self.downloads = 0
        self.avg_rating = 0.0
        self.num_reviews = 0
        self.score = 0.0
        self.featured = False
        self.mint_versions = []
        self.license = "GPL-3.0"
        self.homepage = ""
        self.changelog = ""
        self.status = "published"
        self.created_at = ""
        self.updated_at = ""
        self.installed = False
        self.installed_version = ""
        self.applied = False
        self.source = "remote"
        self.writable = True

    @classmethod
    def from_api(cls, data: dict) -> "Enhancement":
        e = cls()
        for key in cls.__slots__:
            if key in data:
                setattr(e, key, data[key])
        e.source = "remote"
        return e

    @classmethod
    def from_local(cls, name: str, category: str, path: str, **kwargs) -> "Enhancement":
        e = cls()
        e.name = name
        e.slug = name.lower().replace(" ", "-").replace("_", "-")
        e.category = category
        e.install_path = path
        e.installed = True
        e.installed_version = "local"
        e.source = "local"
        for k, v in kwargs.items():
            if hasattr(e, k):
                setattr(e, k, v)
        return e

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}

    def __repr__(self):
        return f"<Enhancement {self.slug} [{self.category}] {'installed' if self.installed else 'available'}>"
