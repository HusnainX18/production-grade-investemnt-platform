import os
from dotenv import dotenv_values
from airflow.providers.docker.operators.docker import DockerOperator

# Load env variables from the mounted host project root
ENV_FILE_PATH = "/usr/app/.env"
env_vars = {}

if os.path.exists(ENV_FILE_PATH):
    env_vars = dotenv_values(ENV_FILE_PATH)
else:
    # Fallback to os.environ if running outside typical container layout
    env_vars = dict(os.environ)

# Host path of the project mounted to the containers. 
# Allow overriding via env, default to the default workspace path.
HOST_PROJECT_DIR = env_vars.get(
    "HOST_PROJECT_DIR", 
    "C:/Users/Husnain/.gemini/antigravity/scratch/investment-platform"
)

# Convert dictionary values to strings for DockerOperator environment block
DOCKER_ENV = {str(k): str(v) for k, v in env_vars.items() if v is not None}

from docker.types import Mount

def create_processing_task(task_id: str, script_path: str, dag) -> DockerOperator:
    """Helper function to create a DockerOperator task running a script in the processing container."""
    return DockerOperator(
        task_id=task_id,
        image="dbt_project-processing:latest",
        command=script_path,
        api_version="auto",
        auto_remove="success",  # Remove container upon successful execution
        network_mode="bridge",
        mounts=[
            Mount(source=HOST_PROJECT_DIR, target="/usr/app", type="bind")
        ],
        entrypoint=["python"],  # Override pre-baked ENTRYPOINT ["dbt"] in Dockerfile
        mount_tmp_dir=False,   # Disable mounting tmp dir to bypass Docker-in-Docker path mismatches
        working_dir="/usr/app",
        environment=DOCKER_ENV,
        dag=dag,
    )


def create_dbt_task(task_id: str, dbt_command: str, dag) -> DockerOperator:
    """Helper function to create a DockerOperator task running dbt in the dbt container."""
    return DockerOperator(
        task_id=task_id,
        image="dbt_project-dbt:latest",
        command=dbt_command,
        api_version="auto",
        auto_remove="success",  # Remove container upon successful execution
        network_mode="bridge",
        mounts=[
            Mount(source=HOST_PROJECT_DIR, target="/usr/app", type="bind")
        ],
        entrypoint=["dbt"],     # Override pre-baked ENTRYPOINT ["dbt"] in Dockerfile
        mount_tmp_dir=False,   # Disable mounting tmp dir to bypass Docker-in-Docker path mismatches
        working_dir="/usr/app/dbt_project",
        environment=DOCKER_ENV,
        dag=dag,
    )
