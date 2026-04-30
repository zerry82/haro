from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 1440
    db_data_dir: str = "./data/pgdata"
    workspace_root: str = "./data/workspaces"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
