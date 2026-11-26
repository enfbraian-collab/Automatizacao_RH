
import io
import json

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for
)

from routes.auth import usuario_atual
from services.database import query_gestantes
from services.usuarios import obter_permissoes


gestantes_bp = Blueprint("gestantes", __name__)


def verificar_acesso(tipo="visualizar"):

    usuario = usuario_atual()

    if not usuario:
        return redirect(url_for("auth.login"))

    if usuario["is_root"]:
        return None

    permissoes = obter_permissoes(usuario["id"])

    if not permissoes.get("gestantes", {}).get(tipo, False):
        abort(403, "Acesso não autorizado.")

    return None


@gestantes_bp.get("/")
def index():

    bloqueio = verificar_acesso("visualizar")

    if bloqueio is not None:
        return bloqueio

    return render_template("gestantes.html")


@gestantes_bp.get("/consultar")
def consultar():

    bloqueio = verificar_acesso("visualizar")

    if bloqueio is not None:
        return bloqueio

    data = query_gestantes(limit=100)

    return jsonify({
        "total_exibido": len(data),
        "colunas": list(data.columns),
        "registros": json.loads(
            data.to_json(
                orient="records",
                date_format="iso"
            )
        )
    })


@gestantes_bp.get("/exportar")
def exportar():

    bloqueio = verificar_acesso("exportar")

    if bloqueio is not None:
        return bloqueio

    formato = request.args.get("formato", "xlsx")

    if formato not in ("xlsx", "csv"):
        abort(400, "Formato inválido.")

    data = query_gestantes()

    output = io.BytesIO()

    if formato == "xlsx":

        if len(data) > 1_048_575:
            abort(400, "Limite do Excel excedido. Use CSV.")

        data.to_excel(
            output,
            index=False,
            engine="openpyxl"
        )

        mime = (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )

    else:

        output.write(
            data.to_csv(
                index=False,
                sep=";"
            ).encode("utf-8-sig")
        )

        mime = "text/csv; charset=utf-8"

    output.seek(0)

    return send_file(
        output,
        mimetype=mime,
        as_attachment=True,
        download_name=f"gestantes.{formato}"
    )
