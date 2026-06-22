from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_port: int = 8000
    log_level: str = "INFO"

    bot_id: str = ""
    bot_secret_key: str = ""
    botx_base_url: str = ""
    botx_proto_version: str = ""
    bot_admin_huids: str = ""

    ldap_host: str = ""
    ldap_port: int = 636
    ldap_use_ssl: bool = True
    ldap_bind_user: str = ""
    ldap_bind_password: str = ""
    ldap_bind_password_file: Path | None = None
    ldap_base_dn: str = ""
    ldap_included_ous: str = ""
    ldap_excluded_ous: str = ""
    ldap_ca_cert_file: str = ""
    ldap_connect_timeout_seconds: int = 10
    ldap_read_timeout_seconds: int = 15

    search_limit: int = 5
    cache_db_path: Path = Field(default=Path("/data/cache.sqlite3"))
    cache_ttl_seconds: int = 86400

    @property
    def admin_huids(self) -> set[str]:
        return {item.strip() for item in self.bot_admin_huids.split(",") if item.strip()}

    @property
    def included_ous(self) -> list[str]:
        return [item.strip() for item in self.ldap_included_ous.split(";") if item.strip()]

    @property
    def excluded_ous(self) -> list[str]:
        return [item.strip() for item in self.ldap_excluded_ous.split(";") if item.strip()]

    @field_validator("ldap_bind_password_file", mode="before")
    @classmethod
    def _empty_password_file_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def ldap_password(self) -> str:
        if self.ldap_bind_password_file:
            return self.ldap_bind_password_file.read_text(encoding="utf-8").strip()
        return self.ldap_bind_password


@lru_cache
def get_settings() -> Settings:
    return Settings()
