"""
Configurações centralizadas da aplicação.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configurações da API usando Pydantic Settings."""
    
    # API Info
    app_name: str = "BMS: PDF & Complex Excel Generator"
    app_version: str = "5.0.0"
    
    # Security
    api_key_name: str = "X-API-Key"
    api_key: str = "minha-chave-secreta-123"
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()


settings = get_settings()
