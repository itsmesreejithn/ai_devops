import paramiko
from app.utils.logger import logger
from app.config import Config


def read_readme(jenkins_job_name: str) -> str:
    """Read the README.md file from the workspace path."""
    ssh_client = None
    try:
        logger.info(f"Connecting to Jenkins server to fetch README.md")
        workspace_path = f"{Config.JENKINS_WORKSPACE_PATH}/{jenkins_job_name}"
        logger.info(f"Workspace path: {workspace_path}")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        username = Config.JENKINS_SSH_USERNAME
        hostname = Config.JENKINS_SSH_HOST
        
        # Connect using password authentication with IdentitiesOnly=yes
        ssh_client.connect(
            hostname=hostname,
            username=username,
            password=Config.JENKINS_SSH_PASSWORD,
            allow_agent=False,
            look_for_keys=False
        )
        
        # Check if README.md exists
        stdin, stdout, stderr = ssh_client.exec_command(f"find {workspace_path} -name 'README.md' | head -1")
        readme_path = stdout.read().decode('utf-8').strip()
        
        if not readme_path:
            logger.warning(f"No README.md found in {workspace_path}")
            return ""
        
        # Read README.md content
        stdin, stdout, stderr = ssh_client.exec_command(f"cat {readme_path}")
        readme_content = stdout.read().decode('utf-8')
        
        logger.info(f"Successfully fetched README.md")
        return readme_content
        
    except Exception as e:
        logger.error(f"Error fetching README.md: {e}")
        return ""
    finally:
        if ssh_client:
            ssh_client.close()