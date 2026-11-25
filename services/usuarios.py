
from sqlalchemy import text
from werkzeug.security import check_password_hash

from services.database import engine


def autenticar_usuario(username, senha):
    """
    Consulta o usuário no PostgreSQL e
    verifica a senha cadastrada.
    """

    username = username.strip().lower()

    if not username or not senha:
        return None

    sql = text("""
        SELECT
            id,
            nome,
            username,
            password_hash,
            is_root,
            ativo
        FROM portal_usuarios
        WHERE username = :username
        LIMIT 1
    """)

    with engine.connect() as conn:
        usuario = conn.execute(
            sql,
            {"username": username}
        ).mappings().first()

    if not usuario:
        return None

    if not usuario["ativo"]:
        return None

    if not check_password_hash(
        usuario["password_hash"],
        senha
    ):
        return None

    return {
        "id": usuario["id"],
        "nome": usuario["nome"],
        "username": usuario["username"],
        "is_root": usuario["is_root"]
    }


def obter_permissoes(usuario_id):
    """
    Retorna as permissões de acesso
    atribuídas ao usuário.
    """

    sql = text("""
        SELECT
            modulo,
            pode_visualizar,
            pode_exportar
        FROM portal_permissoes
        WHERE usuario_id = :usuario_id
    """)

    with engine.connect() as conn:
        registros = conn.execute(
            sql,
            {"usuario_id": usuario_id}
        ).mappings().all()

    return {
        registro["modulo"]: {
            "visualizar": registro["pode_visualizar"],
            "exportar": registro["pode_exportar"]
        }
        for registro in registros
    }
