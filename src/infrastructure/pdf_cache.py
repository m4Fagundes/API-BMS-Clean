"""
Cache em memória para sessões de PDF.

Permite upload único do PDF e extração de páginas sob demanda
sem reenviar o arquivo a cada requisição.
"""
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("BMS_API")


@dataclass
class CacheEntry:
    """Entrada de cache para um PDF."""
    pdf_bytes: bytes
    total_pages: int
    created_at: float
    last_accessed: float
    
    @property
    def size_bytes(self) -> int:
        return len(self.pdf_bytes)


class PdfCache:
    """
    Cache em memória para PDFs com TTL e limite de memória.
    
    Características:
    - TTL de 30 minutos por sessão (renovado a cada acesso)
    - Limite máximo de 500MB em cache
    - Limpeza automática de sessões expiradas
    - Thread-safe
    """
    
    DEFAULT_TTL_SECONDS = 30 * 60  # 30 minutos
    MAX_CACHE_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
    CLEANUP_INTERVAL_SECONDS = 60  # Limpeza a cada 60 segundos
    
    _instance: Optional["PdfCache"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "PdfCache":
        """Singleton pattern para garantir uma única instância do cache."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._cache: dict[str, CacheEntry] = {}
        self._cache_lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = True
        
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Inicia thread de limpeza automática."""
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="PdfCacheCleanup"
        )
        self._cleanup_thread.start()
        logger.info("PDF Cache cleanup thread iniciada")
    
    def _cleanup_loop(self):
        """Loop de limpeza automática."""
        while self._running:
            time.sleep(self.CLEANUP_INTERVAL_SECONDS)
            self._cleanup_expired()
    
    def _cleanup_expired(self):
        """Remove sessões expiradas do cache."""
        now = time.time()
        expired_sessions = []
        
        with self._cache_lock:
            for session_id, entry in self._cache.items():
                if now - entry.last_accessed > self.DEFAULT_TTL_SECONDS:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._cache[session_id]
        
        if expired_sessions:
            logger.info(f"Limpeza: {len(expired_sessions)} sessões expiradas removidas")
    
    def _get_total_size(self) -> int:
        """Retorna tamanho total do cache em bytes."""
        return sum(entry.size_bytes for entry in self._cache.values())
    
    def _evict_oldest(self):
        """Remove a sessão menos acessada recentemente."""
        if not self._cache:
            return
        
        oldest_session = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )
        
        entry = self._cache.pop(oldest_session)
        logger.info(f"Cache cheio: sessão {oldest_session} removida ({entry.size_bytes} bytes)")
    
    def store(self, pdf_bytes: bytes, total_pages: int) -> str:
        """
        Armazena um PDF no cache.
        
        Args:
            pdf_bytes: Bytes do PDF
            total_pages: Número total de páginas
            
        Returns:
            session_id: UUID único para esta sessão
            
        Raises:
            ValueError: Se o PDF exceder o limite de memória
        """
        pdf_size = len(pdf_bytes)
        
        # Verifica se o PDF individual excede o limite
        if pdf_size > self.MAX_CACHE_SIZE_BYTES:
            raise ValueError(
                f"PDF muito grande ({pdf_size / 1024 / 1024:.1f}MB). "
                f"Limite máximo: {self.MAX_CACHE_SIZE_BYTES / 1024 / 1024:.0f}MB"
            )
        
        session_id = str(uuid.uuid4())
        now = time.time()
        
        entry = CacheEntry(
            pdf_bytes=pdf_bytes,
            total_pages=total_pages,
            created_at=now,
            last_accessed=now
        )
        
        with self._cache_lock:
            # Libera espaço se necessário
            while self._get_total_size() + pdf_size > self.MAX_CACHE_SIZE_BYTES:
                self._evict_oldest()
            
            self._cache[session_id] = entry
        
        logger.info(
            f"PDF armazenado: session_id={session_id}, "
            f"pages={total_pages}, size={pdf_size / 1024:.1f}KB"
        )
        
        return session_id
    
    def get(self, session_id: str) -> Optional[CacheEntry]:
        """
        Recupera um PDF do cache.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            CacheEntry ou None se não encontrado/expirado
        """
        with self._cache_lock:
            entry = self._cache.get(session_id)
            
            if entry is None:
                return None
            
            # Verifica se expirou
            if time.time() - entry.last_accessed > self.DEFAULT_TTL_SECONDS:
                del self._cache[session_id]
                logger.info(f"Sessão expirada: {session_id}")
                return None
            
            # Atualiza timestamp de acesso
            entry.last_accessed = time.time()
            
            return entry
    
    def delete(self, session_id: str) -> bool:
        """
        Remove uma sessão do cache.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            True se removido, False se não encontrado
        """
        with self._cache_lock:
            if session_id in self._cache:
                del self._cache[session_id]
                logger.info(f"Sessão removida: {session_id}")
                return True
            return False
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do cache."""
        with self._cache_lock:
            return {
                "active_sessions": len(self._cache),
                "total_size_bytes": self._get_total_size(),
                "total_size_mb": round(self._get_total_size() / 1024 / 1024, 2),
                "max_size_mb": self.MAX_CACHE_SIZE_BYTES / 1024 / 1024,
                "ttl_seconds": self.DEFAULT_TTL_SECONDS,
            }


# Singleton instance
pdf_cache = PdfCache()
