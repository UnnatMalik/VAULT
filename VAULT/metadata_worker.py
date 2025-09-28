import os
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, Signal

class MetadataWorker(QObject):
    log_signal = Signal(str)
    result_signal = Signal(dict)
    finished_signal = Signal()

    def __init__(self, target_path: Path, logger):
        super().__init__()
        self.target_path = target_path
        self.logger = logger # Use the existing logger for consistency

    def _get_file_metadata(self, file_path: Path) -> dict:
        metadata = {}
        try:
            stat_info = file_path.stat()
            metadata["Size"] = f"{stat_info.st_size} bytes"
            metadata["Created"] = datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            metadata["Modified"] = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            metadata["Accessed"] = datetime.fromtimestamp(stat_info.st_atime).strftime('%Y-%m-%d %H:%M:%S')
            metadata["Permissions"] = oct(stat_info.st_mode)[-3:]
            metadata["Owner UID"] = stat_info.st_uid
            metadata["Group GID"] = stat_info.st_gid

            # Placeholder for more advanced metadata extraction (e.g., EXIF, document properties)
            if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                metadata["Image Metadata"] = "(Advanced image metadata extraction not yet implemented)"
            elif file_path.suffix.lower() in ['.doc', '.docx', '.pdf']:
                metadata["Document Metadata"] = "(Advanced document metadata extraction not yet implemented)"

        except Exception as e:
            self.log_signal.emit(f"[ERR] Could not get metadata for {file_path}: {e}")
        return metadata

    def run(self):
        all_metadata = {}
        if not self.target_path.exists():
            self.log_signal.emit(f"[ERR] Target does not exist: {self.target_path}")
            self.result_signal.emit({})
            self.finished_signal.emit()
            return

        if self.target_path.is_file():
            self.log_signal.emit(f"[i] Analyzing file: {self.target_path}")
            all_metadata[self.target_path.as_posix()] = self._get_file_metadata(self.target_path)

        elif self.target_path.is_dir():
            self.log_signal.emit(f"[i] Analyzing directory (recursive): {self.target_path}")
            for root, _, files in os.walk(self.target_path):
                for fname in files:
                    file_path = Path(root) / fname
                    self.log_signal.emit(f"[i] Processing file: {file_path}")
                    all_metadata[file_path.as_posix()] = self._get_file_metadata(file_path)
        else:
            self.log_signal.emit(f"[ERR] Unsupported target type: {self.target_path}")

        self.result_signal.emit(all_metadata)
        self.finished_signal.emit() 