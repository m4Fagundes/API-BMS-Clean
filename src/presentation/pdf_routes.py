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
from src.infrastructure.pdf_cache import pdf_cache


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


# ============================================================================
# CACHE SESSION ENDPOINTS - Upload único + extração de páginas sob demanda
# ============================================================================

class UploadResponse(BaseModel):
    """Resposta do upload de PDF para cache."""
    session_id: str
    total_pages: int
    expires_in_seconds: int


@router.post("/upload", dependencies=[Depends(verify_api_key)], response_model=UploadResponse)
async def upload_pdf_to_cache(request: Request):
    """
    📦 **UPLOAD ÚNICO** - Armazena PDF no cache para extração de páginas sob demanda.
    
    Evita reenviar o mesmo PDF várias vezes. Faça upload uma vez e extraia
    páginas individuais usando o session_id retornado.
    
    **Fluxo no Power Automate:**
    1. `POST /pdf/upload` → Recebe session_id
    2. `GET /pdf/page/{session_id}/1` → Página 1
    3. `GET /pdf/page/{session_id}/2` → Página 2
    4. ... e assim por diante
    
    **Configuração HTTP:**
    - Method: POST
    - Headers: Content-Type: application/octet-stream
    - Body: PDF binário ou Base64
    
    Returns:
        session_id: UUID para usar nos próximos requests
        total_pages: Número total de páginas do PDF
        expires_in_seconds: Tempo até expirar (30 min, renovado a cada acesso)
    """
    try:
        # Lê o corpo da requisição
        raw_body = await request.body()
        
        if not raw_body:
            raise HTTPException(
                status_code=400,
                detail="Nenhum arquivo recebido. Envie o PDF no body da requisição."
            )
        
        # Detecta formato: raw binary ou base64
        if raw_body[:4] == b'%PDF':
            pdf_bytes = raw_body
            logger.info(f"Upload: PDF recebido como raw binary ({len(pdf_bytes)} bytes)")
        elif raw_body[:6] == b'JVBERi':
            try:
                pdf_bytes = base64.b64decode(raw_body)
                logger.info(f"Upload: PDF recebido como Base64, decodificado ({len(pdf_bytes)} bytes)")
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
        
        # Valida PDF
        if not pdf_bytes[:4] == b'%PDF':
            raise HTTPException(
                status_code=400,
                detail="Após decodificação, o arquivo não é um PDF válido."
            )
        
        # Obtém total de páginas
        total_pages = PdfConverter.get_page_count(pdf_bytes)
        
        # Armazena no cache
        try:
            session_id = pdf_cache.store(pdf_bytes, total_pages)
        except ValueError as e:
            raise HTTPException(status_code=413, detail=str(e))
        
        return UploadResponse(
            session_id=session_id,
            total_pages=total_pages,
            expires_in_seconds=pdf_cache.DEFAULT_TTL_SECONDS
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao fazer upload do PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PageResponse(BaseModel):
    """Resposta da extração de uma página."""
    page: int
    total_pages: int
    image_base64: str


@router.get("/page/{session_id}/{page}", dependencies=[Depends(verify_api_key)], response_model=PageResponse)
async def get_page_from_cache(
    session_id: str,
    page: int,
    dpi: int = Query(150, description="Resolução de renderização (DPI)"),
    format: str = Query("png", description="Formato: 'png' ou 'jpeg'"),
    quality: int = Query(85, description="Qualidade JPEG 1-100 (ignorado para PNG)"),
    grayscale: bool = Query(False, description="Converter para escala de cinza"),
    max_dimension: int = Query(0, description="Dimensão máxima em pixels (0 = sem limite). Ex: 4096 para IA.")
):
    """
    📄 **EXTRAI PÁGINA** - Retorna uma página específica do PDF em cache.
    
    Use o session_id recebido no `/pdf/upload` para extrair páginas
    individuais sem reenviar o PDF.
    
    **Exemplo:**
    ```
    GET /pdf/page/abc123-uuid/1?dpi=150
    GET /pdf/page/abc123-uuid/1?dpi=300&format=jpeg&quality=85&max_dimension=4096
    ```
    
    Args:
        session_id: UUID da sessão (de /pdf/upload)
        page: Número da página (1-indexed)
        dpi: Resolução de renderização (default: 150)
        format: Formato: "png" ou "jpeg" (default: "png")
        quality: Qualidade JPEG 1-100 (default: 85)
        grayscale: Escala de cinza (default: false)
        max_dimension: Dimensão máxima em pixels (default: 0 = sem limite)
    
    Returns:
        page: Número da página
        total_pages: Total de páginas no PDF
        image_base64: Imagem em base64 com prefixo data URI
    """
    try:
        logger.info(f"[DEBUG] get_page_from_cache: session={session_id}, page={page}, dpi={dpi}, format={format}, max_dim={max_dimension}")
        
        entry = pdf_cache.get(session_id)
        
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Sessão '{session_id}' não encontrada ou expirada."
            )
        
        if page < 1 or page > entry.total_pages:
            raise HTTPException(
                status_code=400,
                detail=f"Página {page} inválida. O PDF tem {entry.total_pages} páginas."
            )
        
        img_format = format.lower()
        if img_format not in ("png", "jpeg"):
            raise HTTPException(status_code=400, detail="Formato inválido. Use 'png' ou 'jpeg'.")
        
        images = PdfConverter.pages_to_images(
            entry.pdf_bytes,
            pages=[page],
            dpi=dpi,
            img_format=img_format,
            quality=quality,
            grayscale=grayscale,
            max_dimension=max_dimension
        )
        
        if not images:
            logger.error(f"[DEBUG] Nenhuma imagem retornada para page={page}")
            raise HTTPException(
                status_code=500,
                detail=f"Falha ao processar página {page}"
            )
        
        img = images[0]
        mime_type = "image/jpeg" if img_format == "jpeg" else "image/png"
        logger.info(f"[DEBUG] Imagem extraída: page_number={img.page_number}, dimensions={img.width}x{img.height}, format={img_format}")
        logger.info(f"Página {page}/{entry.total_pages} extraída (session={session_id[:8]}...)")
        
        return PageResponse(
            page=page,
            total_pages=entry.total_pages,
            image_base64=f"data:{mime_type};base64,{img.image_base64}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao extrair página do cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/page-sections/{session_id}/{page}", dependencies=[Depends(verify_api_key)])
