"""
Rotas relacionadas a operações com PDF.
"""
import base64
import logging

from fastapi import APIRouter, HTTPException, Depends

from src.core.security import verify_api_key
from src.domain.models import (
    PdfRequest, 
    SectionRequest,
    SectionToImagesRequest,
    PagesToImagesRequest,
    PageImageResponse,
    ImagesToImagesResponse,
)
from src.infrastructure.pdf_extractor import PdfExtractor
from src.infrastructure.pdf_converter import PdfConverter


logger = logging.getLogger("BMS_API")
router = APIRouter(prefix="/pdf", tags=["PDF Operations"])


@router.post("/extract-toc", dependencies=[Depends(verify_api_key)])
async def extract_toc(req: PdfRequest):
    """
    Extrai o índice (Table of Contents) das primeiras páginas do PDF.
    
    Processa as primeiras 20 páginas do documento sem manter o layout original.
    """
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        text = PdfExtractor.extract_text(pdf_bytes, limit=20, maintain_layout=False)
        return {"text": text}
    except Exception as e:
        logger.error(f"Erro ao extrair TOC: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-section", dependencies=[Depends(verify_api_key)])
async def extract_section(req: SectionRequest):
    """
    Extrai uma seção específica do PDF entre marcadores de texto.
    
    Utiliza os parâmetros inicio_texto e fim_texto para delimitar a seção.
    """
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        section_text = PdfExtractor.extract_section(
            pdf_bytes, 
            req.inicio_texto, 
            req.fim_texto
        )
        return {"section_text": section_text}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao extrair seção: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/section-to-images", dependencies=[Depends(verify_api_key)], response_model=ImagesToImagesResponse)
async def section_to_images(req: SectionToImagesRequest):
    """
    Converte uma seção do PDF em imagens PNG.
    
    Encontra as páginas que contêm o texto entre os marcadores
    e converte cada página em uma imagem PNG serializada em base64.
    
    **Tudo em memória** - não salva arquivos em disco.
    
    Args:
        arquivo_base64: PDF em base64
        inicio_texto: Texto que marca o início da seção
        fim_texto: Texto que marca o fim da seção (opcional)
        dpi: Resolução das imagens (default: 150)
    
    Returns:
        Lista de imagens em base64 com metadados (página, dimensões)
    """
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        
        images = PdfConverter.section_to_images(
            pdf_bytes,
            start_marker=req.inicio_texto,
            end_marker=req.fim_texto,
            dpi=req.dpi or 150
        )
        
        return ImagesToImagesResponse(
            total_pages=len(images),
            images=[
                PageImageResponse(
                    page_number=img.page_number,
                    image_base64=img.image_base64,
                    width=img.width,
                    height=img.height
                )
                for img in images
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao converter seção em imagens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pages-to-images", dependencies=[Depends(verify_api_key)], response_model=ImagesToImagesResponse)
async def pages_to_images(req: PagesToImagesRequest):
    """
    Converte páginas específicas do PDF em imagens PNG.
    
    **Tudo em memória** - não salva arquivos em disco.
    
    Args:
        arquivo_base64: PDF em base64
        pages: Lista de números de página (1-indexed). None = todas as páginas
        dpi: Resolução das imagens (default: 150)
    
    Returns:
        Lista de imagens em base64 com metadados (página, dimensões)
    """
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        
        images = PdfConverter.pages_to_images(
            pdf_bytes,
            pages=req.pages,
            dpi=req.dpi or 150
        )
        
        return ImagesToImagesResponse(
            total_pages=len(images),
            images=[
                PageImageResponse(
                    page_number=img.page_number,
                    image_base64=img.image_base64,
                    width=img.width,
                    height=img.height
                )
                for img in images
            ]
        )
    except Exception as e:
        logger.error(f"Erro ao converter páginas em imagens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
