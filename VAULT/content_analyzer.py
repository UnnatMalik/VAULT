import os
import re
import logging
import sqlite3
import io
import hashlib
import json
import time
import multiprocessing as mp
import chardet
import fitz  # PyMuPDF for PDF processing
import magic  # For better file type detection
import pytesseract
import numpy as np
import pandas as pd
import spacy
import torch
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Set, Union, BinaryIO, Callable
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ExifTags
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from spacy.language import Language
from spacy.tokens import Doc, Span
from spacy.matcher import PhraseMatcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB
SUPPORTED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
SUPPORTED_DOCUMENT_EXTS = {'.txt', '.md', '.rtf', '.doc', '.docx', '.odt', '.pdf'}
SUPPORTED_SPREADSHEET_EXTS = {'.csv', '.xls', '.xlsx', '.ods'}
SUPPORTED_PRESENTATION_EXTS = {'.ppt', '.pptx', '.odp'}
SUPPORTED_ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.tar', '.gz'}
SUPPORTED_CODE_EXTS = {
    '.py', '.js', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb',
    '.php', '.sh', '.bat', '.ps1', '.html', '.css', '.ts', '.jsx', '.tsx', '.json'
}

class ContentType(Enum):
    # Document Types
    TEXT = "text"
    EMAIL = "email"
    REPORT = "report"
    ARTICLE = "article"
    MANUAL = "manual"
    PAPER = "paper"
    
    # Code Types
    SOURCE_CODE = "source_code"
    CONFIG = "config"
    SCRIPT = "script"
    
    # Data Types
    DATASET = "dataset"
    LOG = "log"
    
    # Media Types
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    
    # Document Formats
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    PDF = "pdf"
    WORD_DOC = "word_document"
    
    # System Files
    ARCHIVE = "archive"
    EXECUTABLE = "executable"
    BINARY = "binary"
    
    # Special Types
    DATABASE = "database"
    VIRTUAL_MACHINE = "virtual_machine"
    CONTAINER = "container"
    
    # Fallback Types
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class TextClassifier:
    """ML-based text classifier for content analysis."""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize the text classifier.
        
        Args:
            model_path: Path to a pre-trained model (optional)
        """
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.model_path = model_path
        self._load_or_initialize_model()
    
    def _load_or_initialize_model(self):
        """Load a pre-trained model or initialize a new one."""
        if self.model_path and os.path.exists(self.model_path):
            try:
                model_data = joblib.load(self.model_path)
                self.model = model_data['model']
                self.vectorizer = model_data['vectorizer']
                self.label_encoder = model_data['label_encoder']
                logger.info(f"Loaded text classification model from {self.model_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to load model from {self.model_path}: {e}")
        
        # Initialize a new model
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words='english',
            max_df=0.8,
            min_df=2
        )
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        # Default label encoder (will be updated during training)
        self.label_encoder = {t.value: i for i, t in enumerate(ContentType)}
    
    def train(self, texts: List[str], labels: List[Union[str, ContentType]], test_size: float = 0.2):
        """Train the text classifier.
        
        Args:
            texts: List of text samples
            labels: List of corresponding labels (as strings or ContentType enums)
            test_size: Fraction of data to use for testing
        """
        try:
            # Convert labels to strings if they're ContentType enums
            label_strings = [label.value if isinstance(label, ContentType) else str(label) 
                           for label in labels]
            
            # Create label encoder
            unique_labels = sorted(set(label_strings))
            self.label_encoder = {label: i for i, label in enumerate(unique_labels)}
            
            # Convert labels to numerical values
            y = np.array([self.label_encoder[label] for label in label_strings])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                texts, y, test_size=test_size, random_state=42, stratify=y
            )
            
            # Create pipeline
            pipeline = Pipeline([
                ('tfidf', self.vectorizer),
                ('clf', self.model)
            ])
            
            # Train
            pipeline.fit(X_train, y_train)
            self.model = pipeline.named_steps['clf']
            self.vectorizer = pipeline.named_steps['tfidf']
            
            # Evaluate
            train_score = pipeline.score(X_train, y_train)
            test_score = pipeline.score(X_test, y_test)
            
            logger.info(f"Text classifier trained. Train score: {train_score:.3f}, Test score: {test_score:.3f}")
            
            # Save model
            if self.model_path:
                self.save_model(self.model_path)
                
            return pipeline
            
        except Exception as e:
            logger.error(f"Error training text classifier: {e}")
            raise
    
    def predict(self, texts: Union[str, List[str]], return_proba: bool = False):
        """Predict content types for the given texts.
        
        Args:
            texts: Text or list of texts to classify
            return_proba: If True, return probability estimates
            
        Returns:
            Predicted labels or (labels, probabilities) if return_proba is True
        """
        if not self.vectorizer or not self.model:
            raise ValueError("Model not trained or loaded")
            
        single_text = isinstance(texts, str)
        if single_text:
            texts = [texts]
        
        try:
            # Transform text to features
            X = self.vectorizer.transform(texts)
            
            # Predict
            if return_proba:
                proba = self.model.predict_proba(X)
                labels = [list(self.label_encoder.keys())[i] for i in self.model.classes_]
                return labels, proba
            else:
                y_pred = self.model.predict(X)
                # Convert numeric predictions back to labels
                reverse_encoder = {v: k for k, v in self.label_encoder.items()}
                predictions = [reverse_encoder.get(pred, 'unknown') for pred in y_pred]
                return predictions[0] if single_text else predictions
                
        except Exception as e:
            logger.error(f"Error predicting text class: {e}")
            return ['unknown'] if single_text else ['unknown'] * len(texts)
    
    def save_model(self, path: str):
        """Save the model to disk."""
        try:
            model_data = {
                'model': self.model,
                'vectorizer': self.vectorizer,
                'label_encoder': self.label_encoder
            }
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            joblib.dump(model_data, path)
            logger.info(f"Saved text classification model to {path}")
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise


class SensitivityLevel(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class SensitivePattern:
    name: str
    pattern: str
    description: str
    sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM
    compiled: re.Pattern = field(init=False)
    
    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)


@dataclass
class ContentAnalysis:
    content_type: ContentType
    mime_type: str
    file_size: int
    sensitive_info: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    language: Optional[str] = None
    is_encrypted: bool = False
    contains_pii: bool = False
    sensitivity_score: float = 0.0
    processing_time: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the analysis result to a dictionary."""
        return {
            'content_type': self.content_type.value,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'sensitive_info': self.sensitive_info,
            'keywords': self.keywords[:20],  # Limit keywords
            'entities': self.entities,
            'checksum': self.checksum,
            'metadata': self.metadata,
            'language': self.language,
            'is_encrypted': self.is_encrypted,
            'contains_pii': self.contains_pii,
            'sensitivity_score': self.sensitivity_score,
            'processing_time': self.processing_time,
            'error': self.error
        }

