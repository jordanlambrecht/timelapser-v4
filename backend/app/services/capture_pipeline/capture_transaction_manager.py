#!/usr/bin/env python3
# backend/app/services/capture_pipeline/capture_transaction_manager.py
"""
Capture Transaction Manager - Ensures atomic capture operations.

Provides transaction safety for capture operations to prevent:
- Orphaned database records without files
- Orphaned files without database records
- Incomplete thumbnail generation states
- Inconsistent corruption detection records
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Protocol

from ...database.core import SyncDatabase
from ...enums import LoggerName, LogSource
from ...services.logger import get_service_logger

logger = get_service_logger(LoggerName.CAPTURE_PIPELINE, LogSource.PIPELINE)


class ImageOperationsProtocol(Protocol):
    """Protocol for image operations dependency."""

    def delete_image(self, image_id: int) -> None: ...


class FileHelpersProtocol(Protocol):
    """Protocol for file helpers dependency."""

    pass


@dataclass
class CaptureTransaction:
    """Tracks a capture transaction state."""

    camera_id: int
    timelapse_id: Optional[int] = None
    image_id: Optional[int] = None
    file_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    small_path: Optional[Path] = None
    corruption_record_id: Optional[int] = None
    rollback_actions: List[Callable] = field(default_factory=list)
    committed: bool = False

    def add_rollback_action(self, action: Callable) -> None:
        """Add an action to be executed on rollback."""
        self.rollback_actions.append(action)


class CaptureTransactionManager:
    """
    Manages atomic capture operations with automatic rollback.

    Ensures that capture operations are atomic:
    - Either complete successfully or rollback completely
    - No orphaned files or database records
    - Consistent state across all systems
    """

    def __init__(self, db: SyncDatabase, image_ops=None):
        """
        Initialize transaction manager with injected dependencies.

        Args:
            db: Synchronized database connection for atomic operations
            image_ops: Optional SyncImageOperations instance
        """
        self.db = db
        self.image_ops = image_ops or self._get_default_image_ops()

    def _get_default_image_ops(self):
        """Fallback to get SyncImageOperations singleton"""
        from ...dependencies.specialized import get_sync_image_operations

        return get_sync_image_operations()

    @contextmanager
    def capture_transaction(self, camera_id: int, timelapse_id: Optional[int] = None):
        """
        Context manager for atomic capture operations.

        Args:
            camera_id: ID of the camera being captured from
            timelapse_id: Optional timelapse ID for the capture

        Yields:
            CaptureTransaction: Transaction object to track operations

        Example:
            with transaction_manager.capture_transaction(camera_id=1) as tx:
                # Perform capture operations
                tx.file_path = capture_file
                tx.image_id = created_image.id
                # If any exception occurs, rollback is automatic
        """
        transaction = CaptureTransaction(camera_id=camera_id, timelapse_id=timelapse_id)

        try:
            logger.debug(f"Starting capture transaction for camera {camera_id}")
            yield transaction

            # If we reach here, commit the transaction
            transaction.committed = True
            logger.debug(f"Capture transaction committed for camera {camera_id}")

        except Exception as e:
            logger.warning(f"Capture transaction failed for camera {camera_id}: {e}")
            self._rollback_transaction(transaction)
            raise

        finally:
            if not transaction.committed:
                logger.warning(
                    f"Capture transaction not committed for camera {camera_id}, rolling back"
                )
                self._rollback_transaction(transaction)

    def _rollback_transaction(self, transaction: CaptureTransaction) -> None:
        """
        Rollback a failed transaction.

        Args:
            transaction: The transaction to rollback
        """
        logger.info(
            f"Rolling back capture transaction for camera {transaction.camera_id}"
        )

        # Execute custom rollback actions first (in reverse order)
        for action in reversed(transaction.rollback_actions):
            try:
                action()
            except Exception as e:
                logger.error(f"Error executing rollback action: {e}")

        # Clean up files
        self._cleanup_files(transaction)

        # Clean up database records
        self._cleanup_database_records(transaction)

    def _cleanup_files(self, transaction: CaptureTransaction) -> None:
        """Clean up any files created during the transaction."""
        files_to_remove = [
            transaction.file_path,
            transaction.thumbnail_path,
            transaction.small_path,
        ]

        for file_path in files_to_remove:
            if file_path and isinstance(file_path, (str, Path)):
                try:
                    file_path = Path(file_path)
                    if file_path.exists():
                        file_path.unlink()
                        logger.debug(f"Removed file during rollback: {file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to remove file {file_path} during rollback: {e}"
                    )

    def _cleanup_database_records(self, transaction: CaptureTransaction) -> None:
        """Clean up any database records created during the transaction."""
        try:
            # Remove image record if created
            if transaction.image_id:
                try:
                    self.image_ops.delete_image(transaction.image_id)
                    logger.debug(
                        f"Removed image record {transaction.image_id} during rollback"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to remove image record {transaction.image_id} during rollback: {e}"
                    )

            # Remove corruption record if created
            if transaction.corruption_record_id:
                try:
                    # Note: Would need corruption_ops injected if this feature is used
                    logger.debug(
                        f"Would remove corruption record {transaction.corruption_record_id} during rollback"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to remove corruption record during rollback: {e}"
                    )

        except Exception as e:
            logger.error(f"Error cleaning up database records during rollback: {e}")

    def create_file_rollback_action(self, file_path: Path) -> Callable:
        """Create a rollback action to remove a file."""

        def rollback_action():
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Rollback: removed file {file_path}")
            except Exception as e:
                logger.warning(f"Rollback: failed to remove file {file_path}: {e}")

        return rollback_action

    def create_database_rollback_action(
        self, operation: str, entity_id: int
    ) -> Callable:
        """Create a rollback action to remove a database record."""

        def rollback_action():
            try:
                if operation == "image" and entity_id:
                    self.image_ops.delete_image(entity_id)
                    logger.debug(f"Rollback: removed {operation} record {entity_id}")
            except Exception as e:
                logger.warning(
                    f"Rollback: failed to remove {operation} record {entity_id}: {e}"
                )

        return rollback_action


# Helper functions for common transaction patterns


def safe_file_operation(
    file_path: Path, operation: Callable, transaction: CaptureTransaction
):
    """
    Safely perform a file operation with automatic rollback registration.

    Args:
        file_path: Path to the file being operated on
        operation: Callable that performs the file operation
        transaction: Current transaction to register rollback with
    """
    try:
        result = operation()

        # Register rollback action to remove the file if transaction fails
        def file_rollback_action():
            if file_path.exists():
                file_path.unlink()

        transaction.add_rollback_action(file_rollback_action)

        return result

    except Exception as e:
        logger.error(f"File operation failed for {file_path}: {e}")
        raise


def safe_database_operation(
    operation: Callable,
    transaction: CaptureTransaction,
    rollback_operation: Optional[Callable] = None,
):
    """
    Safely perform a database operation with automatic rollback registration.

    Args:
        operation: Callable that performs the database operation
        transaction: Current transaction to register rollback with
        rollback_operation: Optional specific rollback operation
    """
    try:
        result = operation()

        # Register rollback action if provided
        if rollback_operation:
            transaction.add_rollback_action(rollback_operation)

        return result

    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        raise
