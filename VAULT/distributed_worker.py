import os
import hashlib
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, asdict
import json
import time
from cryptography.fernet import Fernet
import psutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ChunkInfo:
    """Information about a chunk of data to be processed."""
    chunk_id: str
    target_path: str
    start_pos: int
    chunk_size: int
    total_size: int
    pass_num: int
    total_passes: int

@dataclass
class WorkerResult:
    """Result of processing a chunk."""
    chunk_id: str
    success: bool
    error: Optional[str] = None
    checksum: Optional[str] = None
    bytes_processed: int = 0
    processing_time: float = 0.0

def generate_chunk_id(target_path: str, start_pos: int, pass_num: int) -> str:
    """Generate a unique ID for a chunk."""
    return hashlib.sha256(f"{target_path}:{start_pos}:{pass_num}".encode()).hexdigest()

def secure_overwrite_chunk(chunk_info: ChunkInfo, encryption_key: bytes = None) -> WorkerResult:
    """Securely overwrite a chunk of a file."""
    start_time = time.time()
    result = WorkerResult(
        chunk_id=chunk_info.chunk_id,
        success=False,
        bytes_processed=0
    )
    
    try:
        chunk_size = min(chunk_info.chunk_size, chunk_info.total_size - chunk_info.start_pos)
        if chunk_size <= 0:
            result.error = "Invalid chunk size or position"
            return result
            
        # Generate random data for overwriting
        rng = os.urandom
        if encryption_key:
            f = Fernet(encryption_key)
            rng = lambda size: f.encrypt(os.urandom(size))
        
        # Process the chunk
        with open(chunk_info.target_path, 'r+b') as f:
            f.seek(chunk_info.start_pos)
            chunk_data = rng(chunk_size)
            f.write(chunk_data)
            f.flush()
            os.fsync(f.fileno())
        
        # Calculate checksum of the written data
        checksum = hashlib.sha256(chunk_data).hexdigest()
        
        result.success = True
        result.checksum = checksum
        result.bytes_processed = chunk_size
        result.processing_time = time.time() - start_time
        
    except Exception as e:
        result.error = str(e)
        logger.error(f"Error processing chunk {chunk_info.chunk_id}: {e}")
    
    return result

def worker_process(task_queue: mp.Queue, result_queue: mp.Queue, worker_id: int, encryption_key: bytes = None):
    """Worker process that processes chunks from the task queue."""
    logger.info(f"Worker {worker_id} started")
    
    try:
        while True:
            # Get a task from the queue
            task_data = task_queue.get()
            
            # Check for shutdown signal
            if task_data is None:
                logger.info(f"Worker {worker_id} received shutdown signal")
                break
                
            # Process the chunk
            chunk_info = ChunkInfo(**task_data)
            logger.debug(f"Worker {worker_id} processing chunk {chunk_info.chunk_id}")
            
            result = secure_overwrite_chunk(chunk_info, encryption_key)
            
            # Put the result in the result queue
            result_queue.put(asdict(result))
            
    except Exception as e:
        logger.error(f"Worker {worker_id} encountered an error: {e}")
    finally:
        logger.info(f"Worker {worker_id} shutting down")