class ContentAnalyzer:
    """
    Advanced content analyzer that uses NLP and Computer Vision to analyze files,
    detect sensitive information, and extract metadata. Supports a wide range of
    file types and provides detailed analysis results.
    """
    
    def __init__(self, db_path: Optional[str] = None, n_threads: int = -1, 
                 classifier_model_path: Optional[str] = None):
        """
        Initialize the content analyzer.
        
        Args:
            db_path: Path to SQLite database for caching results (optional)
            n_threads: Number of threads to use for parallel processing (-1 for auto)
            classifier_model_path: Path to a pre-trained text classification model (optional)
        """
        self.db_path = db_path
        self.n_threads = mp.cpu_count() if n_threads == -1 else max(1, n_threads)
        self._init_models(classifier_model_path)
        self._init_database()
        self._init_sensitive_patterns()
        # Initialize magic library with cross-platform compatibility
        try:
            # Try Unix/Linux/macOS version first
            self.magic = magic.Magic(mime=True)
            self._magic_type = 'unix'
        except (TypeError, AttributeError):
            # Fallback to Windows version
            try:
                self.magic = magic.Magic()
                self._magic_type = 'windows'
            except Exception:
                # If magic fails entirely, we'll use mimetypes as fallback
                self.magic = None
                self._magic_type = 'fallback'
                import mimetypes
                self.mimetypes = mimetypes
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type using cross-platform compatible method."""
        try:
            if self._magic_type == 'unix':
                # Unix/Linux/macOS version
                return self.magic.from_file(str(file_path), mime=True)
            elif self._magic_type == 'windows':
                # Windows version - different API
                return self.magic.from_file(str(file_path))
            else:
                # Fallback to Python's mimetypes module
                mime_type, _ = self.mimetypes.guess_type(str(file_path))
                return mime_type or 'application/octet-stream'
        except Exception as e:
            # Ultimate fallback
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            return mime_type or 'application/octet-stream'
    
    def _init_models(self, classifier_model_path: Optional[str] = None):
        """Initialize all required ML models and processing pipelines.
        
        Args:
            classifier_model_path: Optional path to a pre-trained text classification model
        """
        try:
            # Load NLP models
            self.nlp = spacy.load(
                "en_core_web_sm", 
                disable=['textcat', 'ner']  # We'll use our own NER
            )
            
            # Initialize text classifier with optional model path
            self.text_classifier = TextClassifier(model_path=classifier_model_path) if classifier_model_path else None
            
            # Add custom pipeline components
            ensure_sensitive_info_component(self.nlp)
            
            # Initialize KeyBERT for keyword extraction
            self.keybert_model = KeyBERT()
            
            # Initialize sentence transformer for embeddings
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Initialize PhraseMatcher for pattern matching
            self.phrase_matcher = PhraseMatcher(self.nlp.vocab)
            
            # Initialize text classifier
            self.text_classifier = TextClassifier(classifier_model_path)
            
            logger.info("ML models and classifiers initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ML models: {e}")
            raise
    
    def _init_sensitive_patterns(self):
        """Initialize patterns for detecting sensitive information."""
        self.sensitive_patterns = [
            # Social Security Numbers (SSN)
            SensitivePattern(
                name="ssn",
                pattern=r'\b(?!000|666|9\d{2})\d{3}[-.]?(?!00)\d{2}[-.]?(?!0000)\d{4}\b',
                description="Social Security Number",
                sensitivity=SensitivityLevel.HIGH
            ),
            # Credit/Debit Card Numbers
            SensitivePattern(
                name="credit_card",
                pattern=r'\b(?:4[0-9]{12}(?:[0-9]{3})?|(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b',
                description="Credit/Debit Card Number",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            # Phone Numbers (US format)
            SensitivePattern(
                name="phone_us",
                pattern=r'\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
                description="US Phone Number",
                sensitivity=SensitivityLevel.MEDIUM
            ),
            # Email Addresses
            SensitivePattern(
                name="email",
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                description="Email Address",
                sensitivity=SensitivityLevel.MEDIUM
            ),
            # IP Addresses
            SensitivePattern(
                name="ip_address",
                pattern=r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
                description="IP Address",
                sensitivity=SensitivityLevel.MEDIUM
            ),
            # API Keys
            SensitivePattern(
                name="api_key",
                pattern=r'\b[A-Za-z0-9]{32,}\b',
                description="Potential API Key",
                sensitivity=SensitivityLevel.HIGH
            ),
            # AWS Access Key ID
            SensitivePattern(
                name="aws_access_key",
                pattern=r'\b(AKIA|ASIA)[A-Z0-9]{16}\b',
                description="AWS Access Key ID",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            # AWS Secret Access Key
            SensitivePattern(
                name="aws_secret_key",
                pattern=r'\b[\w/+]{40}\b',
                description="AWS Secret Access Key",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            # Passwords in config files
            SensitivePattern(
                name="password_in_config",
                pattern=r'(?i)(password|passwd|pwd|secret|api[_-]?key|token)[=: ]+[\"\']?([^\"\'\s]+)[\"\']?',
                description="Password in Config",
                sensitivity=SensitivityLevel.HIGH
            ),
            # Database Connection Strings
            SensitivePattern(
                name="db_connection_string",
                pattern=r'\b(?:jdbc:|postgresql://|mysql://|mongodb://|sqlserver://|oracle:)(?:[^:@/\s]+:([^@/\s]+)@)?[^@/\s]+(?:/\S*)?',
                description="Database Connection String",
                sensitivity=SensitivityLevel.HIGH
            )
        ]
        
        # Add patterns to phrase matcher for NER
        for pattern in self.sensitive_patterns:
            self.phrase_matcher.add(pattern.name, None, self.nlp(pattern.pattern))
        
    def _init_database(self) -> None:
        """Initialize the SQLite database for caching analysis results."""
        if not self.db_path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create content_analysis table with additional fields
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS content_analysis (
                        file_path TEXT PRIMARY KEY,
                        content_type TEXT NOT NULL,
                        mime_type TEXT,
                        file_size INTEGER,
                        sensitive_info TEXT,
                        keywords TEXT,
                        entities TEXT,
                        checksum TEXT,
                        metadata TEXT,
                        language TEXT,
                        is_encrypted BOOLEAN DEFAULT 0,
                        contains_pii BOOLEAN DEFAULT 0,
                        sensitivity_score REAL DEFAULT 0,
                        processing_time REAL,
                        last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        error TEXT
                    )
                ''')
                
                # Create index for faster lookups
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_content_type 
                    ON content_analysis(content_type)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_checksum 
                    ON content_analysis(checksum)
                ''')
                
                # Remove blockchain table if it exists
                cursor.execute("DROP TABLE IF EXISTS blockchain")
                
                # Create analysis history table for tracking changes
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS analysis_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        content_type TEXT,
                        sensitive_info_count INTEGER DEFAULT 0,
                        sensitivity_score REAL DEFAULT 0,
                        processing_time REAL,
                        FOREIGN KEY (file_path) REFERENCES content_analysis(file_path)
                    )
                ''')
                
                conn.commit()
                
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def _detect_content_type(self, file_path: Union[str, Path], 
                           mime_type: Optional[str] = None,
                           text_content: Optional[str] = None) -> ContentType:
        """
        Detect the type of content in the file based on extension, MIME type, and content analysis.
        
        Args:
            file_path: Path to the file
            mime_type: Optional MIME type if already determined
            text_content: Optional text content for ML-based classification
            
        Returns:
            ContentType enum value
        """
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        
        # First try to determine by file extension
        extension_map = {
            # Document formats
            '.pdf': ContentType.PDF,
            '.doc': ContentType.WORD_DOC,
            '.docx': ContentType.WORD_DOC,
            '.odt': ContentType.WORD_DOC,
            '.rtf': ContentType.WORD_DOC,
            '.txt': ContentType.TEXT,
            '.md': ContentType.TEXT,
            '.tex': ContentType.PAPER,
            
            # Spreadsheet formats
            '.xls': ContentType.SPREADSHEET,
            '.xlsx': ContentType.SPREADSHEET,
            '.ods': ContentType.SPREADSHEET,
            '.csv': ContentType.SPREADSHEET,
            
            # Presentation formats
            '.ppt': ContentType.PRESENTATION,
            '.pptx': ContentType.PRESENTATION,
            '.odp': ContentType.PRESENTATION,
            
            # Code formats
            '.py': ContentType.SOURCE_CODE,
            '.js': ContentType.SOURCE_CODE,
            '.java': ContentType.SOURCE_CODE,
            '.c': ContentType.SOURCE_CODE,
            '.cpp': ContentType.SOURCE_CODE,
            '.h': ContentType.SOURCE_CODE,
            '.hpp': ContentType.SOURCE_CODE,
            '.cs': ContentType.SOURCE_CODE,
            '.go': ContentType.SOURCE_CODE,
            '.rs': ContentType.SOURCE_CODE,
            '.rb': ContentType.SOURCE_CODE,
            '.php': ContentType.SOURCE_CODE,
            '.sh': ContentType.SCRIPT,
            '.bat': ContentType.SCRIPT,
            '.ps1': ContentType.SCRIPT,
            '.html': ContentType.SOURCE_CODE,
            '.css': ContentType.SOURCE_CODE,
            '.ts': ContentType.SOURCE_CODE,
            '.jsx': ContentType.SOURCE_CODE,
            '.tsx': ContentType.SOURCE_CODE,
            '.json': ContentType.CONFIG,
            '.yaml': ContentType.CONFIG,
            '.yml': ContentType.CONFIG,
            '.toml': ContentType.CONFIG,
            '.ini': ContentType.CONFIG,
            '.cfg': ContentType.CONFIG,
            
            # Data formats
            '.xml': ContentType.DATASET,
            '.jsonl': ContentType.DATASET,
            '.parquet': ContentType.DATASET,
            '.avro': ContentType.DATASET,
            '.feather': ContentType.DATASET,
            '.h5': ContentType.DATASET,
            '.hdf5': ContentType.DATASET,
            '.pkl': ContentType.DATASET,
            '.pickle': ContentType.DATASET,
            
            # Log files
            '.log': ContentType.LOG,
            
            # Email formats
            '.eml': ContentType.EMAIL,
            '.msg': ContentType.EMAIL,
            '.pst': ContentType.EMAIL,
            '.ost': ContentType.EMAIL,
            
            # Archive formats
            '.zip': ContentType.ARCHIVE,
            '.tar': ContentType.ARCHIVE,
            '.gz': ContentType.ARCHIVE,
            '.bz2': ContentType.ARCHIVE,
            '.xz': ContentType.ARCHIVE,
            '.7z': ContentType.ARCHIVE,
            '.rar': ContentType.ARCHIVE,
            
            # Executable formats
            '.exe': ContentType.EXECUTABLE,
            '.dll': ContentType.BINARY,
            '.so': ContentType.BINARY,
            '.dylib': ContentType.BINARY,
            '.pyd': ContentType.BINARY,
            
            # Media formats
            '.jpg': ContentType.IMAGE,
            '.jpeg': ContentType.IMAGE,
            '.png': ContentType.IMAGE,
            '.gif': ContentType.IMAGE,
            '.bmp': ContentType.IMAGE,
            '.tiff': ContentType.IMAGE,
            '.webp': ContentType.IMAGE,
            '.mp3': ContentType.AUDIO,
            '.wav': ContentType.AUDIO,
            '.ogg': ContentType.AUDIO,
            '.flac': ContentType.AUDIO,
            '.mp4': ContentType.VIDEO,
            '.avi': ContentType.VIDEO,
            '.mov': ContentType.VIDEO,
            '.wmv': ContentType.VIDEO,
            '.flv': ContentType.VIDEO,
            '.mkv': ContentType.VIDEO,
            
            # Virtual machine and container files
            '.vmdk': ContentType.VIRTUAL_MACHINE,
            '.vdi': ContentType.VIRTUAL_MACHINE,
            '.vhd': ContentType.VIRTUAL_MACHINE,
            '.vhdx': ContentType.VIRTUAL_MACHINE,
            '.qcow2': ContentType.VIRTUAL_MACHINE,
            '.ova': ContentType.VIRTUAL_MACHINE,
            '.ovf': ContentType.VIRTUAL_MACHINE,
            '.dockerfile': ContentType.CONTAINER,
            '.sif': ContentType.CONTAINER,
            '.simg': ContentType.CONTAINER
        }
        
        # Check extension first
        if ext in extension_map:
            return extension_map[ext]
        
        # Then try MIME type if provided
        if mime_type:
            mime_type = mime_type.lower()
            
            # MIME type to content type mapping
            mime_map = {
                # Document MIME types
                'application/pdf': ContentType.PDF,
                'application/msword': ContentType.WORD_DOC,
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ContentType.WORD_DOC,
                'application/vnd.oasis.opendocument.text': ContentType.WORD_DOC,
                'application/rtf': ContentType.WORD_DOC,
                'text/plain': ContentType.TEXT,
                'text/markdown': ContentType.TEXT,
                'text/x-tex': ContentType.PAPER,
                
                # Spreadsheet MIME types
                'application/vnd.ms-excel': ContentType.SPREADSHEET,
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ContentType.SPREADSHEET,
                'application/vnd.oasis.opendocument.spreadsheet': ContentType.SPREADSHEET,
                'text/csv': ContentType.SPREADSHEET,
                
                # Presentation MIME types
                'application/vnd.ms-powerpoint': ContentType.PRESENTATION,
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': ContentType.PRESENTATION,
                'application/vnd.oasis.opendocument.presentation': ContentType.PRESENTATION,
                
                # Email MIME types
                'message/rfc822': ContentType.EMAIL,
                'application/vnd.ms-outlook': ContentType.EMAIL,
                'application/vnd.ms-outlook-pst': ContentType.EMAIL,
                'application/vnd.ms-outlook-ost': ContentType.EMAIL,
                
                # Archive MIME types
                'application/zip': ContentType.ARCHIVE,
                'application/x-tar': ContentType.ARCHIVE,
                'application/gzip': ContentType.ARCHIVE,
                'application/x-bzip2': ContentType.ARCHIVE,
                'application/x-xz': ContentType.ARCHIVE,
                'application/x-7z-compressed': ContentType.ARCHIVE,
                'application/x-rar-compressed': ContentType.ARCHIVE,
                
                # Executable MIME types
                'application/x-msdownload': ContentType.EXECUTABLE,
                'application/x-msdos-program': ContentType.EXECUTABLE,
                'application/x-msi': ContentType.EXECUTABLE,
                'application/x-ms-shortcut': ContentType.EXECUTABLE,
                'application/x-msdos-windows': ContentType.EXECUTABLE,
                
                # Media MIME types
                'image/jpeg': ContentType.IMAGE,
                'image/png': ContentType.IMAGE,
                'image/gif': ContentType.IMAGE,
                'image/bmp': ContentType.IMAGE,
                'image/tiff': ContentType.IMAGE,
                'image/webp': ContentType.IMAGE,
                'audio/mpeg': ContentType.AUDIO,
                'audio/wav': ContentType.AUDIO,
                'audio/ogg': ContentType.AUDIO,
                'audio/flac': ContentType.AUDIO,
                'video/mp4': ContentType.VIDEO,
                'video/x-msvideo': ContentType.VIDEO,
                'video/quicktime': ContentType.VIDEO,
                'video/x-ms-wmv': ContentType.VIDEO,
                'video/x-flv': ContentType.VIDEO,
                'video/x-matroska': ContentType.VIDEO,
                
                # Database MIME types
                'application/x-sqlite3': ContentType.DATABASE,
                'application/x-sqlite2': ContentType.DATABASE,
                'application/x-sql': ContentType.DATABASE,
                'application/x-netcdf': ContentType.DATABASE,
                'application/x-msaccess': ContentType.DATABASE,
                'application/vnd.ms-access': ContentType.DATABASE,
                
                # Code MIME types
                'text/x-python': ContentType.SOURCE_CODE,
                'application/javascript': ContentType.SOURCE_CODE,
                'application/x-javascript': ContentType.SOURCE_CODE,
                'text/javascript': ContentType.SOURCE_CODE,
                'text/x-java-source': ContentType.SOURCE_CODE,
                'text/x-c': ContentType.SOURCE_CODE,
                'text/x-c++': ContentType.SOURCE_CODE,
                'text/x-csharp': ContentType.SOURCE_CODE,
                'text/x-go': ContentType.SOURCE_CODE,
                'text/x-rust': ContentType.SOURCE_CODE,
                'text/x-ruby': ContentType.SOURCE_CODE,
                'application/x-php': ContentType.SOURCE_CODE,
                'application/x-shellscript': ContentType.SCRIPT,
                'text/x-shellscript': ContentType.SCRIPT,
                'text/x-batch': ContentType.SCRIPT,
                'text/html': ContentType.SOURCE_CODE,
                'text/css': ContentType.SOURCE_CODE,
                'text/x-typescript': ContentType.SOURCE_CODE,
                'application/json': ContentType.CONFIG,
                'application/x-yaml': ContentType.CONFIG,
                'text/yaml': ContentType.CONFIG,
                'text/toml': ContentType.CONFIG,
                'text/x-ini': ContentType.CONFIG,
                'text/x-config': ContentType.CONFIG
            }
            
            # Check for partial MIME type matches
            for mime_pattern, content_type in mime_map.items():
                if mime_pattern in mime_type:
                    return content_type
        
        # For text files, try to determine content type from content
        if text_content and len(text_content) > 0:
            try:
                # Use ML-based classification for text content
                predicted_type = self.text_classifier.predict(text_content[:10000])  # Use first 10KB for classification
                
                # Map prediction to our content types
                if predicted_type in [t.value for t in ContentType]:
                    return ContentType(predicted_type)
                
                # Fallback to simple heuristics if ML classification fails
                if any(keyword in text_content.lower() for keyword in ['dear', 'sincerely', 'regards']):
                    return ContentType.EMAIL
                elif any(keyword in text_content.lower() for keyword in ['abstract', 'introduction', 'conclusion']):
                    return ContentType.PAPER
                elif any(keyword in text_content.lower() for keyword in ['#!', 'def ', 'function ', 'class ', 'import ']):
                    return ContentType.SOURCE_CODE
                elif any(keyword in text_content.lower() for keyword in ['error', 'warning', 'exception', 'traceback']):
                    return ContentType.LOG
                
            except Exception as e:
                logger.debug(f"Error in ML-based content type detection: {e}")
        
        # Fallback to basic file type detection
        try:
            if not mime_type:
                mime_type = self._get_mime_type(file_path)
                
            if 'text/' in mime_type:
                return ContentType.TEXT
            elif 'image/' in mime_type:
                return ContentType.IMAGE
            elif 'audio/' in mime_type:
                return ContentType.AUDIO
            elif 'video/' in mime_type:
                return ContentType.VIDEO
            elif 'application/' in mime_type:
                return ContentType.DOCUMENT
            else:
                return ContentType.UNKNOWN
                
        except Exception as e:
            logger.warning(f"Failed to detect content type for {file_path}: {e}")
            return ContentType.UNKNOWN
    
    def analyze_file(self, file_path: Union[str, Path], force: bool = False) -> ContentAnalysis:
        """
        Analyze a file and return detailed content analysis.
        
        Args:
            file_path: Path to the file to analyze
            force: If True, force re-analysis even if file hasn't changed
            
        Returns:
            ContentAnalysis object with analysis results
        """
        file_path = Path(file_path)
        start_time = time.time()
        analysis = ContentAnalysis(
            content_type=ContentType.UNKNOWN,
            mime_type="",
            file_size=file_path.stat().st_size
        )
        
        try:
            # Check cache first
            if not force and (cached := self._get_cached_analysis(file_path)):
                return cached
            
            # Get MIME type
            mime_type = self._get_mime_type(file_path)
            analysis.mime_type = mime_type
            
            # Detect content type
            analysis.content_type = self._detect_content_type(file_path, mime_type)
            
            # Extract text based on content type
            text_content = self._extract_text(file_path, analysis.content_type)
            
            # Analyze text content
            if text_content:
                doc = self.nlp(text_content)
                
                # Detect sensitive information
                analysis.sensitive_info = self._find_sensitive_info(doc)
                analysis.contains_pii = any(info['sensitivity'] >= SensitivityLevel.HIGH 
                                         for info in analysis.sensitive_info)
                
                # Extract keywords and entities
                analysis.keywords = self._extract_keywords(text_content)
                analysis.entities = self._extract_entities(doc)
                
                # Detect language
                analysis.language = self._detect_language(text_content)
            
            # Extract metadata
            analysis.metadata = self._extract_metadata(file_path, analysis.content_type)
            
            # Calculate checksum
            analysis.checksum = self._calculate_checksum(file_path)
            
            # Calculate sensitivity score
            analysis.sensitivity_score = self._calculate_sensitivity_score(analysis)
            
            # Cache the results
            self._cache_analysis(file_path, analysis)
            
        except Exception as e:
            error_msg = f"Error analyzing {file_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            analysis.error = error_msg
            
        analysis.processing_time = time.time() - start_time
        return analysis
    
    def _extract_text(self, file_path: Path, content_type: ContentType) -> Optional[str]:
        """
        Extract text from a file based on its content type.
        
        Args:
            file_path: Path to the file
            content_type: Detected content type
            
        Returns:
            Extracted text or None if extraction fails or not applicable
        """
        try:
            if content_type == ContentType.IMAGE:
                return self._extract_text_from_image(file_path)
                
            elif content_type == ContentType.DOCUMENT:
                if file_path.suffix.lower() == '.pdf':
                    return self._extract_text_from_pdf(file_path)
                elif file_path.suffix.lower() in ['.docx', '.doc']:
                    return self._extract_text_from_docx(file_path)
                elif file_path.suffix.lower() in ['.odt', '.fodt']:
                    return self._extract_text_from_odt(file_path)
                elif file_path.suffix.lower() in ['.rtf']:
                    return self._extract_text_from_rtf(file_path)
                
            elif content_type == ContentType.SPREADSHEET:
                return self._extract_text_from_spreadsheet(file_path)
                
            elif content_type == ContentType.PRESENTATION:
                return self._extract_text_from_presentation(file_path)
                
            # For text files, read directly
            elif content_type in [ContentType.TEXT, ContentType.CODE]:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
                except UnicodeDecodeError:
                    # Try with different encodings
                    for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                return f.read()
                        except UnicodeDecodeError:
                            continue
            
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting text from {file_path}: {e}")
            return None
    
    def _extract_text_from_image(self, image_path: Path) -> str:
        """Extract text from an image using OCR."""
        try:
            # Preprocess image for better OCR
            img = Image.open(image_path)
            img = self._preprocess_image_for_ocr(img)
            
            # Use pytesseract to extract text
            text = pytesseract.image_to_string(img)
            return text.strip()
            
        except Exception as e:
            logger.warning(f"OCR failed for {image_path}: {e}")
            return ""
    
    def _preprocess_image_for_ocr(self, img: Image.Image) -> Image.Image:
        """Preprocess image to improve OCR accuracy."""
        try:
            # Convert to grayscale
            if img.mode != 'L':
                img = img.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            
            # Apply adaptive thresholding
            img = ImageOps.autocontrast(img)
            
            # Apply sharpening
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.0)
            
            # Resize if too large
            if max(img.size) > 3000:
                ratio = 3000 / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                
            return img
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")
            return img
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from a PDF file."""
        try:
            text = []
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text.append(page.get_text())
            return '\n'.join(text)
        except Exception as e:
            logger.warning(f"Failed to extract text from PDF {pdf_path}: {e}")
            return ""
    
    def _extract_text_from_docx(self, docx_path: Path) -> str:
        """Extract text from a DOCX file."""
        try:
            doc = Document(docx_path)
            return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
        except Exception as e:
            logger.warning(f"Failed to extract text from DOCX {docx_path}: {e}")
            return ""
    
    def _extract_odt_metadata(self, odt_path: Path) -> Dict[str, Any]:
        """Extract metadata from ODT files."""
        try:
            with zipfile.ZipFile(odt_path) as z:
                # Check for meta.xml which contains metadata
                if 'meta.xml' in z.namelist():
                    with z.open('meta.xml') as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        # Extract basic metadata using regex
                        meta = {}
                        for tag in ['creator', 'date', 'description', 'subject', 'title', 'language']:
                            if f'<dc:{tag}>' in content:
                                start = content.find(f'<dc:{tag}>') + len(f'<dc:{tag}>')
                                end = content.find(f'</dc:{tag}>', start)
                                if start > 0 and end > start:
                                    meta[tag] = content[start:end].strip()
                        return meta
            return {}
        except Exception as e:
            logger.warning(f"ODT metadata extraction failed for {odt_path}: {e}")
            return {}

    def _extract_text_from_odt(self, odt_path: Path) -> str:
        """Extract text from an ODT file with improved handling of different structures."""
        try:
            with zipfile.ZipFile(odt_path) as z:
                # Try to find content.xml or other potential content files
                content_files = [f for f in z.namelist() if 'content.xml' in f or 'meta.xml' in f or 'styles.xml' in f]
                
                all_text = []
                
                for content_file in content_files:
                    try:
                        with z.open(content_file) as f:
                            content = f.read()
                            
                        # Try to detect encoding
                        try:
                            # First try UTF-8 with BOM
                            text = content.decode('utf-8-sig')
                        except UnicodeDecodeError:
                            # Fall back to detected encoding or latin-1
                            detected = chardet.detect(content)
                            text = content.decode(detected['encoding'] if detected['confidence'] > 0.7 else 'latin-1', errors='replace')
                        
                        # Improved XML tag and control character handling
                        # Remove comments first
                        text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
                        # Remove processing instructions
                        text = re.sub(r'<\?.*?\?>', ' ', text, flags=re.DOTALL)
                        # Remove all remaining XML tags
                        text = re.sub(r'<[^>]+>', ' ', text)
                        # Normalize whitespace
                        text = re.sub(r'\s+', ' ', text).strip()
                        # Remove control characters except newlines and tabs
                        text = ''.join(char for char in text if char.isprintable() or char in '\n\r\t')
                        
                        if text.strip():
                            all_text.append(text)
                            
                    except Exception as e:
                        logger.debug(f"Error processing {content_file} in ODT: {e}")
                        continue
                
                return '\n'.join(all_text) if all_text else ""
                
        except Exception as e:
            logger.warning(f"Failed to extract text from ODT {odt_path}: {e}")
            return ""
    
    def _extract_text_from_rtf(self, rtf_path: Path) -> str:
        """Extract text from an RTF file with improved control sequence handling."""
        try:
            # Read file as binary first for better encoding detection
            with open(rtf_path, 'rb') as f:
                raw_content = f.read()
            
            # Try to detect encoding with more confidence
            detected = chardet.detect(raw_content[:10000])  # Check first 10KB
            encodings_to_try = []
            
            if detected['confidence'] > 0.8:
                encodings_to_try.append(detected['encoding'])
            
            # Common RTF encodings to try
            encodings_to_try.extend(['utf-8-sig', 'cp1252', 'iso-8859-1', 'latin-1'])
            
            content = None
            for encoding in encodings_to_try:
                try:
                    content = raw_content.decode(encoding, errors='strict')
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            
            if content is None:
                # Fallback to replace errors
                content = raw_content.decode('utf-8', errors='replace')
            
            # Improved RTF control sequence handling
            # Remove RTF header (everything up to first {)
            content = re.sub(r'^.*?\\', '\\', content, flags=re.DOTALL)
            
            # Remove font tables and color tables
            content = re.sub(r'\\fonttbl\{.*?\}', ' ', content, flags=re.DOTALL)
            content = re.sub(r'\\colortbl\{.*?\}', ' ', content, flags=re.DOTALL)
            content = re.sub(r'\\stylesheet\{.*?\}', ' ', content, flags=re.DOTALL)
            
            # Remove common RTF control words
            content = re.sub(r'\\[a-z0-9]+(?:\s+[0-9]+)?[;\\]?', ' ', content, flags=re.IGNORECASE)
            
            # Handle escaped characters
            content = content.replace('\\{', '{').replace('\\}', '}')
            content = content.replace('\\\n', ' ').replace('\\\r', ' ').replace('\\\t', ' ')
            
            # Remove remaining control characters and normalize whitespace
            content = re.sub(r'[\x00-\x1F\x7F]', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()
            
            # Remove any remaining RTF groups
            content = re.sub(r'\{[^}]*\}', ' ', content)
            
            # Final cleanup
            content = re.sub(r'\s+', ' ', content).strip()
            
            return content
            
        except Exception as e:
            logger.warning(f"Failed to extract text from RTF {rtf_path}: {e}")
            return ""
    
    def _extract_spreadsheet_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from spreadsheet files."""
        try:
            if file_path.suffix.lower() == '.csv':
                # For CSV, just count lines as a rough estimate of rows
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    row_count = sum(1 for _ in f)
                return {
                    'format': 'CSV',
                    'estimated_row_count': row_count,
                    'has_header': row_count > 0
                }
            else:
                # For Excel/ODS files
                if file_path.suffix.lower() == '.xlsx':
                    wb = load_workbook(file_path, read_only=True, data_only=True)
                    file_format = 'Excel'
                else:  # ODS
                    wb = load_workbook(file_path, read_only=True)
                    file_format = 'OpenDocument Spreadsheet'
                
                sheet_info = []
                for sheet in wb.worksheets:
                    sheet_info.append({
                        'name': sheet.title,
                        'dimensions': sheet.dimensions,
                        'row_count': sheet.max_row,
                        'column_count': sheet.max_column
                    })
                
                return {
                    'format': file_format,
                    'sheet_count': len(wb.worksheets),
                    'sheet_info': sheet_info,
                    'has_formulas': any(True for sheet in wb.worksheets for row in sheet.iter_rows() 
                                      for cell in row if cell.data_type == 'f')
                }
        except Exception as e:
            logger.warning(f"Spreadsheet metadata extraction failed for {file_path}: {e}")
            return {}

    def _extract_text_from_spreadsheet(self, file_path: Path) -> str:
        """Extract text from spreadsheet files (XLSX, ODS, CSV) with improved handling."""
        try:
            text_parts = []
            
            if file_path.suffix.lower() == '.csv':
                # Try to detect delimiter and encoding first
                with open(file_path, 'rb') as f:
                    sample = f.read(10000).decode('ascii', errors='ignore')
                    
                # Try to detect delimiter
                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(sample)
                except:
                    dialect = None
                
                # Try multiple encodings for CSV files
                encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'cp1250']
                
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding, errors='strict') as f:
                            reader = csv.reader(f, dialect=dialect) if dialect else csv.reader(f)
                            for row in reader:
                                # Clean and join cells
                                cleaned_cells = []
                                for cell in row:
                                    if not cell:
                                        continue
                                    cell = str(cell).strip()
                                    # Remove any remaining control characters
                                    cell = ''.join(c for c in cell if c.isprintable() or c in '\n\r\t')
                                    if cell:
                                        cleaned_cells.append(cell)
                                
                                if cleaned_cells:
                                    text_parts.append(' | '.join(cleaned_cells))
                        
                        # If we got here, reading was successful
                        break
                            
                    except (UnicodeDecodeError, csv.Error) as e:
                        if encoding == encodings[-1]:  # If this was our last attempt
                            logger.warning(f"Failed to read CSV {file_path} with any encoding: {e}")
                            # Try one last time with error replacement
                            try:
                                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                                    reader = csv.reader(f, dialect=dialect) if dialect else csv.reader(f)
                                    for row in reader:
                                        text_parts.append(' | '.join(str(cell).strip() for cell in row if str(cell).strip()))
                            except:
                                pass
                        continue
            else:
                # Handle Excel/ODS files
                if file_path.suffix.lower() == '.xlsx':
                    wb = load_workbook(file_path, read_only=True, data_only=True)
                else:  # ODS
                    wb = load_workbook(file_path, read_only=True)
                
                for sheet in wb.worksheets:
                    # Add sheet name as a header
                    sheet_text = [f"[Sheet: {sheet.title}]"]
                    
                    # Add data from cells
                    for row in sheet.iter_rows(values_only=True):
                        row_text = ' '.join(str(cell).strip() for cell in row if cell is not None and str(cell).strip())
                        if row_text:
                            sheet_text.append(row_text)
                    
                    if len(sheet_text) > 1:  # If we have content beyond the header
                        text_parts.append('\n'.join(sheet_text))
            
            return '\n\n'.join(text_parts)
            
        except Exception as e:
            logger.warning(f"Failed to extract text from spreadsheet {file_path}: {e}")
            return ""
    
    def _extract_presentation_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from presentation files."""
        try:
            if file_path.suffix.lower() == '.pptx':
                prs = Presentation(file_path)
                return {
                    'format': 'PowerPoint',
                    'slide_count': len(prs.slides),
                    'has_notes': any(slide.has_notes_slide for slide in prs.slides),
                    'has_media': any(slide.slide_layout.name.lower().find('media') >= 0 
                                   for slide in prs.slides if hasattr(slide, 'slide_layout'))
                }
            else:  # ODP
                # Basic ODP metadata extraction
                with zipfile.ZipFile(file_path) as z:
                    # Count content.xml entries that look like slides
                    with z.open('content.xml') as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        slide_count = content.count('<draw:page ')
                        
                    return {
                        'format': 'OpenDocument Presentation',
                        'estimated_slide_count': slide_count
                    }
        except Exception as e:
            logger.warning(f"Presentation metadata extraction failed for {file_path}: {e}")
            return {}

    def _extract_archive_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from archive files."""
        try:
            with zipfile.ZipFile(file_path) as z:
                file_list = z.namelist()
                return {
                    'file_count': len(file_list),
                    'compressed_size': sum(zinfo.compress_size for zinfo in z.filelist),
                    'uncompressed_size': sum(zinfo.file_size for zinfo in z.filelist),
                    'compression_ratio': (sum(zinfo.compress_size for zinfo in z.filelist) / 
                                         sum(zinfo.file_size for zinfo in z.filelist) 
                                         if sum(zinfo.file_size for zinfo in z.filelist) > 0 else 0),
                    'contains_executables': any(name.lower().endswith(('.exe', '.dll', '.so', '.dylib')) 
                                              for name in file_list)
                }
        except Exception as e:
            logger.warning(f"Archive metadata extraction failed for {file_path}: {e}")
            return {}

    def _count_lines(self, file_path: Path) -> int:
        """Count the number of lines in a text file."""
        try:
            with open(file_path, 'rb') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _extract_text_from_presentation(self, file_path: Path) -> str:
        """Extract text from presentation files (PPTX, ODP) with improved handling."""
        try:
            text_parts = []
            
            if file_path.suffix.lower() == '.pptx':
                try:
                    prs = Presentation(file_path)
                    
                    # Extract metadata first
                    props = prs.core_properties
                    if props.title:
                        text_parts.append(f"Title: {props.title}")
                    if props.subject:
                        text_parts.append(f"Subject: {props.subject}")
                    if props.author:
                        text_parts.append(f"Author: {props.author}")
                    
                    # Process each slide
                    for i, slide in enumerate(prs.slides, 1):
                        slide_text = [f"[Slide {i} - {slide.slide_layout.name if hasattr(slide, 'slide_layout') else 'No Layout'}]"]
                        
                        # Extract text from shapes
                        for shape in slide.shapes:
                            try:
                                if hasattr(shape, "text") and shape.text.strip():
                                    slide_text.append(shape.text.strip())
                                
                                # Handle tables
                                if shape.has_table:
                                    table = shape.table
                                    for row in table.rows:
                                        row_text = []
                                        for cell in row.cells:
                                            if cell.text.strip():
                                                row_text.append(cell.text.strip())
                                        if row_text:
                                            slide_text.append(' | '.join(row_text))
                            except Exception as e:
                                logger.debug(f"Error processing shape in slide {i}: {e}")
                                continue
                        
                        # Extract notes if available
                        try:
                            if hasattr(slide, 'notes_slide') and slide.notes_slide:
                                notes_frame = slide.notes_slide.notes_text_frame
                                if notes_frame and notes_frame.text.strip():
                                    slide_text.append(f"Notes: {notes_frame.text.strip()}")
                        except Exception as e:
                            logger.debug(f"Error extracting notes from slide {i}: {e}")
                        
                        if len(slide_text) > 1:  # If we have content beyond the slide header
                            text_parts.append('\n'.join(slide_text))
                            
                except Exception as e:
                    logger.warning(f"Error processing PPTX file {file_path}: {e}")
                    
            else:  # ODP
                with zipfile.ZipFile(file_path) as z:
                    # Extract from content.xml (slides) and styles.xml (master slides)
                    for xml_file in ['content.xml', 'styles.xml']:
                        if xml_file in z.namelist():
                            try:
                                with z.open(xml_file) as f:
                                    content = f.read()
                                    
                                    # Try UTF-8 first, then fall back to detected encoding
                                    try:
                                        text = content.decode('utf-8')
                                    except UnicodeDecodeError:
                                        detected = chardet.detect(content)
                                        text = content.decode(detected['encoding'] if detected['confidence'] > 0.7 else 'latin-1', errors='replace')
                                    
                                    # Improved XML processing
                                    # Remove comments
                                    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
                                    # Remove processing instructions
                                    text = re.sub(r'<\?.*?\?>', ' ', text, flags=re.DOTALL)
                                    # Remove all XML tags but keep text
                                    text = re.sub(r'<[^>]+>', ' ', text)
                                    # Normalize whitespace
                                    text = re.sub(r'\s+', ' ', text).strip()
                                    # Remove control characters except newlines and tabs
                                    text = ''.join(char for char in text if char.isprintable() or char in '\n\r\t')
                                    
                                    if text.strip():
                                        text_parts.append(text)
                                        
                            except Exception as e:
                                logger.debug(f"Error processing {xml_file} in ODP: {e}")
                                continue
            
            return '\n\n'.join(text_parts)
            
        except Exception as e:
            logger.warning(f"Failed to extract text from presentation {file_path}: {e}")
            return ""
    
    def _find_sensitive_info(self, doc) -> List[Dict[str, Any]]:
        """Find sensitive information in the document using regex patterns and NER."""
        sensitive_info = []
        
        # Check for sensitive patterns
        for pattern in self.sensitive_patterns:
            for match in re.finditer(pattern.compiled, doc.text):
                context = self._get_context(doc.text, match.start(), match.end())
                sensitive_info.append({
                    'type': pattern.name,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'context': context,
                    'sensitivity': pattern.sensitivity.value,
                    'description': pattern.description
                })
        
        # Use NER to find potential secrets (API keys, tokens, etc.)
        sensitive_info.extend(self._find_potential_secrets(doc))
        
        return sensitive_info
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get context around a match in the text."""
        start_ctx = max(0, start - window)
        end_ctx = min(len(text), end + window)
        prefix = '...' if start_ctx > 0 else ''
        suffix = '...' if end_ctx < len(text) else ''
        return f"{prefix}{text[start_ctx:end_ctx]}{suffix}"
    
    def _find_potential_secrets(self, doc) -> List[Dict[str, Any]]:
        """Find potential secrets using heuristics and NER."""
        secrets = []
        
        # Look for common secret patterns
        secret_patterns = [
            (r'[A-Za-z0-9+/=]{40,}', 'Potential API Key/Token'),
            (r'[A-Za-z0-9]{32,}', 'Potential Hash/Token'),
            (r'[A-Za-z0-9-]{36}', 'Potential UUID'),
            (r'[A-Za-z0-9]{24}', 'Potential MongoDB ID'),
        ]
        
        for pattern, description in secret_patterns:
            for match in re.finditer(pattern, doc.text):
                # Skip if it's part of a URL or common non-secret patterns
                if not self._is_likely_secret(match.group(), doc.text, match.start(), match.end()):
                    continue
                    
                context = self._get_context(doc.text, match.start(), match.end())
                secrets.append({
                    'type': 'potential_secret',
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'context': context,
                    'sensitivity': SensitivityLevel.HIGH.value,
                    'description': description
                })
        
        return secrets
    
    def _is_likely_secret(self, token: str, full_text: str, start: int, end: int) -> bool:
        """Determine if a token is likely to be a secret."""
        # Skip if it's part of a URL
        if re.search(r'https?://[^\s]+', full_text[max(0, start-10):min(len(full_text), end+10)]):
            return False
            
        # Skip if it's part of a common non-secret pattern
        non_secret_patterns = [
            r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',  # UUID
            r'[0-9a-fA-F]{32}',  # MD5 hash
            r'[0-9a-fA-F]{40}',  # SHA-1 hash
            r'[0-9a-fA-F]{64}',  # SHA-256 hash
        ]
        
        for pattern in non_secret_patterns:
            if re.fullmatch(pattern, token):
                return False
                
        return True
    
    def _extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """Extract keywords from text using KeyBERT."""
        try:
            keywords = self.kw_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2),
                stop_words='english',
                use_mmr=True,
                diversity=0.7,
                top_n=top_n
            )
            return [kw[0] for kw in keywords if kw[1] > 0.2]  # Filter by confidence
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            return []
    
    def _extract_entities(self, doc) -> List[Dict[str, Any]]:
        """Extract named entities from text using spaCy NER."""
        entities = []
        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char,
                'confidence': 0.9  # Placeholder, could be enhanced with model confidence
            })
        return entities
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of the text."""
        try:
            # Simple language detection based on common words
            # For more accurate detection, consider using langdetect or similar
            text_lower = text.lower()
            
            # Check for common English words
            en_words = ['the', 'and', 'for', 'that', 'have', 'with', 'this', 'but', 'not', 'you']
            en_score = sum(1 for word in en_words if f' {word} ' in f' {text_lower} ')
            
            # Add more language checks as needed
            
            # Default to English for now
            return 'en' if en_score > 2 else 'unknown'
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return 'unknown'
    
    def _detect_encoding(self, file_path: Path) -> str:
        """Detect the encoding of a text file."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Read first 10KB for detection
                result = chardet.detect(raw_data)
                return result.get('encoding', 'utf-8')
        except Exception as e:
            logger.warning(f"Encoding detection failed for {file_path}: {e}")
            return 'utf-8'

    def _extract_metadata(self, file_path: Path, content_type: ContentType) -> Dict[str, Any]:
        """Extract metadata from the file."""
        metadata = {}
        
        try:
            # Basic file metadata
            stat = file_path.stat()
            metadata.update({
                'size_bytes': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'accessed': stat.st_atime,
                'file_extension': file_path.suffix.lower(),
                'file_name': file_path.name,
                'parent_dir': str(file_path.parent),
                'file_type': content_type.value
            })
            
            # Content type specific metadata
            try:
                if content_type == ContentType.IMAGE:
                    metadata.update(self._extract_image_metadata(file_path))
                elif content_type == ContentType.DOCUMENT:
                    if file_path.suffix.lower() == '.pdf':
                        metadata.update(self._extract_pdf_metadata(file_path))
                    elif file_path.suffix.lower() in ['.docx', '.doc']:
                        metadata.update(self._extract_docx_metadata(file_path))
                    elif file_path.suffix.lower() in ['.odt', '.fodt']:
                        metadata.update(self._extract_odt_metadata(file_path))
                    elif file_path.suffix.lower() == '.rtf':
                        metadata.update({'type': 'rich_text_format'})
                elif content_type == ContentType.SPREADSHEET:
                    metadata.update(self._extract_spreadsheet_metadata(file_path))
                elif content_type == ContentType.PRESENTATION:
                    metadata.update(self._extract_presentation_metadata(file_path))
                elif content_type == ContentType.ARCHIVE:
                    metadata.update(self._extract_archive_metadata(file_path))
                elif content_type == ContentType.CODE:
                    metadata.update({
                        'language': file_path.suffix[1:].lower(),
                        'line_count': self._count_lines(file_path)
                    })
            except Exception as e:
                logger.warning(f"Content-specific metadata extraction failed for {file_path}: {e}")
            
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {file_path}: {e}")
        
        return metadata
    
    def _extract_image_metadata(self, image_path: Path) -> Dict[str, Any]:
        """Extract metadata from image files."""
        try:
            with Image.open(image_path) as img:
                metadata = {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'dimensions': f"{img.width}x{img.height}",
                    'info': {}
                }
                
                # Extract EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = {}
                    for tag, value in img._getexif().items():
                        if tag in ExifTags.TAGS:
                            exif_data[ExifTags.TAGS[tag]] = value
                    metadata['exif'] = exif_data
                
                # Add basic image info
                metadata['info'] = {
                    'dpi': img.info.get('dpi', None),
                    'compression': img.info.get('compression', None),
                    'progressive': img.info.get('progressive', False)
                }
                
                return metadata
        except Exception as e:
            logger.warning(f"Image metadata extraction failed for {image_path}: {e}")
            return {}
    
    def _extract_pdf_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract metadata from PDF files."""
        try:
            with fitz.open(pdf_path) as doc:
                metadata = {
                    'page_count': len(doc),
                    'is_encrypted': doc.is_encrypted,
                    'metadata': {},
                    'has_toc': len(doc.get_toc()) > 0,
                    'has_forms': len(doc.get_form_text_fields()) > 0,
                    'has_annotations': False
                }
                
                # Extract standard PDF metadata
                pdf_metadata = doc.metadata
                if pdf_metadata:
                    metadata['metadata'] = {k: v for k, v in pdf_metadata.items() if v}
                
                # Check for annotations on each page
                for page in doc:
                    if page.annots():
                        metadata['has_annotations'] = True
                        break
                
                return metadata
        except Exception as e:
            logger.warning(f"PDF metadata extraction failed for {pdf_path}: {e}")
            return {}
    
    def _extract_docx_metadata(self, docx_path: Path) -> Dict[str, Any]:
        """Extract metadata from DOCX files."""
        try:
            doc = Document(docx_path)
            
            # Count various elements
            element_counts = {
                'paragraphs': len(doc.paragraphs),
                'tables': len(doc.tables),
                'sections': len(doc.sections),
                'inlines': 0,
                'pages': 0
            }
            
            # Estimate page count (very rough estimate)
            if doc.paragraphs:
                element_counts['pages'] = max(1, len(doc.paragraphs) // 30)  # ~30 paragraphs per page
            
            # Get core properties
            core_props = {}
            if hasattr(doc, 'core_properties'):
                core_props = {
                    'author': doc.core_properties.author,
                    'created': str(doc.core_properties.created) if doc.core_properties.created else None,
                    'modified': str(doc.core_properties.modified) if doc.core_properties.modified else None,
                    'title': doc.core_properties.title,
                    'subject': doc.core_properties.subject,
                    'keywords': doc.core_properties.keywords,
                    'category': doc.core_properties.category,
                    'comments': doc.core_properties.comments,
                    'content_status': doc.core_properties.content_status,
                    'identifier': doc.core_properties.identifier,
                    'language': doc.core_properties.language,
                    'version': doc.core_properties.version,
                    'last_modified_by': doc.core_properties.last_modified_by,
                    'last_printed': str(doc.core_properties.last_printed) if doc.core_properties.last_printed else None,
                    'revision': doc.core_properties.revision
                }
            
            return {
                'element_counts': element_counts,
                'core_properties': {k: v for k, v in core_props.items() if v is not None}
            }
        except Exception as e:
            logger.warning(f"DOCX metadata extraction failed for {docx_path}: {e}")
            return {}
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate checksum of a file."""
        hash_func = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Read and update hash in chunks of 4K
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
            
        except Exception as e:
            logger.warning(f"Checksum calculation failed for {file_path}: {e}")
            return ""
    
    def _calculate_sensitivity_score(self, analysis: ContentAnalysis) -> float:
        """
        Calculate a sensitivity score based on the analysis results.
        Higher scores indicate more sensitive content.
        """
        score = 0.0
        
        # Increase score for sensitive information
        for info in analysis.sensitive_info:
            score += info.get('sensitivity', 0) * 0.5
        
        # Increase score for PII
        if analysis.contains_pii:
            score += 2.0
            
        # Increase score for encrypted content
        if analysis.is_encrypted:
            score += 1.5
        
        # Adjust based on content type
        if analysis.content_type in [ContentType.DATABASE, ContentType.SOURCE_CODE]:
            score += 1.0
            
        # Cap the score at 10.0
        return min(10.0, max(0.0, score))
    
    def _get_cached_analysis(self, file_path: Path) -> Optional[ContentAnalysis]:
        """
        Get cached analysis results if available and still valid.
        
        Args:
            file_path: Path to the file to check in cache
            
        Returns:
            Cached ContentAnalysis or None if not in cache or outdated
        """
        if not self.db_path:
            return None
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM content_analysis 
                    WHERE file_path = ?
                ''', (str(file_path),))
                
                row = cursor.fetchone()
                if not row:
                    return None
                    
                # Check if file has been modified since last analysis
                last_modified = os.path.getmtime(file_path)
                if row[13] < last_modified:  # last_analyzed < file_mtime
                    return None
                    
                # Deserialize the analysis
                return self._deserialize_analysis(row)
                
        except Exception as e:
            logger.warning(f"Error retrieving cached analysis for {file_path}: {e}")
            return None
    
    def _cache_analysis(self, file_path: Path, analysis: ContentAnalysis) -> None:
        """
        Cache the analysis results in the database.
        
        Args:
            file_path: Path to the analyzed file
            analysis: ContentAnalysis object to cache
        """
        if not self.db_path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Serialize complex fields
                sensitive_info = json.dumps(analysis.sensitive_info) if analysis.sensitive_info else '[]'
                keywords = json.dumps(analysis.keywords) if analysis.keywords else '[]'
                entities = json.dumps(analysis.entities) if analysis.entities else '[]'
                metadata = json.dumps(analysis.metadata) if analysis.metadata else '{}'
                
                # Insert or replace existing analysis
                cursor.execute('''
                    INSERT OR REPLACE INTO content_analysis (
                        file_path, content_type, mime_type, file_size, 
                        sensitive_info, keywords, entities, checksum, 
                        metadata, language, is_encrypted, contains_pii, 
                        sensitivity_score, processing_time, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(file_path),
                    analysis.content_type.value,
                    analysis.mime_type,
                    analysis.file_size,
                    sensitive_info,
                    keywords,
                    entities,
                    analysis.checksum,
                    metadata,
                    analysis.language,
                    int(analysis.is_encrypted),
                    int(analysis.contains_pii),
                    analysis.sensitivity_score,
                    analysis.processing_time,
                    analysis.error
                ))
                
                # Log to history
                cursor.execute('''
                    INSERT INTO analysis_history (
                        file_path, content_type, sensitive_info_count, 
                        sensitivity_score, processing_time
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    str(file_path),
                    analysis.content_type.value,
                    len(analysis.sensitive_info),
                    analysis.sensitivity_score,
                    analysis.processing_time
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error caching analysis for {file_path}: {e}")
    
    def _deserialize_analysis(self, row: tuple) -> ContentAnalysis:
        """
        Deserialize a database row into a ContentAnalysis object.
        
        Args:
            row: Database row from content_analysis table
            
        Returns:
            Deserialized ContentAnalysis object
        """
        try:
            analysis = ContentAnalysis(
                content_type=ContentType(row[1]),
                mime_type=row[2],
                file_size=row[3],
                sensitive_info=json.loads(row[4]) if row[4] else [],
                keywords=json.loads(row[5]) if row[5] else [],
                entities=json.loads(row[6]) if row[6] else [],
                checksum=row[7],
                metadata=json.loads(row[8]) if row[8] else {},
                language=row[9],
                is_encrypted=bool(row[10]),
                contains_pii=bool(row[11]),
                sensitivity_score=row[12],
                processing_time=row[13],
                error=row[15] if len(row) > 15 else None
            )
            return analysis
            
        except Exception as e:
            logger.error(f"Error deserializing analysis: {e}")
            raise
    
    def analyze_directory(
        self, 
        directory: Union[str, Path], 
        recursive: bool = True,
        file_pattern: Optional[str] = None,
        max_file_size: Optional[int] = None,
        content_types: Optional[List[ContentType]] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, ContentAnalysis]:
        """
        Analyze all files in a directory.
        
        Args:
            directory: Directory to analyze
            recursive: If True, analyze subdirectories recursively
            file_pattern: Optional glob pattern to filter files
            max_file_size: Maximum file size to analyze in bytes
            content_types: List of content types to include (None for all)
            force: If True, force re-analysis of all files
            progress_callback: Optional callback for progress updates (current, total, current_file)
            
        Returns:
            Dictionary mapping file paths to ContentAnalysis objects
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        # Find all matching files
        file_pattern = file_pattern or '*'
        files = []
        
        if recursive:
            for ext in SUPPORTED_EXTS:
                files.extend(directory.rglob(f"{file_pattern}{ext}"))
        else:
            for ext in SUPPORTED_EXTS:
                files.extend(directory.glob(f"{file_pattern}{ext}"))
        
        # Filter by content type if specified
        if content_types:
            content_type_set = set(content_types)
            files = [f for f in files if self._detect_content_type(f) in content_type_set]
        
        # Filter by size if specified
        if max_file_size is not None:
            files = [f for f in files if f.stat().st_size <= max_file_size]
        
        # Analyze each file
        results = {}
        total_files = len(files)
        
        for i, file_path in enumerate(files, 1):
            if progress_callback:
                progress_callback(i, total_files, str(file_path))
                
            try:
                results[str(file_path)] = self.analyze_file(file_path, force=force)
            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                results[str(file_path)] = ContentAnalysis(
                    content_type=ContentType.UNKNOWN,
                    mime_type="",
                    file_size=file_path.stat().st_size,
                    error=str(e)
                )
        
        return results
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the analysis results.
        
        Returns:
            Dictionary with analysis statistics
        """
        if not self.db_path:
            return {}
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total number of files analyzed
                cursor.execute('SELECT COUNT(*) FROM content_analysis')
                total_files = cursor.fetchone()[0]
                
                # Get files by content type
                cursor.execute('''
                    SELECT content_type, COUNT(*) 
                    FROM content_analysis 
                    GROUP BY content_type
                ''')
                files_by_type = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Get files with sensitive information
                cursor.execute('''
                    SELECT COUNT(DISTINCT file_path)
                    FROM content_analysis, json_each(content_analysis.sensitive_info)
                ''')
                files_with_sensitive_info = cursor.fetchone()[0] or 0
                
                # Get average sensitivity score
                cursor.execute('SELECT AVG(sensitivity_score) FROM content_analysis')
                avg_sensitivity = cursor.fetchone()[0] or 0.0
                
                # Get most common sensitive info types
                cursor.execute('''
                    SELECT json_extract(value, '$.type') as info_type, COUNT(*) as count
                    FROM content_analysis, json_each(content_analysis.sensitive_info)
                    WHERE json_extract(value, '$.type') IS NOT NULL
                    GROUP BY info_type
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                common_sensitive_info = {row[0]: row[1] for row in cursor.fetchall()}
                
                return {
                    'total_files_analyzed': total_files,
                    'files_by_type': files_by_type,
                    'files_with_sensitive_info': files_with_sensitive_info,
                    'avg_sensitivity_score': round(avg_sensitivity, 2),
                    'common_sensitive_info': common_sensitive_info
                }
                
        except Exception as e:
            logger.error(f"Error getting analysis stats: {e}")
            return {}
    
    def export_analysis(
        self, 
        output_format: str = 'json', 
        output_file: Optional[Union[str, Path]] = None,
        include_sensitive: bool = False
    ) -> Optional[str]:
        """
        Export analysis results to a file or return as string.
        
        Args:
            output_format: Output format ('json', 'csv', 'html')
            output_file: Path to output file (None to return as string)
            include_sensitive: If True, include sensitive information in the export
            
        Returns:
            Exported data as string if output_file is None, else None
        """
        if not self.db_path:
            return None
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all analysis results
                cursor.execute('''
                    SELECT file_path, content_type, mime_type, file_size, 
                           sensitive_info, keywords, entities, checksum,
                           metadata, language, is_encrypted, contains_pii,
                           sensitivity_score, processing_time, error
                    FROM content_analysis
                    ORDER BY sensitivity_score DESC, file_path
                ''')
                
                rows = cursor.fetchall()
                
                if output_format.lower() == 'json':
                    # Convert to list of dicts
                    results = []
                    for row in rows:
                        result = {
                            'file_path': row[0],
                            'content_type': row[1],
                            'mime_type': row[2],
                            'file_size': row[3],
                            'sensitive_info': json.loads(row[4]) if row[4] and include_sensitive else [],
                            'keywords': json.loads(row[5]) if row[5] else [],
                            'entities': json.loads(row[6]) if row[6] else [],
                            'checksum': row[7],
                            'metadata': json.loads(row[8]) if row[8] else {},
                            'language': row[9],
                            'is_encrypted': bool(row[10]),
                            'contains_pii': bool(row[11]),
                            'sensitivity_score': row[12],
                            'processing_time': row[13],
                            'error': row[14]
                        }
                        
                        # Redact sensitive info if needed
                        if not include_sensitive and result['sensitive_info']:
                            result['sensitive_info_count'] = len(result['sensitive_info'])
                            result['sensitive_info'] = []
                            
                        results.append(result)
                    
                    json_data = json.dumps(results, indent=2, default=str)
                    
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(json_data)
                        return None
                    return json_data
                    
                elif output_format.lower() == 'csv':
                    # Create CSV output
                    import csv
                    from io import StringIO
                    
                    output = StringIO()
                    writer = csv.writer(output)
                    
                    # Write header
                    header = [
                        'file_path', 'content_type', 'mime_type', 'file_size',
                        'sensitive_info_count', 'keywords_count', 'entities_count',
                        'is_encrypted', 'contains_pii', 'sensitivity_score',
                        'processing_time', 'error'
                    ]
                    
                    if include_sensitive:
                        header.insert(4, 'sensitive_info')
                    
                    writer.writerow(header)
                    
                    # Write data rows
                    for row in rows:
                        sensitive_info = json.loads(row[4]) if row[4] else []
                        keywords = json.loads(row[5]) if row[5] else []
                        entities = json.loads(row[6]) if row[6] else []
                        
                        row_data = [
                            row[0],  # file_path
                            row[1],  # content_type
                            row[2],  # mime_type
                            row[3],  # file_size
                            len(sensitive_info),  # sensitive_info_count
                            len(keywords),  # keywords_count
                            len(entities),  # entities_count
                            bool(row[10]),  # is_encrypted
                            bool(row[11]),  # contains_pii
                            row[12],  # sensitivity_score
                            row[13],  # processing_time
                            row[14] or ''  # error
                        ]
                        
                        if include_sensitive:
                            row_data.insert(4, json.dumps(sensitive_info))
                        
                        writer.writerow(row_data)
                    
                    csv_data = output.getvalue()
                    
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(csv_data)
                        return None
                    return csv_data
                    
                elif output_format.lower() == 'html':
                    # Create HTML report
                    from datetime import datetime
                    
                    html = []
                    html.append("""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Content Analysis Report</title>
                        <style>
                            body { 
                                font-family: Arial, sans-serif; 
                                line-height: 1.6; 
                                margin: 0; 
                                padding: 20px;
                                color: #333;
                            }
                            h1 { 
                                color: #2c3e50; 
                                border-bottom: 2px solid #3498db;
                                padding-bottom: 10px;
                            }
                            h2 {
                                color: #2980b9;
                                margin-top: 30px;
                            }
                            table {
                                width: 100%; 
                                border-collapse: collapse; 
                                margin: 20px 0;
                                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            }
                            th, td { 
                                border: 1px solid #ddd; 
                                padding: 12px; 
                                text-align: left; 
                            }
                            th { 
                                background-color: #f2f2f2; 
                                font-weight: bold;
                                position: sticky;
                                top: 0;
                            }
                            tr:nth-child(even) { 
                                background-color: #f9f9f9; 
                            }
                            tr:hover { 
                                background-color: #f1f1f1; 
                            }
                            .risk-high { 
                                background-color: #ffdddd; 
                            }
                            .risk-medium { 
                                background-color: #fff3cd; 
                            }
                            .risk-low { 
                                background-color: #d4edda; 
                            }
                            .summary-card {
                                background: #f8f9fa;
                                border-radius: 5px;
                                padding: 15px;
                                margin: 15px 0;
                                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            }
                            .summary-grid {
                                display: grid;
                                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                                gap: 15px;
                                margin: 20px 0;
                            }
                            .summary-item {
                                background: white;
                                padding: 15px;
                                border-radius: 5px;
                                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                                text-align: center;
                            }
                            .summary-item h3 {
                                margin-top: 0;
                                color: #2c3e50;
                            }
                            .summary-item .value {
                                font-size: 24px;
                                font-weight: bold;
                                color: #2980b9;
                                margin: 10px 0;
                            }
                            .footer {
                                margin-top: 30px;
                                text-align: center;
                                color: #7f8c8d;
                                font-size: 0.9em;
                            }
                            @media (max-width: 768px) {
                                .summary-grid {
                                    grid-template-columns: 1fr;
                                }
                            }
                        </style>
                    </head>
                    <body>
                        <h1>Content Analysis Report</h1>
                        <p>Generated on: {}</p>
                        <p>Total files analyzed: {}</p>
                    """.format(
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        len(rows)
                    ))
                    
                    # Add summary section
                    stats = self.get_analysis_stats()
                    if stats:
                        html.append('<div class="summary-card">')
                        html.append('<h2>Summary</h2>')
                        html.append('<div class="summary-grid">')
                        
                        # Total files
                        html.append('''
                            <div class="summary-item">
                                <h3>Total Files</h3>
                                <div class="value">{}</div>
                            </div>
                        '''.format(stats['total_files_analyzed']))
                        
                        # Files with sensitive info
                        html.append('''
                            <div class="summary-item">
                                <h3>Files with Sensitive Info</h3>
                                <div class="value">{}</div>
                                <div>{}% of total</div>
                            </div>
                        '''.format(
                            stats['files_with_sensitive_info'],
                            round((stats['files_with_sensitive_info'] / stats['total_files_analyzed'] * 100) if stats['total_files_analyzed'] > 0 else 0, 1)
                        ))
                        
                        # Average sensitivity score
                        html.append('''
                            <div class="summary-item">
                                <h3>Avg. Sensitivity</h3>
                                <div class="value">{}/10</div>
                                <div>{}</div>
                            </div>
                        '''.format(
                            stats['avg_sensitivity_score'],
                            self._get_risk_level(stats['avg_sensitivity_score']).title()
                        ))
                        
                        # Files by type
                        html.append('''
                            <div class="summary-item">
                                <h3>Files by Type</h3>
                                <div class="value">{}</div>
                                <div>unique types</div>
                            </div>
                        '''.format(len(stats['files_by_type'])))
                        
                        html.append('</div>')  # Close summary-grid
                        
                        # Common sensitive info types
                        if stats.get('common_sensitive_info'):
                            html.append('<h3>Common Sensitive Information</h3>')
                            html.append('<ul>')
                            for info_type, count in stats['common_sensitive_info'].items():
                                html.append(f'<li>{info_type}: {count} occurrences</li>')
                            html.append('</ul>')
                        
                        html.append('</div>')  # Close summary-card
                    
                    # Add detailed results table
                    html.append('<h2>Detailed Results</h2>')
                    html.append('<div style="overflow-x:auto;">')
                    html.append('''
                        <table>
                            <thead>
                                <tr>
                                    <th>File</th>
                                    <th>Type</th>
                                    <th>Size</th>
                                    <th>Sensitive Info</th>
                                    <th>Risk</th>
                                    <th>Processing Time</th>
                                    <th>Error</th>
                                </tr>
                            </thead>
                            <tbody>
                    ''')
                    
                    for row in rows:
                        sensitive_info = json.loads(row[4]) if row[4] else []
                        risk_level = 'high' if row[12] >= 7 else 'medium' if row[12] >= 4 else 'low'
                        
                        html.append(f'''
                            <tr class="risk-{risk_level}">
                                <td>{row[0]}</td>
                                <td>{row[1]}</td>
                                <td>{self._format_file_size(row[3])}</td>
                                <td>{len(sensitive_info)} items</td>
                                <td>{risk_level.title()} ({row[12]}/10)</td>
                                <td>{f'{row[13]:.2f}s' if row[13] is not None else 'N/A'}</td>
                                <td>{row[14] or ''}</td>
                            </tr>
                        ''')
                        
                        # Add sensitive info details if enabled
                        if include_sensitive and sensitive_info:
                            html.append(f'''
                                <tr>
                                    <td colspan="7" style="padding: 0;">
                                        <div style="margin: 5px 15px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                            <strong>Sensitive Information:</strong>
                                            <ul>
                            ''')
                            
                            for info in sensitive_info:
                                html.append(f'''
                                    <li>
                                        <strong>{info.get('type', 'Unknown')}</strong>: 
                                        {self._truncate_text(str(info.get('value', '')), 100)}<br>
                                        <small>Context: {self._truncate_text(info.get('context', ''), 150)}</small>
                                    </li>
                                ''')
                            
                            html.append('''
                                            </ul>
                                        </div>
                                    </td>
                                </tr>
                            ''')
                    
                    html.append('''
                            </tbody>
                        </table>
                    </div>
                    <div class="footer">
                        <p>Report generated by VAULT Content Analyzer</p>
                    </div>
                    </body>
                    </html>
                    ''')
                    
                    html_content = '\n'.join(html)
                    
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        return None
                    return html_content
                    
                else:
                    raise ValueError(f"Unsupported output format: {output_format}")
                
        except Exception as e:
            logger.error(f"Error exporting analysis: {e}")
            raise
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to a maximum length, adding ellipsis if needed."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + '...'
    
    def _get_risk_level(self, score: float) -> str:
        """Convert sensitivity score to risk level."""
        if score >= 7:
            return 'high'
        elif score >= 4:
            return 'medium'
        return 'low'
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def cleanup_old_analyses(self, days_old: int = 30) -> int:
        """
        Remove analysis records for files that no longer exist or are older than specified days.
        
        Args:
            days_old: Remove analyses older than this many days
            
        Returns:
            Number of records removed
        """
        if not self.db_path:
            return 0
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find files that no longer exist
                cursor.execute('SELECT file_path FROM content_analysis')
                files_to_check = [row[0] for row in cursor.fetchall()]
                
                # Check which files don't exist anymore
                missing_files = [f for f in files_to_check if not os.path.exists(f)]
                
                # Delete records for missing files
                if missing_files:
                    placeholders = ','.join('?' * len(missing_files))
                    cursor.execute(
                        f'DELETE FROM content_analysis WHERE file_path IN ({placeholders})',
                        missing_files
                    )
                    deleted_count = cursor.rowcount
                else:
                    deleted_count = 0
                
                # Delete old records
                cursor.execute('''
                    DELETE FROM content_analysis 
                    WHERE last_analyzed < datetime('now', ?)
                ''', (f'-{days_old} days',))
                
                old_count = cursor.rowcount
                
                # Clean up orphaned history records
                cursor.execute('''
                    DELETE FROM analysis_history
                    WHERE file_path NOT IN (SELECT file_path FROM content_analysis)
                ''')
                
                conn.commit()
                return deleted_count + old_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old analyses: {e}")
            return 0


# Register custom pipeline component for sensitive info detection
@Language.component("sensitive_info")
def sensitive_info_component(doc):
    """Custom pipeline component for detecting sensitive information."""
    # This is a placeholder - the actual detection is done in _find_sensitive_info
    # using the patterns defined in _init_sensitive_patterns
    return doc


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze files for sensitive information.')
    parser.add_argument('path', help='File or directory to analyze')
    parser.add_argument('--db', help='Path to SQLite database for caching (optional)')
    parser.add_argument('--format', choices=['json', 'csv', 'html'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--output', help='Output file (default: print to stdout)')
    parser.add_argument('--include-sensitive', action='store_true',
                       help='Include sensitive information in the output')
    parser.add_argument('--recursive', '-r', action='store_true',
                       help='Recursively analyze directories')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Force re-analysis of all files')
    parser.add_argument('--cleanup-days', type=int, default=0,
                       help='Clean up analyses older than N days (0 to disable)')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = ContentAnalyzer(db_path=args.db)
    
    # Clean up old analyses if requested
    if args.cleanup_days > 0:
        removed = analyzer.cleanup_old_analyses(days_old=args.cleanup_days)
        print(f"Cleaned up {removed} old analysis records")
    
    # Check if path exists
    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)
    
    # Analyze file or directory
    try:
        if path.is_file():
            result = analyzer.analyze_file(path, force=args.force)
            results = {str(path): result}
        else:
            def progress_callback(current, total, current_file):
                print(f"Analyzing {current}/{total}: {current_file}", end='\r')
            
            results = analyzer.analyze_directory(
                path,
                recursive=args.recursive,
                force=args.force,
                progress_callback=progress_callback
            )
            print()  # New line after progress
        
        # Export results
        output = analyzer.export_analysis(
            output_format=args.format,
            output_file=args.output,
            include_sensitive=args.include_sensitive
        )
        
        if output:
            print(output)
        
        # Print summary
        stats = analyzer.get_analysis_stats()
        if stats:
            print("\nAnalysis Summary:")
            print(f"  Total files analyzed: {stats['total_files_analyzed']}")
            print(f"  Files with sensitive info: {stats['files_with_sensitive_info']}")
            print(f"  Average sensitivity score: {stats['avg_sensitivity_score']:.1f}/10")
            
            if stats['common_sensitive_info']:
                print("\nCommon sensitive information types:")
                for info_type, count in stats['common_sensitive_info'].items():
                    print(f"  - {info_type}: {count} occurrences")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        # Print error message and exit with non-zero status
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    def export_analysis(
        self, 
        output_format: str = 'json', 
        output_file: Optional[Union[str, Path]] = None
    ) -> Optional[str]:
        """
        Export analysis results to a file or return as string.
        
        Args:
            output_format: Output format ('json', 'csv', 'html')
            output_file: Path to output file (None to return as string)
            
        Returns:
            Exported data as string if output_file is None, else None
        """
        if not self.db_path:
            return None
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all analysis results
                cursor.execute('''
                    SELECT file_path, content_type, mime_type, file_size, 
                           sensitive_info, keywords, entities, checksum,
                           metadata, language, is_encrypted, contains_pii,
                           sensitivity_score, processing_time, error
                    FROM content_analysis
                    ORDER BY sensitivity_score DESC, file_path
                ''')
                
                rows = cursor.fetchall()
                
                if output_format.lower() == 'json':
                    # Convert to list of dicts
                    results = []
                    for row in rows:
                        results.append({
                            'file_path': row[0],
                            'content_type': row[1],
                            'mime_type': row[2],
                            'file_size': row[3],
                            'sensitive_info': json.loads(row[4]) if row[4] else [],
                            'keywords': json.loads(row[5]) if row[5] else [],
                            'entities': json.loads(row[6]) if row[6] else [],
                            'checksum': row[7],
                            'metadata': json.loads(row[8]) if row[8] else {},
                            'language': row[9],
                            'is_encrypted': bool(row[10]),
                            'contains_pii': bool(row[11]),
                            'sensitivity_score': row[12],
                            'processing_time': row[13],
                            'error': row[14]
                        })
                    
                    json_data = json.dumps(results, indent=2, default=str)
                    
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(json_data)
                        return None
                    return json_data
                    
                elif output_format.lower() == 'csv':
                    # Create CSV output
                    import csv
                    from io import StringIO
                    
                    output = StringIO()
                    writer = csv.writer(output)
                    
                    # Write header
                    writer.writerow([
                        'file_path', 'content_type', 'mime_type', 'file_size',
                        'sensitive_info_count', 'keywords_count', 'entities_count',
                        'is_encrypted', 'contains_pii', 'sensitivity_score',
                        'processing_time', 'error'
                    ])
                    
                    # Write data rows
                    for row in rows:
                        writer.writerow([
                            row[0],  # file_path
                            row[1],  # content_type
                            row[2],  # mime_type
                            row[3],  # file_size
                            len(json.loads(row[4])) if row[4] else 0,  # sensitive_info_count
                            len(json.loads(row[5])) if row[5] else 0,  # keywords_count
                            len(json.loads(row[6])) if row[6] else 0,  # entities_count
                            bool(row[10]),  # is_encrypted
                            bool(row[11]),  # contains_pii
                            row[12],  # sensitivity_score
                            row[13],  # processing_time
                            row[14] or ''  # error
                        ])
                    
                    csv_data = output.getvalue()
                    
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(csv_data)
                        return None
                    return csv_data
                    
                elif output_format.lower() == 'html':
                    # Create HTML report
                    from datetime import datetime
                    
                    html = ["""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Content Analysis Report</title>
                        <style>
                            body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; }
                            h1 { color: #2c3e50; }
                            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                            th { background-color: #f2f2f2; }
                            tr:nth-child(even) { background-color: #f9f9f9; }
                            .high { background-color: #ffdddd; }
                            .medium { background-color: #fff3cd; }
                            .low { background-color: #d4edda; }
                        </style>
                    </head>
                    <body>
                        <h1>Content Analysis Report</h1>
                        <p>Generated on: {}</p>
                        <p>Total files analyzed: {}</p>
                        <table>
                            <tr>
                                <th>File</th>
                                <th>Type</th>
                                <th>Size</th>
                                <th>Sensitive Info</th>
                                <th>Risk</th>
                                <th>Error</th>
                            </tr>
                    """.format(
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        len(rows)
                    )]
                    
                    for row in rows:
                        sensitive_info = json.loads(row[4]) if row[4] else []
                        risk_level = 'high' if any(info.get('sensitivity', 0) >= 3 for info in sensitive_info) else \
                                    'medium' if any(info.get('sensitivity', 0) >= 2 for info in sensitive_info) else 'low'
                        
                        html.append(f"""
                            <tr class="{risk_level}">
                                <td>{row[0]}</td>
                                <td>{row[1]}</td>
                                <td>{self._format_file_size(row[3])}</td>
                                <td>{len(sensitive_info)} items</td>
                                <td>{risk_level.title()}</td>
                                <td>{row[14] or ''}</td>
                            </tr>
                        """)
                    
                    html.append("""
                        </table>
                    </body>
                    </html>
                    """)
                    
                    html_content = '\n'.join(html)
                    
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        return None
                    return html_content
                    
                else:
                    raise ValueError(f"Unsupported output format: {output_format}")
                
        except Exception as e:
            logger.error(f"Error exporting analysis: {e}")
            raise
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def cleanup_old_analyses(self, days_old: int = 30) -> int:
        """
        Remove analysis records for files that no longer exist or are older than specified days.
        
        Args:
            days_old: Remove analyses older than this many days
            
        Returns:
            Number of records removed
        """
        if not self.db_path:
            return 0
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find files that no longer exist
                cursor.execute('SELECT file_path FROM content_analysis')
                files_to_check = [row[0] for row in cursor.fetchall()]
                
                # Check which files don't exist anymore
                missing_files = [f for f in files_to_check if not os.path.exists(f)]
                
                # Delete records for missing files
                if missing_files:
                    placeholders = ','.join('?' * len(missing_files))
                    cursor.execute(
                        f'DELETE FROM content_analysis WHERE file_path IN ({placeholders})',
                        missing_files
                    )
                    deleted_count = cursor.rowcount
                else:
                    deleted_count = 0
                
                # Delete old records
                cursor.execute('''
                    DELETE FROM content_analysis 
                    WHERE last_analyzed < datetime('now', ?)
                ''', (f'-{days_old} days',))
                
                old_count = cursor.rowcount
                
                # Clean up orphaned history records
                cursor.execute('''
                    DELETE FROM analysis_history
                    WHERE file_path NOT IN (SELECT file_path FROM content_analysis)
                ''')
                
                conn.commit()
                return deleted_count + old_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old analyses: {e}")
            return 0

    def _init_database(self):
        """Initialize the SQLite database for caching analysis results."""
        if not self.db_path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create content_analysis table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS content_analysis (
                        file_path TEXT PRIMARY KEY,
                        content_type TEXT,
                        sensitive_info TEXT,
                        keywords TEXT,
                        entities TEXT,
                        checksum TEXT,
                        metadata TEXT,
                        last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for better query performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_content_type 
                    ON content_analysis(content_type)
                ''')
                
                # Create analysis_history table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS analysis_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT,
                        analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        analysis_result TEXT,
                        FOREIGN KEY (file_path) REFERENCES content_analysis(file_path) ON DELETE CASCADE
                    )
                ''')
                
                # Create index on analysis_history for faster lookups
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_analysis_history_file_path 
                    ON analysis_history(file_path)
                ''')
                
                # Remove blockchain table if it exists (legacy)
                cursor.execute("DROP TABLE IF EXISTS blockchain")
                
                # Enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON")
                
                conn.commit()
                
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            # If there's an error, we'll continue without the database
            self.db_path = None
    
    def analyze_file(self, file_path: str) -> ContentAnalysis:
        """
        Analyze a file and return its content analysis.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            ContentAnalysis object with analysis results
        """
        file_path = str(Path(file_path).resolve())
        checksum = self._calculate_checksum(file_path)
        
        # Check cache first
        if self.db_path:
            cached = self._get_cached_analysis(file_path, checksum)
            if cached:
                return cached
        
        # Determine content type
        content_type = self._detect_content_type(file_path)
        
        # Extract text based on content type
        if content_type == ContentType.IMAGE:
            text = self._extract_text_from_image(file_path)
        elif content_type in [ContentType.DOCUMENT, ContentType.SPREADSHEET, ContentType.PRESENTATION]:
            text = self._extract_text_from_document(file_path)
        else:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            except UnicodeDecodeError:
                text = ""
        
        # Analyze text
        sensitive_info = self._find_sensitive_info(text)
        keywords = self._extract_keywords(text)
        entities = self._extract_entities(text)
        
        # Get file metadata
        metadata = self._get_file_metadata(file_path, content_type)
        
        # Create analysis result
        analysis = ContentAnalysis(
            content_type=content_type,
            sensitive_info=sensitive_info,
            keywords=keywords,
            entities=entities,
            checksum=checksum,
            metadata=metadata
        )
        
        # Cache the result
        if self.db_path:
            self._cache_analysis(file_path, analysis)
        
        return analysis
    
    def _detect_content_type(self, file_path: str) -> ContentType:
        """Detect the type of content in the file."""
        ext = Path(file_path).suffix.lower()
        
        # Image files
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
            return ContentType.IMAGE
            
        # Document files
        if ext in ['.txt', '.md', '.rtf', '.doc', '.docx', '.odt', '.pdf']:
            return ContentType.DOCUMENT
            
        # Spreadsheet files
        if ext in ['.csv', '.xls', '.xlsx', '.ods']:
            return ContentType.SPREADSHEET
            
        # Presentation files
        if ext in ['.ppt', '.pptx', '.odp']:
            return ContentType.PRESENTATION
            
        # Archive files
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return ContentType.ARCHIVE
            
        # Code files
        if ext in ['.py', '.js', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.sh', '.bat', '.ps1']:
            return ContentType.CODE
            
        return ContentType.UNKNOWN
    
    def _extract_text_from_image(self, image_path: str) -> str:
        """Extract text from an image using OCR."""
        try:
            # Preprocess image for better OCR
            image = Image.open(image_path)
            
            # Convert to grayscale
            image = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Apply slight sharpening
            image = image.filter(ImageFilter.SHARPEN)
            
            # Use pytesseract to do OCR on the image
            text = pytesseract.image_to_string(image)
            
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from image {image_path}: {e}")
            return ""
    
    def _extract_text_from_document(self, file_path: str) -> str:
        """Extract text from a document file."""
        # For now, just read as text. In a real implementation, you'd use libraries like:
        # - python-docx for .docx
        # - PyPDF2 or pdfminer for PDFs
        # - openpyxl for Excel files
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error extracting text from document {file_path}: {e}")
            return ""
    
    def _find_sensitive_info(self, text: str) -> List[Dict[str, Any]]:
        """Find sensitive information in text using regex patterns."""
        sensitive_info = []
        
        for info_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                sensitive_info.append({
                    'type': info_type,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
        
        return sensitive_info
    
    def _extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """Extract keywords from text using KeyBERT."""
        if not text.strip():
            return []
            
        try:
            # Extract keywords with KeyBERT
            keywords = self.kw_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2),
                stop_words='english',
                top_n=top_n,
                use_mmr=True,
                diversity=0.7
            )
            
            return [kw[0] for kw in keywords]
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities from text using spaCy."""
        if not text.strip():
            return []
            
        try:
            doc = self.nlp(text)
            return [
                {
                    'text': ent.text,
                    'label': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                }
                for ent in doc.ents
            ]
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _get_file_metadata(self, file_path: str, content_type: ContentType) -> Dict[str, Any]:
        """Get metadata about the file."""
        path = Path(file_path)
        stat = path.stat()
        
        metadata = {
            'size_bytes': stat.st_size,
            'created': stat.st_ctime,
            'modified': stat.st_mtime,
            'accessed': stat.st_atime,
            'file_extension': path.suffix.lower(),
            'content_type': content_type.value,
            'is_file': path.is_file(),
            'is_dir': path.is_dir(),
        }
        
        # Add EXIF data for images
        if content_type == ContentType.IMAGE:
            try:
                with Image.open(file_path) as img:
                    if hasattr(img, '_getexif') and img._getexif():
                        exif_data = {}
                        for tag, value in img._getexif().items():
                            if tag in [34665, 34853]:  # Skip thumbnail data
                                continue
                            try:
                                exif_data[str(tag)] = str(value)
                            except:
                                pass
                        metadata['exif'] = exif_data
            except Exception as e:
                logger.warning(f"Could not extract EXIF data from {file_path}: {e}")
        
        return metadata
    
    def _get_cached_analysis(self, file_path: str, checksum: str) -> Optional[ContentAnalysis]:
        """Get cached analysis for a file if it exists and is still valid."""
        if not self.db_path:
            return None
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT content_type, sensitive_info, keywords, entities, checksum, metadata
                    FROM content_analysis
                    WHERE file_path = ?
                ''', (file_path,))
                
                row = cursor.fetchone()
                if row and row[4] == checksum:  # Check if checksum matches
                    return ContentAnalysis(
                        content_type=ContentType(row[0]),
                        sensitive_info=json.loads(row[1]) if row[1] else [],
                        keywords=json.loads(row[2]) if row[2] else [],
                        entities=json.loads(row[3]) if row[3] else [],
                        checksum=row[4],
                        metadata=json.loads(row[5]) if row[5] else {}
                    )
        except Exception as e:
            logger.error(f"Error getting cached analysis: {e}")
            
        return None
    
    def _cache_analysis(self, file_path: str, analysis: ContentAnalysis) -> None:
        """Cache the analysis results in the database."""
        if not self.db_path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO content_analysis 
                    (file_path, content_type, sensitive_info, keywords, entities, checksum, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_path,
                    analysis.content_type.value,
                    json.dumps(analysis.sensitive_info) if analysis.sensitive_info else None,
                    json.dumps(analysis.keywords) if analysis.keywords else None,
                    json.dumps(analysis.entities) if analysis.entities else None,
                    analysis.checksum,
                    json.dumps(analysis.metadata) if analysis.metadata else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error caching analysis: {e}")

def ensure_sensitive_info_component(nlp: Language) -> None:
    """Add the sensitive info component to the pipeline if it's not already present."""
    if 'sensitive_info' in nlp.pipe_names:
        return
        
    # In spaCy v3, components must be added by string name after being registered via the decorator.
    # To be extremely robust, especially for frozen builds (like PyInstaller) where 
    # module-level decorators might not trigger as expected, we ensure it's registered
    # in the global Language factories right here if it's missing.
    if not hasattr(Language, 'has_factory') or not Language.has_factory('sensitive_info'):
        @Language.component('sensitive_info')
        def dynamic_sensitive_info_component(doc):
            """Custom pipeline component to detect sensitive information."""
            return doc

    # Safely insert the component before 'parser' if possible.
    try:
        if 'parser' in nlp.pipe_names:
            nlp.add_pipe('sensitive_info', before='parser')
        else:
            nlp.add_pipe('sensitive_info')
    except Exception as e:
        logger.warning(f"Failed to add 'sensitive_info' component before parser. Error: {e}")
        try:
            # Fallback to appending to the pipeline directly
            nlp.add_pipe('sensitive_info')
        except Exception:
            pass

