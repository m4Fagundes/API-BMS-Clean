"""
Rotas relacionadas a operações com PDF.
"""
import base64
import logging

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Query, Request
from pydantic import BaseModel

from src.core.security import verify_api_key
from src.domain.models import (
    PdfRequest, 
    SectionRequest,
    SectionToImagesRequest,
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


class PagesToBase64Request(BaseModel):
    """Request para converter páginas do PDF em imagens Base64."""
    arquivo_base64: str
    pages: list[int] | None = None  # None = todas as páginas
    dpi: int = 150
    include_data_uri: bool = True


@router.post("/pages-to-base64", dependencies=[Depends(verify_api_key)])
async def pages_to_base64(req: PagesToBase64Request):
    """
    Converte páginas do PDF para Base64 - **OTIMIZADO PARA POWER AUTOMATE**.
    
    Recebe JSON com PDF em Base64 e retorna array de imagens Base64.
    Formato idêntico aos outros endpoints da API.
    
    **Formato de Entrada (JSON Body):**
    ```json
    {
        "arquivo_base64": "JVBERi0xLjQK...",
        "pages": [1, 2, 3],
        "dpi": 150,
        "include_data_uri": true
    }
    ```
    
    **Formato de Resposta:**
    ```json
    {
        "total_pages": 3,
        "images": [
            {"page": 1, "base64": "data:image/png;base64,iVBORw0KGgo..."},
            {"page": 2, "base64": "data:image/png;base64,iVBORw0KGgo..."},
            {"page": 3, "base64": "data:image/png;base64,iVBORw0KGgo..."}
        ]
    }
    ```
    
    Args:
        arquivo_base64: PDF em Base64
        pages: Lista de páginas específicas (ex: [1,2,5]). Null = todas
        dpi: Resolução das imagens (default: 150)
        include_data_uri: Se true, inclui prefixo "data:image/png;base64," (default: true)
    
    Returns:
        JSON com total_pages e array de imagens em Base64
    """
    try:
        # Decodifica o PDF de Base64
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        
        # Converte páginas em imagens
        images = PdfConverter.pages_to_images(
            pdf_bytes,
            pages=req.pages,
            dpi=req.dpi
        )
        
        # Prepara prefixo Data URI se solicitado
        prefix = "data:image/png;base64," if req.include_data_uri else ""
        
        # Retorna JSON otimizado para Power Automate
        return {
            "total_pages": len(images),
            "images": [
                {
                    "page": img.page_number,
                    "base64": f"{prefix}{img.image_base64}"
                }
                for img in images
            ]
        }
    except Exception as e:
        logger.error(f"Erro ao converter páginas para Base64: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pages-to-images", dependencies=[Depends(verify_api_key)])
async def pages_to_images(
    file: UploadFile = File(..., description="Arquivo PDF para converter em imagens"),
    pages: str = Query(None, description="Páginas específicas separadas por vírgula (ex: 1,2,5). Vazio = todas"),
    dpi: int = Query(150, description="Resolução das imagens (DPI)")
):
    """
    Converte páginas do PDF em imagens PNG.
    
    Recebe um arquivo PDF e retorna cada página como imagem em base64.
    Formato otimizado para consumo no Power Automate.
    
    **Tudo em memória** - não salva arquivos em disco.
    
    Args:
        file: Arquivo PDF (upload direto)
        pages: Páginas específicas separadas por vírgula (ex: "1,2,5"). Vazio = todas
        dpi: Resolução das imagens (default: 150)
    
    Returns:
        JSON com total_pages e lista de páginas com image_base64
    """
    try:
        # Valida tipo do arquivo
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="O arquivo deve ser um PDF")
        
        # Lê o conteúdo do arquivo
        pdf_bytes = await file.read()
        
        # Parse das páginas (se fornecidas)
        page_list = None
        if pages:
            try:
                page_list = [int(p.strip()) for p in pages.split(',') if p.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de páginas inválido. Use números separados por vírgula (ex: 1,2,5)")
        
        # Converte páginas em imagens
        images = PdfConverter.pages_to_images(
            pdf_bytes,
            pages=page_list,
            dpi=dpi
        )
        
        # Retorna JSON limpo para Power Automate
        return {
            "total_pages": len(images),
            "pages": [
                {
                    "page_number": img.page_number,
                    "image_base64": img.image_base64
                }
                for img in images
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao converter páginas em imagens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/split-pdf-to-images", dependencies=[Depends(verify_api_key)])
async def split_pdf_to_images(
    request: Request,
    page: int = Query(1, description="Número da página a processar (1-indexed). Use com 'total_only=true' primeiro para saber quantas páginas existem."),
    dpi: int = Query(150, description="Resolução das imagens (DPI)"),
    total_only: bool = Query(False, description="Se true, retorna apenas o total de páginas sem processar imagens")
):
    """
    🚀 **STREAM FRIENDLY + PAGINADO** - Converte PDF em imagens UMA POR VEZ.
    
    Resolve o limite de 100MB do Power Automate processando uma página por chamada.
    
    **FLUXO NO POWER AUTOMATE (2 etapas):**
    
    **Etapa 1 - Descobrir total de páginas:**
    - URI: /pdf/split-pdf-to-images?total_only=true
    - Retorna: {"total_pages": 27, "page": null, "image_base64": null}
    
    **Etapa 2 - Loop para cada página:**
    - URI: /pdf/split-pdf-to-images?page=1 (depois 2, 3, 4...)
    - Retorna: {"total_pages": 27, "page": 1, "image_base64": "data:image/png;base64,..."}
    
    **Configuração HTTP:**
    - Method: POST
    - Headers: Content-Type: application/octet-stream
    - Body: File Content (binário ou base64)
    - Settings: Chunking: ON
    
    Args:
        page: Número da página a processar (default: 1)
        dpi: Resolução das imagens (default: 150)
        total_only: Se true, retorna apenas contagem de páginas
    
    Returns:
        JSON com total_pages, page e image_base64 (null se total_only=true)
    """
    try:
        # Lê o corpo da requisição (pode ser raw binary ou base64)
        raw_body = await request.body()
        
        if not raw_body:
            raise HTTPException(
                status_code=400, 
                detail="Nenhum arquivo recebido. Envie o PDF no body da requisição."
            )
        
        # Detecta automaticamente o formato: raw binary ou base64
        if raw_body[:4] == b'%PDF':
            pdf_bytes = raw_body
            logger.info(f"PDF recebido como raw binary: {len(pdf_bytes)} bytes")
        elif raw_body[:6] == b'JVBERi':
            try:
                pdf_bytes = base64.b64decode(raw_body)
                logger.info(f"PDF recebido como Base64, decodificado: {len(pdf_bytes)} bytes")
            except Exception as decode_error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Falha ao decodificar Base64: {str(decode_error)}"
                )
        else:
            raise HTTPException(
                status_code=400, 
                detail="O arquivo recebido não é um PDF válido. Esperado: raw binary (%PDF) ou Base64 (JVBERi...)."
            )
        
        # Valida que após decodificação é um PDF válido
        if not pdf_bytes[:4] == b'%PDF':
            raise HTTPException(
                status_code=400, 
                detail="Após decodificação, o arquivo não é um PDF válido."
            )
        
        # Obtém total de páginas
        total_pages = PdfConverter.get_page_count(pdf_bytes)
        logger.info(f"PDF tem {total_pages} páginas")
        
        # Se só quer o total, retorna sem processar imagens
        if total_only:
            return {
                "total_pages": total_pages,
                "page": None,
                "image_base64": None
            }
        
        # Valida número da página
        if page < 1 or page > total_pages:
            raise HTTPException(
                status_code=400,
                detail=f"Página {page} inválida. O PDF tem {total_pages} páginas (1 a {total_pages})."
            )
        
        # Processa apenas a página solicitada
        images = PdfConverter.pages_to_images(
            pdf_bytes,
            pages=[page],
            dpi=dpi
        )
        
        if not images:
            raise HTTPException(
                status_code=500,
                detail=f"Falha ao processar página {page}"
            )
        
        img = images[0]
        logger.info(f"Página {page}/{total_pages} processada")
        
        # Retorna JSON com UMA imagem
        return {
            "total_pages": total_pages,
            "page": page,
            "image_base64": f"data:image/png;base64,{img.image_base64}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao converter PDF stream em imagens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
