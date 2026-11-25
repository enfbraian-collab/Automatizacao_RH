
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    abort
)

from sqlalchemy import text

from services.database import engine
from services.usuarios import (
    autenticar_usuario,
    obter_permissoes
)


auth_bp = Blueprint("auth", __name__)


# =====================================================
# CONSULTAR USUÁRIO AUTENTICADO
# =====================================================

def usuario_atual():

    usuario_id = session.get("usuario_id")

    if not usuario_id:
        return None

    with engine.connect() as conn:
        usuario = conn.execute(
            text("""
                SELECT
                    id,
                    nome,
                    username,
                    is_root,
                    ativo
                FROM portal_usuarios
                WHERE id = :usuario_id
            """),
            {"usuario_id": usuario_id}
        ).mappings().first()

    if not usuario or not usuario["ativo"]:
        session.clear()
        return None

    return usuario


# =====================================================
# REDIRECIONAMENTO CONFORME PERMISSÕES
# =====================================================

def redirecionar_usuario(usuario):

    # ROOT acessa o painel administrativo
    if usuario["is_root"]:
        return redirect(url_for("auth.painel"))

    # Consultar permissões no PostgreSQL
    permissoes = obter_permissoes(usuario["id"])

    # Acesso ao módulo de contratos
    if permissoes.get("contratos", {}).get("visualizar"):
        return redirect(url_for("contratos.index"))

    # Acesso ao módulo de gestantes
    if permissoes.get("gestantes", {}).get("visualizar"):
        return redirect(url_for("gestantes.index"))

    # Usuário sem permissão
    abort(
        403,
        "Usuário autenticado, mas sem módulo autorizado."
    )


# =====================================================
# PÁGINA INICIAL
# =====================================================

@auth_bp.get("/")
def inicio():

    usuario = usuario_atual()

    if not usuario:
        return redirect(url_for("auth.login"))

    return redirecionar_usuario(usuario)


# =====================================================
# LOGIN
# =====================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    usuario = usuario_atual()

    if usuario:
        return redirecionar_usuario(usuario)

    error = None

    if request.method == "POST":

        usuario = autenticar_usuario(
            request.form.get("username", ""),
            request.form.get("password", "")
        )

        if usuario:

            session.clear()

            session["usuario_id"] = usuario["id"]
            session["nome"] = usuario["nome"]
            session["username"] = usuario["username"]
            session["is_root"] = usuario["is_root"]

            return redirecionar_usuario(usuario)

        error = "Usuário ou senha inválidos."

    return render_template(
        "login.html",
        error=error
    )


# =====================================================
# PAINEL ROOT
# =====================================================

@auth_bp.get("/painel")
def painel():

    usuario = usuario_atual()

    if not usuario:
        return redirect(url_for("auth.login"))

    if not usuario["is_root"]:
        abort(
            403,
            "Acesso não autorizado."
        )

    # Renderizar nova interface administrativa
    return render_template(
        "painel_root.html",
        usuario=usuario
    )


# =====================================================
# LOGOUT
# =====================================================

@auth_bp.post("/logout")
def logout():

    session.clear()

    return redirect(url_for("auth.login"))
