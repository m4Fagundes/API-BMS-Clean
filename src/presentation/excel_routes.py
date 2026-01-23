"""
Rotas relacionadas a geração de relatórios Excel e PDF.
"""
import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from src.core.security import verify_api_key
from src.domain.models import ProjectReportRequest, BMSPointsRequest
from src.application.pdf_service import PdfReportService
from src.application.excel_service import ExcelReportService
from src.application.bms_excel_service import BMSExcelService


logger = logging.getLogger("BMS_API")
router = APIRouter(prefix="/reports", tags=["Report Generation"])


def _sanitize_filename(name: str) -> str:
    """Sanitiza o nome do arquivo removendo caracteres inválidos."""
    return "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()


@router.post("/pdf", dependencies=[Depends(verify_api_key)])
async def generate_pdf(data: ProjectReportRequest):
    """
    Gera um relatório PDF com a lista de pontos do projeto.
    """
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
        logger.error(f"Erro ao gerar PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/excel", dependencies=[Depends(verify_api_key)])
async def generate_excel(data: ProjectReportRequest):
    """
    Gera um relatório Excel estruturado com células mescladas.
    """
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
        logger.error(f"Erro ao gerar Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bms-points-excel", dependencies=[Depends(verify_api_key)])
async def generate_bms_points_excel(data: BMSPointsRequest):
    """
    Gera um Excel estruturado a partir de lista de pontos BMS.
    
    Agrupa pontos por AssetTag e organiza em tabela com células mescladas.
    Aplica cores diferentes para cada tipo de ponto (AI, AO, DI, DO).
    """
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
        logger.error(f"Erro ao gerar BMS Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
