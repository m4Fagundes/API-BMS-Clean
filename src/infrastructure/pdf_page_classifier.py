"""
Classificador de páginas PDF para identificar P&IDs vs Layouts.

Usa 3 níveis de classificação:
1. OCR no índice (Drawing Index)
2. OCR no título/rodapé da página
3. Análise visual (cores da região central)
"""
import re
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger("BMS_API")


class PageType(Enum):
    """Tipos de página identificados."""
    PID = "pid"          # Esquema P&ID - deve ser analisado
    LAYOUT = "layout"    # Planta/Layout - ignorar
    INDEX = "index"      # Índice de desenhos
    LEGEND = "legend"    # Legenda/símbolos
    UNKNOWN = "unknown"  # Não classificado


@dataclass
class ClassificationResult:
    """Resultado da classificação de um PDF."""
    total_pages: int
    index_page: Optional[int]
    pid_pages: list[int]
    layout_pages: list[int]
    unknown_pages: list[int]
    method_used: str  # "index", "title", "visual"
    processing_time_ms: float


@dataclass
class DrawingEntry:
    """Entrada do índice de desenhos."""
    number: str      # Ex: "M602"
    name: str        # Ex: "MECHANICAL PIPEWORK SCHEMATICS"
    page_type: PageType


class PdfPageClassifier:
    """
    Classificador de páginas PDF.
    
    Identifica quais páginas são P&IDs (esquemas) e quais são
    Layouts (plantas) para otimizar processamento.
    """
    
    # Palavras-chave para classificação
    PID_KEYWORDS = [
        "SCHEMATIC", "SCHEMATICS", "P&ID", "P&I", 
        "PIPING AND INSTRUMENTATION", "FLOW DIAGRAM"
    ]
    
    LAYOUT_KEYWORDS = [
        "LAYOUT", "PLAN", "ELEVATION", "SECTION", "DETAIL",
        "GA", "GENERAL ARRANGEMENT", "PLANTROOM"
    ]
    
    INDEX_KEYWORDS = [
        "DRAWING INDEX", "INDEX", "TABLE OF CONTENTS", 
        "CONTENTS", "DRAWING LIST"
    ]
    
    LEGEND_KEYWORDS = [
        "LEGEND", "SYMBOL", "STANDARD DETAIL", "KEY"
    ]
    
    # DPI baixo para classificação rápida
    CLASSIFICATION_DPI = 72
    
    @classmethod
    def classify_pdf(cls, pdf_bytes: bytes) -> ClassificationResult:
        """
        Classifica todas as páginas de um PDF.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            
        Returns:
            ClassificationResult com páginas classificadas.
        """
        import time
        start_time = time.time()
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        try:
            # Nível 1: Tentar encontrar e parsear índice
            index_page, drawing_entries = cls._find_and_parse_index(doc)
            
            if index_page is not None and drawing_entries:
                # Classificar baseado no índice
                result = cls._classify_from_index(
                    total_pages, index_page, drawing_entries
                )
                result.method_used = "index"
            else:
                # Nível 2: OCR em cada página (título/rodapé)
                result = cls._classify_by_page_titles(doc)
                
                if result.pid_pages or result.layout_pages:
                    result.method_used = "title"
                else:
                    # Nível 3: Análise visual (fallback)
                    result = cls._classify_by_visual(doc)
                    result.method_used = "visual"
            
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result
            
        finally:
            doc.close()
    
    @classmethod
    def _find_and_parse_index(
        cls, 
        doc: fitz.Document
    ) -> tuple[Optional[int], list[DrawingEntry]]:
        """
        Procura página de índice e extrai lista de desenhos.
        
        Returns:
            Tupla (página do índice, lista de entries).
        """
        # Procura índice nas primeiras 5 páginas
        for page_num in range(min(5, len(doc))):
            page = doc[page_num]
            text = page.get_text().upper()
            
            # Verifica se é página de índice
            if any(kw in text for kw in cls.INDEX_KEYWORDS):
                entries = cls._parse_index_page(text)
                if entries:
                    logger.info(
                        f"Índice encontrado na página {page_num + 1} "
                        f"com {len(entries)} desenhos"
                    )
                    return page_num + 1, entries
        
        return None, []
    
    @classmethod
    def _parse_index_page(cls, text: str) -> list[DrawingEntry]:
        """
        Extrai lista de desenhos do texto do índice.
        """
        entries = []
        lines = text.split('\n')
        
        # Padrão: código (M100, H101, etc) seguido de descrição
        pattern = re.compile(r'\b([A-Z]\d{2,4})\b\s+(.+?)(?=\s+[A-Z]\d{2,4}|\s*$)')
        
        for line in lines:
            # Procura padrões como "M602 MECHANICAL PIPEWORK SCHEMATICS"
            matches = pattern.findall(line)
            for number, name in matches:
                name = name.strip()
                if len(name) > 5:  # Ignora nomes muito curtos
                    page_type = cls._classify_by_name(name)
                    entries.append(DrawingEntry(
                        number=number,
                        name=name,
                        page_type=page_type
                    ))
        
        return entries
    
    @classmethod
    def _classify_by_name(cls, name: str) -> PageType:
        """Classifica um desenho pelo nome."""
        name_upper = name.upper()
        
        # P&ID tem prioridade se contém SCHEMATIC
        if any(kw in name_upper for kw in cls.PID_KEYWORDS):
            return PageType.PID
        
        # Legenda
        if any(kw in name_upper for kw in cls.LEGEND_KEYWORDS):
            return PageType.LEGEND
        
        # Layout
        if any(kw in name_upper for kw in cls.LAYOUT_KEYWORDS):
            return PageType.LAYOUT
        
        return PageType.UNKNOWN
    
    @classmethod
    def _classify_from_index(
        cls,
        total_pages: int,
        index_page: int,
        entries: list[DrawingEntry]
    ) -> ClassificationResult:
        """
        Cria resultado baseado nas entradas do índice.
        
        Assume que as páginas seguem a ordem do índice.
        """
        pid_pages = []
        layout_pages = []
        unknown_pages = []
        
        # Página 1 = índice, desenhos começam na página 2
        # Mapeia entries para páginas
        start_page = index_page + 1
        
        for i, entry in enumerate(entries):
            page_num = start_page + i
            if page_num > total_pages:
                break
                
            if entry.page_type == PageType.PID:
                pid_pages.append(page_num)
            elif entry.page_type == PageType.LAYOUT:
                layout_pages.append(page_num)
            elif entry.page_type != PageType.LEGEND:
                unknown_pages.append(page_num)
        
        return ClassificationResult(
            total_pages=total_pages,
            index_page=index_page,
            pid_pages=pid_pages,
            layout_pages=layout_pages,
            unknown_pages=unknown_pages,
            method_used="index",
            processing_time_ms=0
        )
    
    @classmethod
    def _classify_by_page_titles(cls, doc: fitz.Document) -> ClassificationResult:
        """
        Classifica cada página pelo texto do título/rodapé.
        """
        pid_pages = []
        layout_pages = []
        unknown_pages = []
        index_page = None
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().upper()
            
            # Verifica tipo
            is_pid = any(kw in text for kw in cls.PID_KEYWORDS)
            is_layout = any(kw in text for kw in cls.LAYOUT_KEYWORDS)
            is_index = any(kw in text for kw in cls.INDEX_KEYWORDS)
            
            page_number = page_num + 1
            
            if is_index:
                index_page = page_number
            elif is_pid and not is_layout:
                pid_pages.append(page_number)
            elif is_layout and not is_pid:
                layout_pages.append(page_number)
            elif is_pid and is_layout:
                # Tem ambos - SCHEMATIC tem prioridade
                pid_pages.append(page_number)
            else:
                unknown_pages.append(page_number)
        
        return ClassificationResult(
            total_pages=len(doc),
            index_page=index_page,
            pid_pages=pid_pages,
            layout_pages=layout_pages,
            unknown_pages=unknown_pages,
            method_used="title",
            processing_time_ms=0
        )
    
    @classmethod
    def _classify_by_visual(cls, doc: fitz.Document) -> ClassificationResult:
        """
        Classifica páginas por análise visual (cores).
        
        P&IDs são predominantemente preto/branco.
        Layouts são muito coloridos.
        """
        pid_pages = []
        layout_pages = []
        unknown_pages = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Renderiza em baixa resolução
            zoom = cls.CLASSIFICATION_DPI / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            
            # Analisa cores
            samples = pix.samples
            is_colorful = cls._analyze_colors(samples, pix.width, pix.height, pix.n)
            
            page_number = page_num + 1
            
            if is_colorful:
                layout_pages.append(page_number)
            else:
                # Assume P&ID se não é colorido
                # (pode ter falsos positivos, mas é o fallback)
                unknown_pages.append(page_number)
        
        return ClassificationResult(
            total_pages=len(doc),
            index_page=None,
            pid_pages=pid_pages,
            layout_pages=layout_pages,
            unknown_pages=unknown_pages,
            method_used="visual",
            processing_time_ms=0
        )
    
    @classmethod
    def _analyze_colors(
        cls, 
        samples: bytes, 
        width: int, 
        height: int, 
        n: int
    ) -> bool:
        """
        Analisa se imagem é predominantemente colorida.
        
        Returns:
            True se imagem é colorida (Layout), False se monocromática (P&ID).
        """
        # Amostra apenas 10% dos pixels para velocidade
        total_pixels = width * height
        sample_step = max(1, total_pixels // 1000)
        
        colorful_count = 0
        checked_count = 0
        
        for i in range(0, len(samples), n * sample_step):
            if i + 2 >= len(samples):
                break
                
            r = samples[i]
            g = samples[i + 1]
            b = samples[i + 2]
            
            # Calcula saturação aproximada
            max_val = max(r, g, b)
            min_val = min(r, g, b)
            diff = max_val - min_val
            
            # Considera "colorido" se tem boa saturação
            # e não é muito escuro nem muito claro
            if diff > 50 and 30 < max_val < 230:
                colorful_count += 1
            
            checked_count += 1
        
        if checked_count == 0:
            return False
            
        color_ratio = colorful_count / checked_count
        
        # Se mais de 15% dos pixels são coloridos, é Layout
        return color_ratio > 0.15
