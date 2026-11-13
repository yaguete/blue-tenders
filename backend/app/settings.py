from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    anthropic_api_key: str = ""
    # Si hay clave, el chat usa DeepSeek. Clasificar y traducir siguen en Anthropic.
    deepseek_api_key: str = ""
    voyage_api_key: str = ""
    resend_api_key: str = ""
    resend_from: str = "Blue Tender <alerts@localhost>"
    ops_email: str = ""
    heartbeat_url: str = ""
    admin_token: str = ""
    # Clave del portal de desarrolladores de Doffin. Sin ella se usa la API interna de su web.
    doffin_api_key: str = ""
    # Se cambia por un Bearer de 24 h. Sin ella el adaptador no arranca.
    aides_territoires_api_key: str = ""
    enrich_documents: bool = False
    classify_model: str = "claude-haiku-5-5"
    extract_model: str = "claude-haiku-5-5"
    assistant_router_model: str = "claude-haiku-5-5"
    assistant_answer_model: str = "claude-sonnet-5-5"
    allow_demo_auth: bool = False
    # En falso hasta el DPA de Anthropic y la retención a cero. La demo local lo salta.
    assistant_public: bool = False
    # En falso mientras no haya cuentas. Con 1, el chat vuelve a pedir sesión.
    assistant_requires_account: bool = False
    assistant_daily_limit: int = 30
    assistant_daily_budget_usd: float = 20
    vertical: str = "blue-economy"
    verticals_dir: Path = ROOT / "config" / "verticals"
    config_dir: Path = ROOT / "config"
    data_dir: Path = ROOT / "backend" / "data"


settings = Settings()
