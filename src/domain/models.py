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


# ==========================================
#           MODELOS P&ID ANALYSIS EXPORT
# ==========================================

class PIDSummary(BaseModel):
    """Resumo de contagem de pontos."""
    total_devices: int = 0
    total_points: int = 0
    by_type: Optional[dict] = None


class PIDComponent(BaseModel):
    """Um dispositivo/componente encontrado no P&ID."""
    tag: str
    device_type: str
    points: List[str] = []
    point_count: int = 0
    confidence: Optional[str] = "medium"


class PIDPageResult(BaseModel):
    """Resultado da análise de uma página P&ID."""
    is_relevant_pid: bool
    reasoning: Optional[str] = ""
    drawing_title: Optional[str] = ""
    drawing_number: Optional[str] = ""
    components: Optional[List[PIDComponent]] = []
    summary: Optional[PIDSummary] = None


class PIDAnalysisExportRequest(BaseModel):
    """Request para exportar resultados de análise P&ID para Excel."""
    project_name: Optional[str] = "P&ID Analysis"
    pages: List[PIDPageResult]


# ==========================================
#   MODELOS POINTS LIST (genérico)
# ==========================================

class PointsListPoint(BaseModel):
    """Um ponto individual com descrição, tipos de sinal, notas e quantidade."""
    point_description: str
    types: List[str] = []  # e.g. ["AI", "HLI"], ["DO"], ["Pulse"]
    field_device_or_notes: Optional[str] = ""
    qty: Optional[int] = 1


class PointsListSystem(BaseModel):
    """Um sistema/equipamento com seus pontos de monitoramento."""
    system_name: str
    equipment_tag: Optional[str] = ""
    location: Optional[str] = ""
    description: Optional[str] = ""
    points: List[PointsListPoint] = []


class PointsListRequest(BaseModel):
    """Request para geração de Points List Excel (formato setpoint padrão)."""
    project_name: Optional[str] = "Unknown"
    systems: List[PointsListSystem] = []