async def get_page_sections(
    session_id: str,
    page: int,
    rows: int = 2,
    cols: int = 2,
    dpi: int = 200
):
    """
    Divide uma página do PDF em seções (grid) com alta resolução.
    
    Útil para enviar para IA quando a página inteira fica grande demais.
    Por padrão divide em 4 seções (2x2).
    
    Args:
        session_id: ID da sessão do cache
        page: Número da página (1-indexed)
        rows: Linhas do grid (default: 2)
        cols: Colunas do grid (default: 2)
        dpi: Resolução (default: 200)
    
    Returns:
        page: Número da página original
        total_pages: Total de páginas no PDF
        sections: Lista de seções com image_base64
        grid: Configuração do grid usada
    """
    try:
        entry = pdf_cache.get(session_id)
        
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Sessão '{session_id}' não encontrada ou expirada."
            )
        
        if page < 1 or page > entry.total_pages:
            raise HTTPException(
                status_code=400,
                detail=f"Página {page} inválida. O PDF tem {entry.total_pages} páginas."
            )
        
        # Limita grid para evitar abuso
        rows = min(max(rows, 1), 4)
        cols = min(max(cols, 1), 4)
        
        sections = PdfConverter.page_to_sections(
            entry.pdf_bytes,
            page=page,
            rows=rows,
            cols=cols,
            dpi=dpi
        )
        
        logger.info(
            f"Página {page}/{entry.total_pages} dividida em {rows}x{cols} seções "
            f"(session={session_id[:8]}...)"
        )
        
        return {
            "page": page,
            "total_pages": entry.total_pages,
            "grid": {"rows": rows, "cols": cols, "total_sections": rows * cols},
            "sections": [
                {
                    "section": s.page_number,
                    "image_base64": f"data:image/png;base64,{s.image_base64}",
                    "width": s.width,
                    "height": s.height
                }
                for s in sections
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao dividir página em seções: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats", dependencies=[Depends(verify_api_key)])
async def get_cache_stats():
    """
    📊 **ESTATÍSTICAS** - Retorna informações sobre o cache de PDFs.
    
    Returns:
        active_sessions: Número de sessões ativas
        total_size_mb: Tamanho total em MB
        max_size_mb: Limite máximo em MB
        ttl_seconds: Tempo de vida das sessões
    """
    return pdf_cache.get_stats()


@router.delete("/cache/{session_id}", dependencies=[Depends(verify_api_key)])
async def delete_cache_session(session_id: str):
    """
    🗑️ **LIMPAR SESSÃO** - Remove uma sessão do cache manualmente.
    
    Útil para liberar memória após processar todas as páginas necessárias.
    
    Args:
        session_id: UUID da sessão a remover
    
    Returns:
        success: True se removido
        message: Mensagem de confirmação
    """
    deleted = pdf_cache.delete(session_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Sessão '{session_id}' não encontrada."
        )
    
    return {
        "success": True,
        "message": f"Sessão {session_id} removida do cache."
    }


# ============================================================================
# PAGE CLASSIFICATION ENDPOINTS - Identificar P&IDs vs Layouts
# ============================================================================

class ClassifyPagesResponse(BaseModel):
    """Resposta da classificação de páginas."""
    total_pages: int
    index_page: int | None
    pid_pages: list[int]
    layout_pages: list[int]
    unknown_pages: list[int]
    method_used: str
    processing_time_ms: float


@router.post("/classify-pages", dependencies=[Depends(verify_api_key)], response_model=ClassifyPagesResponse)
async def classify_pages(request: Request):
    """
    🔍 **CLASSIFICAR PÁGINAS** - Identifica quais páginas são P&IDs vs Layouts.
    
    Usa 3 níveis de classificação:
    1. **OCR no Índice**: Procura "Drawing Index" e lê nomes dos desenhos
    2. **OCR no Título**: Lê título/rodapé de cada página
    3. **Análise Visual**: Detecta páginas coloridas (Layouts) vs P&B (P&IDs)
    
    **Uso no Power Automate:**
    1. Envia PDF → Recebe lista de páginas P&ID
    2. Loop apenas nas páginas retornadas em `pid_pages`
    3. Envia cada página para análise com IA
    
    **Configuração HTTP:**
    - Method: POST
    - Headers: Content-Type: application/octet-stream
    - Body: PDF binário ou Base64
    
    Returns:
        total_pages: Número total de páginas
        index_page: Página do índice (se encontrado)
        pid_pages: Lista de páginas P&ID (1-indexed)
        layout_pages: Lista de páginas Layout (1-indexed)
        unknown_pages: Páginas não classificadas
        method_used: "index", "title" ou "visual"
        processing_time_ms: Tempo de processamento
    """
    from src.infrastructure.pdf_page_classifier import PdfPageClassifier
    
    try:
        # Lê o corpo da requisição
        raw_body = await request.body()
        
        if not raw_body:
            raise HTTPException(
                status_code=400,
                detail="Nenhum arquivo recebido. Envie o PDF no body da requisição."
            )
        
        # Detecta formato: raw binary ou base64
        if raw_body[:4] == b'%PDF':
            pdf_bytes = raw_body
            logger.info(f"Classificação: PDF recebido como raw binary ({len(pdf_bytes)} bytes)")
        elif raw_body[:6] == b'JVBERi':
            try:
                pdf_bytes = base64.b64decode(raw_body)
                logger.info(f"Classificação: PDF recebido como Base64 ({len(pdf_bytes)} bytes)")
            except Exception as decode_error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Falha ao decodificar Base64: {str(decode_error)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="O arquivo recebido não é um PDF válido."
            )
        
        # Classifica as páginas
        result = PdfPageClassifier.classify_pdf(pdf_bytes)
        
        logger.info(
            f"Classificação concluída: {len(result.pid_pages)} P&IDs, "
            f"{len(result.layout_pages)} Layouts, método={result.method_used}, "
            f"tempo={result.processing_time_ms:.0f}ms"
        )
        
        return ClassifyPagesResponse(
            total_pages=result.total_pages,
            index_page=result.index_page,
            pid_pages=result.pid_pages,
            layout_pages=result.layout_pages,
            unknown_pages=result.unknown_pages,
            method_used=result.method_used,
            processing_time_ms=result.processing_time_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao classificar páginas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-and-classify", dependencies=[Depends(verify_api_key)])
async def upload_and_classify(request: Request):
    """
    📦🔍 **UPLOAD + CLASSIFICAR** - Armazena PDF no cache e classifica páginas.
    
    Combina /pdf/upload com /pdf/classify-pages em uma única chamada.
    Retorna session_id + lista de páginas P&ID para processar.
    
    **Fluxo otimizado no Power Automate:**
    1. `POST /pdf/upload-and-classify` → session_id + pid_pages
    2. Loop em pid_pages: `GET /pdf/page/{session_id}/{page}`
    3. Envia cada imagem para IA
    
    Returns:
        session_id: UUID para extrair páginas
        total_pages: Total de páginas no PDF
        pid_pages: Lista de páginas P&ID
        layout_pages: Lista de páginas Layout
        method_used: Método de classificação usado
        expires_in_seconds: Tempo até expirar
    """
    from src.infrastructure.pdf_page_classifier import PdfPageClassifier
    
    try:
        # Lê o corpo da requisição
        raw_body = await request.body()
        
        if not raw_body:
            raise HTTPException(
                status_code=400,
                detail="Nenhum arquivo recebido."
            )
        
        # Detecta formato
        if raw_body[:4] == b'%PDF':
            pdf_bytes = raw_body
        elif raw_body[:6] == b'JVBERi':
            pdf_bytes = base64.b64decode(raw_body)
        else:
            raise HTTPException(
                status_code=400,
                detail="O arquivo recebido não é um PDF válido."
            )
        
        # Obtém total de páginas
        total_pages = PdfConverter.get_page_count(pdf_bytes)
        
        # Armazena no cache
        try:
            session_id = pdf_cache.store(pdf_bytes, total_pages)
        except ValueError as e:
            raise HTTPException(status_code=413, detail=str(e))
        
        # Classifica as páginas
        result = PdfPageClassifier.classify_pdf(pdf_bytes)
        
        logger.info(
            f"Upload+Classificação: session={session_id[:8]}..., "
            f"{len(result.pid_pages)} P&IDs encontrados"
        )
        
        return {
            "session_id": session_id,
            "total_pages": result.total_pages,
            "index_page": result.index_page,
            "pid_pages": result.pid_pages,
            "layout_pages": result.layout_pages,
            "unknown_pages": result.unknown_pages,
            "method_used": result.method_used,
            "processing_time_ms": result.processing_time_ms,
            "expires_in_seconds": pdf_cache.DEFAULT_TTL_SECONDS
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no upload+classificação: {e}")
        raise HTTPException(status_code=500, detail=str(e))
