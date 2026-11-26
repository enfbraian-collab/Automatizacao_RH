
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from services.database import engine


BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_ETL = BASE_DIR / "APP" / "Transformacao.py"

LOCK_ID = 83621402


class ETLJaEmExecucao(Exception):
    pass


def executar_etl_contratos():

    if not SCRIPT_ETL.is_file():
        raise FileNotFoundError(
            f"Script não encontrado: {SCRIPT_ETL}"
        )

    # Impede cargas simultâneas,
    # inclusive entre workers do Gunicorn.
    with engine.connect() as conn:

        bloqueado = conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": LOCK_ID}
        ).scalar()

        if not bloqueado:
            raise ETLJaEmExecucao()

        try:

            # Copiar variáveis de ambiente
            ambiente = os.environ.copy()

            # Forçar UTF-8 no processo Python
            ambiente["PYTHONIOENCODING"] = "utf-8"

            # Executar script de transformação
            resultado = subprocess.run(
                [sys.executable, str(SCRIPT_ETL)],
                cwd=str(SCRIPT_ETL.parent),
                env=ambiente,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                check=False
            )

            # Verificar se ocorreu erro
            if resultado.returncode != 0:

                raise RuntimeError(
                    f"ETL retornou código {resultado.returncode}: "
                    f"{resultado.stderr[-2000:]}"
                )

        finally:

            # Liberar bloqueio PostgreSQL
            conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": LOCK_ID}
            )
