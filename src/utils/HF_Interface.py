from .config_manager import ConfigManager
from dotenv import dotenv_values
from pathlib import Path
import shutil

class Interface:
    def __init__(self) -> None:
        self.config = ConfigManager("connections.yaml")
        self.read_token = dotenv_values(".env")["HUGGINGFACE_READ_TOKEN"]


    def download_raws(self) -> None:
        from huggingface_hub import snapshot_download

        localD = self.config.find_root() / self.config["LOCAL_DATA_PATH"]
        shutil.rmtree(localD / self.config["HF_RAW_PATH"], ignore_errors=True)

        snapshot_download(
            repo_id=self.config["HF_REPO_ADDRESS"],
            repo_type="dataset",
            allow_patterns=[f"{self.config["HF_RAW_PATH"]}*"],
            local_dir=localD,
            token=self.read_token
        )

    def download_processed(self) -> None:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=self.config["HF_REPO_ADDRESS"],
            repo_type="dataset",
            allow_patterns=[f"{self.config["HF_PROCESSED_PATH"]}*"],
            local_dir=self.config.find_root() / self.config["LOCAL_DATA_PATH"],
            token=self.read_token
        )

    def download_file(self, path:str|Path) -> None:
        from huggingface_hub import hf_hub_download

        hf_hub_download(
            repo_id=self.config["HF_REPO_ADDRESS"],
            filename=path,
            repo_type="dataset",
            token=self.read_token
        )

    def download_all(self):
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=self.config["HF_REPO_ADDRESS"],
            repo_type="dataset",
            local_dir=self.config.find_root() / self.config["LOCAL_DATA_PATH"],
            token=self.read_token
        )
