import os
import pandas as pd
from sqlalchemy import create_engine, inspect, text

DATABASE_URL = os.environ["DATABASE_URL"]
TABLE_NAME = os.environ.get("TABLE_NAME", "Automatizacao_Lidi")
DATE_COLUMN = os.environ.get("DATE_COLUMN", "Admissão")
STATUS_COLUMN = "Status Vencimento"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def get_columns():
    cols = [c["name"] for c in inspect(engine).get_columns(TABLE_NAME)]

    if DATE_COLUMN not in cols:
        raise RuntimeError(
            f"Coluna de período não encontrada: {DATE_COLUMN}"
        )

    return cols


def query_data(start, end, status, limit=None):
    cols = get_columns()

    date_col = quote_identifier(DATE_COLUMN)

    sql = (
        f"SELECT * FROM {quote_identifier(TABLE_NAME)} "
        f"WHERE {date_col} >= :inicio "
        f"AND {date_col} < (:fim + INTERVAL '1 day')"
    )

    params = {"inicio": start, "fim": end}

    if status:
        if STATUS_COLUMN not in cols:
            raise ValueError("Coluna de status não encontrada.")

        sql += f" AND {quote_identifier(STATUS_COLUMN)} = :status"
        params["status"] = status

    sql += f" ORDER BY {date_col} DESC"

    if limit is not None:
        sql += " LIMIT :limite"
        params["limite"] = limit

    return pd.read_sql_query(text(sql), engine, params=params)


def criar_tabelas_portal():
    """
    Cria as tabelas de autenticação e permissões
    no PostgreSQL, caso ainda não existam.
    """

    sql_usuarios = """
    CREATE TABLE IF NOT EXISTS portal_usuarios (
        id BIGSERIAL PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        username VARCHAR(100) NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_root BOOLEAN NOT NULL DEFAULT FALSE,
        ativo BOOLEAN NOT NULL DEFAULT TRUE,
        criado_em TIMESTAMPTZ DEFAULT NOW()
    )
    """

    sql_permissoes = """
    CREATE TABLE IF NOT EXISTS portal_permissoes (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL
            REFERENCES portal_usuarios(id)
            ON DELETE CASCADE,
        modulo VARCHAR(50) NOT NULL,
        pode_visualizar BOOLEAN NOT NULL DEFAULT FALSE,
        pode_exportar BOOLEAN NOT NULL DEFAULT FALSE,
        UNIQUE (usuario_id, modulo),
        CHECK (modulo IN ('contratos', 'gestantes'))
    )
    """

    with engine.begin() as conn:
        conn.execute(text(sql_usuarios))
        conn.execute(text(sql_permissoes))

    print("Tabelas do portal verificadas com sucesso.")


# =====================================================
# CONSULTA DO MÓDULO GESTANTES
# =====================================================

GESTANTES_TABLE = os.environ.get(
    "GESTANTES_TABLE",
    "Gestantes"
)


def get_columns_gestantes():
    return [
        coluna["name"]
        for coluna in inspect(engine).get_columns(
            GESTANTES_TABLE
        )
    ]


def query_gestantes(limit=None):

    sql = (
        f"SELECT * FROM "
        f"{quote_identifier(GESTANTES_TABLE)}"
    )

    params = {}

    if limit is not None:
        sql += " LIMIT :limite"
        params["limite"] = limit

    return pd.read_sql_query(
        text(sql),
        engine,
        params=params
    )
