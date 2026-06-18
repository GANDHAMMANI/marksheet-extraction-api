from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str
    groq_model_name: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    nvidia_api_key: str
    nvidia_model_name: str = "minimaxai/minimax-m3"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    auth_username: str
    auth_password: str

    max_file_size_mb: int = 10
    allowed_content_types: list[str] = ["image/jpeg", "image/png", "image/webp", "application/pdf"]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()