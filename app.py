
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

# =====================================================
# CONFIGURAÇÕES INICIAIS
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    dotenv_path=BASE_DIR / ".env",
    override=True
)


def create_app():

    app = Flask(__name__)

    app.secret_key = os.environ.get(
        "FLASK_SECRET_KEY",
        ""
    )

    # =================================================
    # VALIDAR VARIÁVEIS DE AMBIENTE
    # =================================================

    required = [
        "FLASK_SECRET_KEY",
        "DATABASE_URL"
    ]

    missing = [
        key for key in required
        if not os.environ.get(key)
    ]

    if missing:
        raise RuntimeError(
            "Variáveis não configuradas: "
            + ", ".join(missing)
        )

    # =================================================
    # CONFIGURAÇÕES DE SESSÃO
    # =================================================

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax"
    )

    # =================================================
    # IMPORTAR BLUEPRINTS
    # =================================================

    from routes.auth import auth_bp
    from routes.contratos import contratos_bp
    from routes.gestantes import gestantes_bp
    from routes.admin import admin_bp

    from services.database import criar_tabelas_portal

    # =================================================
    # INICIALIZAR TABELAS
    # =================================================

    criar_tabelas_portal()

    # =================================================
    # REGISTRAR BLUEPRINTS
    # =================================================

    # Autenticação e página inicial
    app.register_blueprint(auth_bp)

    # Contratos Determinados
    app.register_blueprint(
        contratos_bp,
        url_prefix="/contratos"
    )

    # Gestantes
    app.register_blueprint(
        gestantes_bp,
        url_prefix="/gestantes"
    )

    # Administração ROOT
    app.register_blueprint(
        admin_bp,
        url_prefix="/admin"
    )

    return app


# =====================================================
# INICIALIZAR APLICAÇÃO
# =====================================================

app = create_app()


if __name__ == "__main__":

    app.run(
        host="127.0.0.2",
        port=2000,
        debug=False
    )
