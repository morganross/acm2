"""
GitHub Input Service.

Fetches files from GitHub repositories for use as input documents.
Supports both individual files and folder paths (fetches all .md files in folder).
"""
import base64
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.repositories import GitHubConnectionRepository, ContentRepository
from app.infra.db.models.content import ContentType


logger = logging.getLogger(__name__)


@dataclass
class FetchedFile:
    """Represents a file fetched from GitHub."""
    path: str
    name: str
    content: str
    size: int


@dataclass
class GitHubFetchResult:
    """Result of fetching files from GitHub."""
    success: bool
    files: List[FetchedFile]
    document_ids: List[str]  # IDs of created Content items
    error: Optional[str] = None


class GitHubInputService:
    """
    Service for fetching input documents from GitHub.
    
    Handles:
    - Single file fetching
    - Folder fetching (recursively gets all text files)
    - Importing fetched files to Content Library as INPUT_DOCUMENT
    """
    
    def __init__(self, db: AsyncSession, user_uuid: str):
        self.db = db
        self.user_uuid = user_uuid
        self.gh_repo = GitHubConnectionRepository(db, user_uuid=user_uuid)
        self.content_repo = ContentRepository(db, user_uuid=user_uuid)
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a GitHub token."""
        try:
            decoded = base64.b64decode(encrypted_token).decode()
            if decoded.startswith("enc:"):
                return decoded[4:]
            return decoded
        except Exception:
            # Fallback: maybe it's not encrypted
            return encrypted_token
    
    async def _get_github_client(self, connection_id: str) -> Tuple[Any, Any, str]:
        """
        Get PyGithub client and repository for a connection.
        
        Returns:
            Tuple of (Github client, Repository object, branch name)
        """
        from github import Github
        
        connection = await self.gh_repo.get_by_id(connection_id)
        if not connection:
            raise ValueError(f"GitHub connection {connection_id} not found")
        
        token = self._decrypt_token(connection.token_encrypted)
        g = Github(token)
        repository = g.get_repo(connection.repo)
        
        return g, repository, connection.branch
    
    async def fetch_file(
        self,
        connection_id: str,
        file_path: str
    ) -> FetchedFile:
        """
        Fetch a single file from GitHub.
        
        Args:
            connection_id: ID of the GitHub connection
            file_path: Path to the file in the repository
            
        Returns:
            FetchedFile with content
        """
        from github.GithubException import GithubException
        
        try:
            _, repository, branch = await self._get_github_client(connection_id)
            
            clean_path = file_path.strip("/")
            file_content = repository.get_contents(clean_path, ref=branch)
            
            if file_content.type == "dir":
                raise ValueError(f"Path {file_path} is a directory, not a file")
            
            # Decode content
            content = base64.b64decode(file_content.content).decode("utf-8")
            
            return FetchedFile(
                path=file_content.path,
                name=file_content.name,
                content=content,
                size=file_content.size,
            )
            
        except GithubException as e:
            raise ValueError(f"GitHub error fetching {file_path}: {e.data.get('message', str(e))}")
        except UnicodeDecodeError:
            raise ValueError(f"File {file_path} is not a text file")
    
    async def fetch_folder(
        self,
        connection_id: str,
        folder_path: str,
        extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> List[FetchedFile]:
        """
        Fetch all files from a folder in GitHub.
        
        Args:
            connection_id: ID of the GitHub connection
            folder_path: Path to the folder in the repository
            extensions: List of file extensions to include (e.g., [".md", ".txt"])
                       If None, includes all text files
            recursive: Whether to recursively fetch subfolders
            
        Returns:
            List of FetchedFile objects
        """
        from github.GithubException import GithubException
        
        if extensions is None:
            extensions = [".md", ".txt", ".rst", ".html"]
        
        try:
            _, repository, branch = await self._get_github_client(connection_id)
            
            clean_path = folder_path.strip("/") if folder_path != "/" else ""
            
            files: List[FetchedFile] = []
            paths_to_process = [clean_path]
            
            while paths_to_process:
                current_path = paths_to_process.pop(0)
                
                try:
                    if current_path:
                        contents = repository.get_contents(current_path, ref=branch)
                    else:
                        contents = repository.get_contents("", ref=branch)
                except GithubException:
                    logger.warning(f"Could not access path: {current_path}")
                    continue
                
                # Handle both single item and list
                if not isinstance(contents, list):
                    contents = [contents]
                
                for item in contents:
                    if item.type == "dir" and recursive:
                        paths_to_process.append(item.path)
                    elif item.type == "file":
                        # Check extension
                        has_valid_ext = any(item.name.endswith(ext) for ext in extensions)
                        if has_valid_ext:
                            try:
                                content = base64.b64decode(item.content).decode("utf-8")
                                files.append(FetchedFile(
                                    path=item.path,
                                    name=item.name,
                                    content=content,
                                    size=item.size,
                                ))
                            except (UnicodeDecodeError, AttributeError):
                                logger.warning(f"Skipping non-text file: {item.path}")
            
            return files
            
        except GithubException as e:
            raise ValueError(f"GitHub error browsing {folder_path}: {e.data.get('message', str(e))}")
    
    async def fetch_paths(
        self,
        connection_id: str,
        paths: List[str],
        extensions: Optional[List[str]] = None
    ) -> List[FetchedFile]:
        """
        Fetch multiple paths (files or folders) from GitHub.
        
        Args:
            connection_id: ID of the GitHub connection
            paths: List of file or folder paths
            extensions: File extensions to include for folders
            
        Returns:
            List of all fetched files
        """
        from github.GithubException import GithubException
        
        all_files: List[FetchedFile] = []
        
        for path in paths:
            try:
                # First, determine if it's a file or folder
                _, repository, branch = await self._get_github_client(connection_id)
                
                clean_path = path.strip("/")
                item = repository.get_contents(clean_path, ref=branch)
                
                if isinstance(item, list) or item.type == "dir":
                    # It's a folder
                    folder_files = await self.fetch_folder(
                        connection_id, path, extensions
                    )
                    all_files.extend(folder_files)
                else:
                    # It's a file
                    file = await self.fetch_file(connection_id, path)
                    all_files.append(file)
                    
            except GithubException as e:
                logger.error(f"Error fetching path {path}: {e}")
                raise ValueError(f"Failed to fetch {path}: {e.data.get('message', str(e))}")
        
        return all_files
    
    async def import_files_as_content(
        self,
        files: List[FetchedFile],
        connection_name: str,
        run_id: Optional[str] = None
    ) -> List[str]:
        """
        Import fetched files as INPUT_DOCUMENT content items.
        
        Args:
            files: List of FetchedFile objects to import
            connection_name: Name of the GitHub connection (for description)
            run_id: Optional run ID for tagging
            
        Returns:
            List of created content IDs
        """
        document_ids: List[str] = []
        
        for file in files:
            # Create tags
            tags = ["github-import", f"source:{connection_name}"]
            if run_id:
                tags.append(f"run:{run_id[:8]}")
            
            # Create content
            content = await self.content_repo.create(
                name=file.name,
                content_type=ContentType.INPUT_DOCUMENT.value,
                body=file.content,
                variables={},
                description=f"Imported from GitHub: {file.path}",
                tags=tags,
            )
            
            document_ids.append(content.id)
            logger.info(f"Imported GitHub file as content: {file.path} -> {content.id}")
        
        return document_ids
    
    async def fetch_and_import(
        self,
        connection_id: str,
        paths: List[str],
        run_id: Optional[str] = None
    ) -> GitHubFetchResult:
        """
        Fetch files from GitHub and import them as content.
        
        This is the main entry point for run creation.
        
        Args:
            connection_id: ID of the GitHub connection
            paths: List of file or folder paths to fetch
            run_id: Optional run ID for tagging
            
        Returns:
            GitHubFetchResult with document IDs
        """
        try:
            # Get connection name for description
            connection = await self.gh_repo.get_by_id(connection_id)
            if not connection:
                return GitHubFetchResult(
                    success=False,
                    files=[],
                    document_ids=[],
                    error=f"GitHub connection {connection_id} not found"
                )
            
            # Fetch all files
            logger.info(f"Fetching GitHub files from connection {connection.name}: {paths}")
            files = await self.fetch_paths(connection_id, paths)
            
            if not files:
                return GitHubFetchResult(
                    success=False,
                    files=[],
                    document_ids=[],
                    error=f"No files found at paths: {paths}"
                )
            
            logger.info(f"Fetched {len(files)} files from GitHub")
            
            # Import as content
            document_ids = await self.import_files_as_content(
                files, 
                connection.name,
                run_id
            )
            
            return GitHubFetchResult(
                success=True,
                files=files,
                document_ids=document_ids,
            )
            
        except ImportError:
            return GitHubFetchResult(
                success=False,
                files=[],
                document_ids=[],
                error="PyGithub not installed. Run: pip install PyGithub"
            )
        except Exception as e:
            logger.exception(f"Error fetching from GitHub: {e}")
            return GitHubFetchResult(
                success=False,
                files=[],
                document_ids=[],
                error=str(e)
            )
