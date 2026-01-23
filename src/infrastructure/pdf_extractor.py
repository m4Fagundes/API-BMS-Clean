"""
Infraestrutura para extração de texto de PDFs.
"""
import io
import pdfplumber
from typing import Optional


class PdfExtractor:
    """Responsável pela extração de texto de arquivos PDF."""
    
    @staticmethod
    def extract_text(
        pdf_bytes: bytes, 
        limit: Optional[int] = None, 
        maintain_layout: bool = True
    ) -> str:
        """
        Extrai texto de um arquivo PDF.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            limit: Número máximo de páginas a extrair (None = todas).
            maintain_layout: Se deve manter o layout original do texto.
            
        Returns:
            Texto extraído do PDF.
        """
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = pdf.pages[:limit] if limit else pdf.pages
            for page in pages:
                extracted = page.extract_text(layout=maintain_layout)
                if extracted:
                    text += extracted + "\n"
        return text
    
    @staticmethod
    def extract_section(
        pdf_bytes: bytes, 
        start_marker: str, 
        end_marker: Optional[str] = None
    ) -> str:
        """
        Extrai uma seção específica do PDF entre marcadores.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            start_marker: Texto que marca o início da seção.
            end_marker: Texto que marca o fim da seção (opcional).
            
        Returns:
            Texto da seção extraída.
            
        Raises:
            ValueError: Se o marcador de início não for encontrado.
        """
        full_text = PdfExtractor.extract_text(pdf_bytes, maintain_layout=True)
        
        idx_start = full_text.find(start_marker)
        if idx_start == -1:
            raise ValueError("Marcador de início não encontrado no documento.")
        
        final_text = full_text[idx_start:]
        
        if end_marker:
            idx_end = full_text.find(end_marker, idx_start)
            if idx_end != -1:
                final_text = full_text[idx_start:idx_end]
        
        return final_text
