"""
Modelos de domínio da aplicação (DTOs/Schemas).
Utiliza Pydantic para validação e serialização.
"""
from pydantic import BaseModel
from typing import List, Optional


# ==========================================
#           MODELOS PDF
# ==========================================

class PdfRequest(BaseModel):
    """Request para extração de texto de PDF."""
    arquivo_base64: str


class SectionRequest(BaseModel):
    """Request para extração de seção específica do PDF."""
    arquivo_base64: str
    inicio_texto: str
    fim_texto: Optional[str] = None


# ==========================================
#           MODELOS EXCEL - PROJECT REPORT
# ==========================================

class PointData(BaseModel):
    """Dados de um ponto de monitoramento."""
    Descriptor: str
    Signal_Type: str
    Sensor_Hardware: Optional[str] = ""
    Notes: Optional[str] = ""


class EquipmentData(BaseModel):
    """Dados de um equipamento com seus pontos."""
    Tag: str
    Description: Optional[str] = ""
    Status: Optional[str] = ""
    Switchboard_Ref: Optional[str] = ""
    Location: Optional[str] = ""
    Points: List[PointData] = []


class SystemData(BaseModel):
    """Dados de um sistema contendo equipamentos."""
    System_Name: str
    Equipment: List[EquipmentData] = []


class ProjectReportRequest(BaseModel):
    """Request para geração de relatório de projeto."""
    Focus_Category: Optional[str] = "General"
    Systems: List[SystemData] = []


# ==========================================
#           MODELOS BMS POINTS
# ==========================================

class BMSPointData(BaseModel):
    """Dados de um ponto BMS individual."""
    AssetTag: str
    PointName: str
    PointType: str
    Logic: str
    IsIntegration: bool = False


class BMSPointsRequest(BaseModel):
    """Request para geração de lista de pontos BMS."""
    Points: List[BMSPointData]
    Report_Title: Optional[str] = "BMS Points List"


# ==========================================
#           MODELOS PDF -> IMAGEM
# ==========================================

class SectionToImagesRequest(BaseModel):
    """Request para converter seção do PDF em imagens."""
    arquivo_base64: str
    inicio_texto: str
    fim_texto: Optional[str] = None
    dpi: Optional[int] = 150


class PagesToImagesRequest(BaseModel):
    """Request para converter páginas específicas em imagens."""
    arquivo_base64: str
    pages: Optional[List[int]] = None  # None = todas as páginas
    dpi: Optional[int] = 150


class PageImageResponse(BaseModel):
    """Resposta com uma imagem de página."""
    page_number: int
    image_base64: str
    width: int
    height: int


class ImagesToImagesResponse(BaseModel):
    """Resposta com múltiplas imagens."""
    total_pages: int
    images: List[PageImageResponse]
