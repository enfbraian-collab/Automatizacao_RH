
import secrets
from functools import wraps

from flask import (
    Blueprint, abort, flash, redirect,
    render_template, request, session, url_for
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from routes.auth import usuario_atual
from services.database import engine


admin_bp = Blueprint("admin", __name__)

MODULOS = ("contratos", "gestantes")


# =====================================================
# SEGURANÇA
# =====================================================

def root_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        usuario = usuario_atual()

        if not usuario:
            return redirect(url_for("auth.login"))

        if not usuario["is_root"]:
            abort(403, "Acesso restrito ao ROOT.")

        return func(*args, **kwargs)

    return wrapper


def token_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    return session["csrf_token"]


def validar_csrf():
    recebido = request.form.get("csrf_token", "")
    esperado = session.get("csrf_token", "")

    if not esperado or not secrets.compare_digest(
        recebido, esperado
    ):
        abort(400, "Token de segurança inválido.")


# =====================================================
# LISTAR USUÁRIOS
# =====================================================

@admin_bp.get("/")
@root_required
def index():

    with engine.connect() as conn:
        usuarios = conn.execute(
            text("""
                SELECT
                    id, nome, username,
                    is_root, ativo, criado_em
                FROM portal_usuarios
                ORDER BY is_root DESC, nome
            """)
        ).mappings().all()

        registros = conn.execute(
            text("""
                SELECT
                    usuario_id,
                    modulo,
                    pode_visualizar,
                    pode_exportar
                FROM portal_permissoes
            """)
        ).mappings().all()

    permissoes = {}

    for registro in registros:
        usuario_id = registro["usuario_id"]

        permissoes.setdefault(usuario_id, {})

        permissoes[usuario_id][registro["modulo"]] = {
            "visualizar": registro["pode_visualizar"],
            "exportar": registro["pode_exportar"]
        }

    return render_template(
        "admin_usuarios.html",
        usuarios=usuarios,
        permissoes=permissoes,
        csrf_token=token_csrf()
    )


# =====================================================
# CADASTRAR USUÁRIO
# =====================================================

@admin_bp.post("/criar")
@root_required
def criar():

    validar_csrf()

    nome = request.form.get("nome", "").strip()
    username = request.form.get("username", "").strip().lower()
    senha = request.form.get("senha", "")

    if not nome or not username:
        flash("Informe nome e login.", "erro")
        return redirect(url_for("admin.index"))

    if len(senha) < 7:
        flash("A senha precisa ter pelo menos 7 caracteres.", "erro")
        return redirect(url_for("admin.index"))

    try:
        with engine.begin() as conn:

            usuario_id = conn.execute(
                text("""
                    INSERT INTO portal_usuarios
                        (nome, username, password_hash, is_root, ativo)
                    VALUES
                        (:nome, :username, :senha, FALSE, TRUE)
                    RETURNING id
                """),
                {
                    "nome": nome,
                    "username": username,
                    "senha": generate_password_hash(
                        senha, method="scrypt"
                    )
                }
            ).scalar_one()

            for modulo in MODULOS:

                visualizar = (
                    request.form.get(f"{modulo}_visualizar")
                    == "on"
                )

                exportar = (
                    request.form.get(f"{modulo}_exportar")
                    == "on"
                )

                # Exportação exige permissão de consulta
                if exportar:
                    visualizar = True

                conn.execute(
                    text("""
                        INSERT INTO portal_permissoes
                            (usuario_id, modulo,
                             pode_visualizar, pode_exportar)
                        VALUES
                            (:id, :modulo, :visualizar, :exportar)
                    """),
                    {
                        "id": usuario_id,
                        "modulo": modulo,
                        "visualizar": visualizar,
                        "exportar": exportar
                    }
                )

    except IntegrityError:
        flash("Esse login já está cadastrado.", "erro")
        return redirect(url_for("admin.index"))

    flash("Usuário cadastrado com sucesso.", "sucesso")
    return redirect(url_for("admin.index"))


# =====================================================
# ATUALIZAR PERMISSÕES
# =====================================================

@admin_bp.post("/permissoes/<int:usuario_id>")
@root_required
def atualizar_permissoes(usuario_id):

    validar_csrf()

    with engine.begin() as conn:

        usuario = conn.execute(
            text("""
                SELECT is_root
                FROM portal_usuarios
                WHERE id = :id
            """),
            {"id": usuario_id}
        ).mappings().first()

        if not usuario:
            abort(404)

        if usuario["is_root"]:
            abort(403, "Permissões ROOT não podem ser alteradas.")

        for modulo in MODULOS:

            visualizar = (
                request.form.get(f"{modulo}_visualizar")
                == "on"
            )

            exportar = (
                request.form.get(f"{modulo}_exportar")
                == "on"
            )

            if exportar:
                visualizar = True

            conn.execute(
                text("""
                    INSERT INTO portal_permissoes
                        (usuario_id, modulo,
                         pode_visualizar, pode_exportar)
                    VALUES
                        (:id, :modulo, :visualizar, :exportar)
                    ON CONFLICT (usuario_id, modulo)
                    DO UPDATE SET
                        pode_visualizar = EXCLUDED.pode_visualizar,
                        pode_exportar = EXCLUDED.pode_exportar
                """),
                {
                    "id": usuario_id,
                    "modulo": modulo,
                    "visualizar": visualizar,
                    "exportar": exportar
                }
            )

    flash("Permissões atualizadas.", "sucesso")
    return redirect(url_for("admin.index"))


# =====================================================
# ATIVAR / BLOQUEAR USUÁRIO
# =====================================================

@admin_bp.post("/status/<int:usuario_id>")
@root_required
def alterar_status(usuario_id):

    validar_csrf()

    with engine.begin() as conn:
        resultado = conn.execute(
            text("""
                UPDATE portal_usuarios
                SET ativo = NOT ativo
                WHERE id = :id
                  AND is_root = FALSE
                RETURNING id
            """),
            {"id": usuario_id}
        ).first()

    if not resultado:
        abort(404, "Usuário comum não encontrado.")

    flash("Situação do usuário atualizada.", "sucesso")
    return redirect(url_for("admin.index"))


# =====================================================
# REDEFINIR SENHA
# =====================================================

@admin_bp.post("/senha/<int:usuario_id>")
@root_required
def redefinir_senha(usuario_id):

    validar_csrf()

    senha = request.form.get("senha", "")

    if len(senha) < 6:
        flash("A nova senha precisa ter 6 caracteres.", "erro")
        return redirect(url_for("admin.index"))

    with engine.begin() as conn:
        resultado = conn.execute(
            text("""
                UPDATE portal_usuarios
                SET password_hash = :senha
                WHERE id = :id
                  AND is_root = FALSE
                RETURNING id
            """),
            {
                "id": usuario_id,
                "senha": generate_password_hash(
                    senha, method="scrypt"
                )
            }
        ).first()

    if not resultado:
        abort(404, "Usuário comum não encontrado.")

    flash("Senha redefinida com sucesso.", "sucesso")
    return redirect(url_for("admin.index"))
