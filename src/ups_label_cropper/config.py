import json
from dataclasses import dataclass, asdict
from pathlib import Path

import platformdirs


@dataclass
class Config:
    watched_directory: str
    printer_name: str | None = None
    processed_folder: str = "processed"
    poll_interval_seconds: float = 1.0

    @classmethod
    def default_config_path(cls) -> Path:
        return Path(platformdirs.user_data_dir("UPS-Label-Cropper")) / "config.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        if path is None:
            path = cls.default_config_path()

        if not path.exists():
            config = cls._create_default()
            config.save(path)
            return config

        with open(path) as f:
            data = json.load(f)
        return cls(
            watched_directory=data["watched_directory"],
            printer_name=data.get("printer_name"),
            processed_folder=data.get("processed_folder", "processed"),
            poll_interval_seconds=data.get("poll_interval_seconds", 1.0),
        )

    @classmethod
    def _create_default(cls) -> "Config":
        default_watch = Path.home() / "UPSLabels"
        default_watch.mkdir(exist_ok=True)
        return cls(watched_directory=str(default_watch))

    def save(self, path: Path | None = None) -> None:
        if path is None:
            path = self.default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=4)

    def get_processed_dir(self) -> Path:
        processed = Path(self.watched_directory) / self.processed_folder
        processed.mkdir(exist_ok=True)
        return processed