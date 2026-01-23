"""
Módulo de segurança e autenticação.
"""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings


api_key_header = APIKeyHeader(name=settings.api_key_name, auto_error=True)


async def verify_api_key(key: str = Security(api_key_header)) -> str:
    """
    Verifica se a API Key fornecida é válida.
    
    Args:
        key: Chave da API recebida no header.
        
    Returns:
        A chave validada.
        
    Raises:
        HTTPException: Se a chave for inválida.
    """
    if key == settings.api_key:
        return key
    raise HTTPException(status_code=401, detail="Chave de API inválida")
