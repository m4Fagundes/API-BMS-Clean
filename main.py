import uvicorn
import io
import base64
import os
import secrets
import pdfplumber
import logging

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional

# --- Configuração ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDF_API")

app = FastAPI(title="BMS Spec Extractor API", version="1.1.0")

# --- Segurança ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
REAL_KEY = "minha-chave-secreta-123" 

async def verify_key(key: str = Security(api_key_header)):
    if key == REAL_KEY:
        return key
    raise HTTPException(401, "Chave inválida")

# --- Modelos ---
class PdfRequest(BaseModel):
    arquivo_base64: str

class SectionRequest(BaseModel):
    arquivo_base64: str
    inicio_texto: str
    fim_texto: Optional[str] = None

# --- Lógica de Extração Otimizada ---
def extract_text_pypdf(pdf_bytes, limit=None, maintain_layout=True):
    """
    maintain_layout=True: Preserva espaços (Bom para tabelas M.7)
    maintain_layout=False: Texto corrido (Bom para Sumário/TOC)
    """
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages[:limit] if limit else pdf.pages
        for page in pages:
            # Aqui está a mágica: layout=False remove os espaços inúteis
            extracted = page.extract_text(layout=maintain_layout) 
            if extracted:
                text += extracted + "\n"
    return text

# --- Endpoints ---

@app.post("/extract-toc", dependencies=[Depends(verify_key)])
async def get_toc(req: PdfRequest):
    """
    Navegador: Extrai as primeiras 20 páginas SEM layout visual.
    Resultado: Texto limpo e denso para o GPT ler o índice.
    """
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        # MUDANÇA: maintain_layout=False para limpar os espaços em branco
        text = extract_text_pypdf(pdf_bytes, limit=20, maintain_layout=False)
        return {"text": text}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, str(e))

@app.post("/extract-section", dependencies=[Depends(verify_key)])
async def get_section(req: SectionRequest):
    """
    Extrator: Lê o PDF todo COM layout visual.
    Resultado: Texto formatado para preservar as colunas das tabelas.
    """
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        # MANTÉM layout=True aqui para as tabelas não quebrarem
        full_text = extract_text_pypdf(pdf_bytes, maintain_layout=True)
        
        # Lógica de Corte
        idx_start = full_text.find(req.inicio_texto)
        
        # Fallback: Se não achar o texto exato com layout, tenta achar sem layout (opcional, mas seguro)
        if idx_start == -1:
             raise HTTPException(404, f"Marcador de início '{req.inicio_texto}' não encontrado no texto formatado.")

        if req.fim_texto:
            idx_end = full_text.find(req.fim_texto, idx_start)
            if idx_end == -1:
                final_text = full_text[idx_start:]
            else:
                final_text = full_text[idx_start:idx_end]
        else:
            final_text = full_text[idx_start:]
            
        return {"section_text": final_text}
        
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)