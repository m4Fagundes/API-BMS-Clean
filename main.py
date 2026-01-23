"""
BMS API - PDF & Excel Generator

Ponto de entrada da aplicação. Orquestra os módulos e inicializa o servidor FastAPI.

Arquitetura:
    src/
    ├── core/           # Configurações e segurança
    ├── domain/         # Modelos de dados (DTOs)
    ├── application/    # Serviços e lógica de negócio
    ├── infrastructure/ # Implementações externas (PDF extractor)
    └── presentation/   # Rotas da API (Controllers)
"""
import logging
import uvicorn

from fastapi import FastAPI

from src.core.config import settings
from src.presentation import pdf_router, excel_router


# Configuração de logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("BMS_API")


def create_app() -> FastAPI:
    """
    Factory function para criar a aplicação FastAPI.
    
    Returns:
        Instância configurada do FastAPI.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API para extração de texto de PDFs e geração de relatórios Excel/PDF estruturados."
    )
    
    # Registra os routers
    _register_routers(app)
    
    # Registra rotas legadas (retrocompatibilidade)
    _register_legacy_routes(app)
    
    logger.info(f"Aplicação {settings.app_name} v{settings.app_version} inicializada.")
    
    return app


def _register_routers(app: FastAPI):
    """Registra os routers da aplicação."""
    app.include_router(pdf_router)
    app.include_router(excel_router)


def _register_legacy_routes(app: FastAPI):
    """
    Registra rotas legadas para manter retrocompatibilidade.
    
    Rotas antigas:
        - POST /extract-toc -> POST /pdf/extract-toc
        - POST /extract-section -> POST /pdf/extract-section
        - POST /generate-pdf -> POST /reports/pdf
        - POST /generate-excel -> POST /reports/excel
        - POST /generate-bms-points-excel -> POST /reports/bms-points-excel
    """
    import base64
    from fastapi import Depends, HTTPException
    from fastapi.responses import StreamingResponse
    
    from src.core.security import verify_api_key
    from src.domain.models import PdfRequest, SectionRequest, ProjectReportRequest, BMSPointsRequest
    from src.infrastructure.pdf_extractor import PdfExtractor
    from src.application.pdf_service import PdfReportService
    from src.application.excel_service import ExcelReportService
    from src.application.bms_excel_service import BMSExcelService
    
    def _sanitize_filename(name: str) -> str:
        return "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
    
    @app.post("/extract-toc", dependencies=[Depends(verify_api_key)], tags=["Legacy"])
    async def legacy_extract_toc(req: PdfRequest):
        try:
            pdf_bytes = base64.b64decode(req.arquivo_base64)
            text = PdfExtractor.extract_text(pdf_bytes, limit=20, maintain_layout=False)
            return {"text": text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/extract-section", dependencies=[Depends(verify_api_key)], tags=["Legacy"])
    async def legacy_extract_section(req: SectionRequest):
        try:
            pdf_bytes = base64.b64decode(req.arquivo_base64)
            section_text = PdfExtractor.extract_section(pdf_bytes, req.inicio_texto, req.fim_texto)
            return {"section_text": section_text}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/generate-pdf", dependencies=[Depends(verify_api_key)], tags=["Legacy"])
    async def legacy_generate_pdf(data: ProjectReportRequest):
        try:
            service = PdfReportService()
            pdf_file = service.generate(data)
            filename = f"{_sanitize_filename(data.Focus_Category or 'Report')}.pdf"
            return StreamingResponse(
                pdf_file,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/generate-excel", dependencies=[Depends(verify_api_key)], tags=["Legacy"])
    async def legacy_generate_excel(data: ProjectReportRequest):
        try:
            service = ExcelReportService()
            excel_file = service.generate(data)
            filename = f"{_sanitize_filename(data.Focus_Category or 'Report')}.xlsx"
            return StreamingResponse(
                excel_file,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/generate-bms-points-excel", dependencies=[Depends(verify_api_key)], tags=["Legacy"])
    async def legacy_generate_bms_points_excel(data: BMSPointsRequest):
        try:
            service = BMSExcelService()
            excel_file = service.generate(data)
            filename = f"{_sanitize_filename(data.Report_Title or 'BMS_Points')}.xlsx"
            return StreamingResponse(
                excel_file,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# Cria a instância da aplicação
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )