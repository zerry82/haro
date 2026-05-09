from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE_ROOT = str(PROJECT_ROOT / "runtime" / "workspaces")


class Settings(BaseSettings):
    gemini_api_key: str = ""
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 1440
    db_data_dir: str = "./data/pgdata"
    workspace_root: str = DEFAULT_WORKSPACE_ROOT
    host: str = "0.0.0.0"
    port: int = 8001
    cors_origins: str = "http://localhost:5174"

    # Sandbox settings
    sandbox_image: str = "denoland/deno:latest"
    sandbox_mem_limit: str = "256m"
    sandbox_cpu_quota: int = 50000
    sandbox_cpu_period: int = 100000
    sandbox_idle_timeout_minutes: int = 30
    sandbox_work_idle_timeout_minutes: int = 5
    sandbox_exec_timeout: int = 30
    sandbox_docker_timeout: int = 3
    sandbox_docker_circuit_breaker_seconds: int = 30
    sandbox_stop_containers_on_shutdown: bool = False
    sandbox_default_node_host: str = "unix:///var/run/docker.sock"
    sandbox_default_node_max_containers: int = 10

    # Web search settings
    web_search_provider: str = "searxng"
    web_search_base_url: str = ""
    web_search_api_key: str = ""
    web_search_timeout_seconds: float = 10.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("workspace_root")
    @classmethod
    def resolve_workspace_root(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path.resolve())


settings = Settings()
