import os
from dotenv import load_dotenv
import flyte

load_dotenv()

base_env = flyte.TaskEnvironment(
    name="base_env",
    image=flyte.Image.from_debian_base().with_requirements("requirements.txt"),
    secrets=[
        flyte.Secret(key="OPENAI_API_KEY", as_env_var="OPENAI_API_KEY"),
    ],
    # base image islightweight, doesn't need much compute
    # resources=flyte.Resources(cpu=1, mem="1Gi")
)


# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY is not None, "❌ OPENAI_API_KEY is not set!"

# Database configuration

# logging configuration