class DistributedWipeManager:
    """Manages distributed secure wipe operations."""
    
    def __init__(self, num_workers: int = None, chunk_size: int = 1024 * 1024):  # 1MB chunks by default
        self.num_workers = num_workers or max(1, mp.cpu_count() - 1)
        self.chunk_size = chunk_size
        self.workers = []
        self.task_queue = mp.Queue()
        self.result_queue = mp.Queue()
        self.encryption_key = Fernet.generate_key()
        self.active_tasks = {}
        self.completed_chunks = {}
        self.lock = mp.Lock()
        
    def start_workers(self):
        """Start worker processes."""
        for i in range(self.num_workers):
            p = mp.Process(
                target=worker_process,
                args=(self.task_queue, self.result_queue, i, self.encryption_key)
            )
            p.daemon = True
            p.start()
            self.workers.append(p)
        
        logger.info(f"Started {self.num_workers} worker processes")
    
    def stop_workers(self):
        """Stop all worker processes."""
        logger.info("Stopping worker processes...")
        for _ in self.workers:
            self.task_queue.put(None)  # Send shutdown signal
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
        
        self.workers = []
        logger.info("All worker processes stopped")
    
    def queue_file_wipe(self, file_path: str, passes: int = 3) -> str:
        """Queue a file for secure wiping."""
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        task_id = hashlib.sha256(f"{file_path}:{time.time()}".encode()).hexdigest()
        self.active_tasks[task_id] = {
            'file_path': file_path,
            'total_chunks': 0,
            'completed_chunks': 0,
            'passes': passes,
            'current_pass': 0,
            'total_size': file_size,
            'processed_size': 0,
            'start_time': time.time(),
            'status': 'queued',
            'chunks': {}
        }
        
        # Queue chunks for the first pass
        self._queue_chunks_for_pass(task_id, 0)
        
        return task_id
    
    def _queue_chunks_for_pass(self, task_id: str, pass_num: int):
        """Queue chunks for a specific pass."""
        task = self.active_tasks[task_id]
        task['current_pass'] = pass_num
        task['status'] = f'pass_{pass_num + 1}'  # 0-indexed internally, 1-indexed for display
        
        file_size = task['total_size']
        chunks = []
        
        # Create chunks
        for start_pos in range(0, file_size, self.chunk_size):
            chunk_id = generate_chunk_id(task['file_path'], start_pos, pass_num)
            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                target_path=task['file_path'],
                start_pos=start_pos,
                chunk_size=self.chunk_size,
                total_size=file_size,
                pass_num=pass_num,
                total_passes=task['passes']
            )
            chunks.append(chunk_info)
            
            # Store chunk info for verification
            with self.lock:
                task['chunks'][chunk_id] = {
                    'status': 'queued',
                    'start_pos': start_pos,
                    'size': min(self.chunk_size, file_size - start_pos),
                    'pass_num': pass_num
                }
        
        # Update task info
        task['total_chunks'] = len(chunks)
        task['completed_chunks'] = 0
        
        # Queue chunks
        for chunk in chunks:
            self.task_queue.put(asdict(chunk))
    
    def process_results(self, timeout: float = 0.1) -> Dict:
        """Process results from worker processes."""
        results = {}
        
        # Process all available results
        while True:
            try:
                result = self.result_queue.get(timeout=timeout)
                chunk_id = result['chunk_id']
                
                # Find which task this chunk belongs to
                task_id = None
                for tid, task in self.active_tasks.items():
                    if chunk_id in task['chunks']:
                        task_id = tid
                        break
                
                if task_id is None:
                    logger.warning(f"Received result for unknown chunk: {chunk_id}")
                    continue
                
                # Update task and chunk status
                with self.lock:
                    task = self.active_tasks[task_id]
                    task['chunks'][chunk_id].update({
                        'status': 'completed' if result['success'] else 'failed',
                        'error': result.get('error'),
                        'checksum': result.get('checksum'),
                        'processing_time': result.get('processing_time', 0)
                    })
                    
                    if result['success']:
                        task['completed_chunks'] += 1
                        task['processed_size'] += result['bytes_processed']
                        
                        # If all chunks for this pass are done, queue next pass or complete
                        if task['completed_chunks'] >= task['total_chunks']:
                            next_pass = task['current_pass'] + 1
                            if next_pass < task['passes']:
                                self._queue_chunks_for_pass(task_id, next_pass)
                            else:
                                task['status'] = 'completed'
                                task['end_time'] = time.time()
                                task['total_time'] = task['end_time'] - task['start_time']
                                results[task_id] = task
                                del self.active_tasks[task_id]
                    else:
                        task['status'] = 'error'
                        task['last_error'] = result.get('error')
                        results[task_id] = task
                        del self.active_tasks[task_id]
                        
            except Exception as e:
                break
        
        return results
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get the status of a specific task."""
        return self.active_tasks.get(task_id)
    
    def get_all_task_statuses(self) -> Dict[str, Dict]:
        """Get status of all active tasks."""
        return self.active_tasks.copy()
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self.active_tasks:
            # We can't actually stop in-progress chunks, but we can prevent new ones
            with self.lock:
                self.active_tasks[task_id]['status'] = 'cancelled'
                # Remove from active tasks but keep in completed for reference
                task = self.active_tasks.pop(task_id)
                self.completed_chunks[task_id] = task
            return True
        return False

    def __enter__(self):
        self.start_workers()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_workers()

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file_to_wipe> [passes=3] [chunk_size_mb=1]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    passes = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    chunk_size_mb = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    # Initialize distributed wipe manager
    with DistributedWipeManager(chunk_size=chunk_size_mb * 1024 * 1024) as manager:
        # Start wiping the file
        task_id = manager.queue_file_wipe(file_path, passes=passes)
        print(f"Started wipe task {task_id} for {file_path}")
        
        try:
            while True:
                # Process results
                results = manager.process_results(timeout=1.0)
                
                # Print status
                task = manager.get_task_status(task_id)
                if not task:
                    print("Task completed or not found")
                    break
                    
                progress = (task['processed_size'] / (task['total_size'] * task['passes'])) * 100
                print(f"\rProgress: {progress:.1f}% | "
                      f"Pass {task['current_pass'] + 1}/{task['passes']} | "
                      f"Speed: {task['processed_size'] / (time.time() - task['start_time'] + 1e-6) / (1024*1024):.1f} MB/s", 
                      end='', flush=True)
                
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
            manager.cancel_task(task_id)
        
        print("\nDone.")
