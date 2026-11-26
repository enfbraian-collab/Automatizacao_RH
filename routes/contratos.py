
import io
import json

from datetime import date
from functools import wraps

from flask import (
    Blueprint,
    abort,
    render_template,
    request,
    send_file,
    session,
    redirect,
    url_for,
    jsonify,
    current_app
)

from services.database import query_data, DATE_COLUMN
from services.usuarios import obter_permissoes
from services.etl import executar_etl_contratos, ETLJaEmExecucao


contratos_bp = Blueprint("contratos", __name__)

ALLOWED_STATUSES = {
    "VENCIDO",
    "ENCAMINHAR E-MAIL COM URGÊNCIA",
    "ENCAMINHAR E-MAIL",
    "EM TEMPO DE CARÊNCIA",
    "SEM DATA DE VENCIMENTO"
}


# =====================================================
# CONTROLE DE ACESSO
# =====================================================

def permissao_contratos(tipo="visualizar"):

    def decorator(fn):

        @wraps(fn)
        def wrapper(*args, **kwargs):

            usuario_id = session.get("usuario_id")

            if not usuario_id:
                return redirect(url_for("auth.login"))

            # ROOT tem acesso a todas as funcionalidades
            if session.get("is_root"):
                return fn(*args, **kwargs)

            permissoes = obter_permissoes(usuario_id)

            acesso = permissoes.get("contratos", {})

            if not acesso.get(tipo, False):
                abort(403, "Você não possui permissão para esta operação.")

            return fn(*args, **kwargs)

        return wrapper

    return decorator


# =====================================================
# FILTROS
# =====================================================

def get_filters():

    start_raw = request.args.get("inicio", "").strip()
    end_raw = request.args.get("fim", "").strip()

    if not start_raw or not end_raw:
        abort(400, "Informe data inicial e data final.")

    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
    except ValueError:
        abort(400, "Datas inválidas.")

    if start > end:
        abort(400, "Data inicial deve ser anterior ou igual à final.")

    status = request.args.get("status", "").strip()

    if status and status not in ALLOWED_STATUSES:
        abort(400, "Status inválido.")

    return start, end, status


# =====================================================
# PÁGINA DE CONTRATOS
# =====================================================

@contratos_bp.get("/")
@permissao_contratos("visualizar")
def index():

    return render_template(
        "index.html",
        statuses=sorted(ALLOWED_STATUSES),
        date_column=DATE_COLUMN
    )


# =====================================================
# CONSULTAR CONTRATOS
# =====================================================

@contratos_bp.get("/consultar")
@permissao_contratos("visualizar")
def consultar():

    start, end, status = get_filters()

    try:
        data = query_data(
            start,
            end,
            status,
            limit=100
        )

    except ValueError as exc:
        abort(400, str(exc))

    registros = json.loads(
        data.to_json(
            orient="records",
            date_format="iso"
        )
    )

    return jsonify({
        "total_exibido": len(data),
        "colunas": list(data.columns),
        "registros": registros
    })


# =====================================================
# EXPORTAR CONTRATOS
# =====================================================

@contratos_bp.get("/exportar")
@permissao_contratos("exportar")
def exportar():

    start, end, status = get_filters()

    formato = request.args.get(
        "formato",
        "xlsx"
    )

    if formato not in ("xlsx", "csv"):
        abort(400, "Formato inválido.")

    try:
        data = query_data(
            start,
            end,
            status
        )

    except ValueError as exc:
        abort(400, str(exc))

    nome = (
        f"contratos_{start:%Y%m%d}_"
        f"{end:%Y%m%d}.{formato}"
    )

    output = io.BytesIO()

    if formato == "xlsx":

        if len(data) > 1_048_575:
            abort(
                400,
                "Quantidade excede o limite do Excel. Use CSV."
            )

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
        download_name=nome
    )


# Acionado pelo botão Consultar registros antes da consulta ao PostgreSQL.
@contratos_bp.post("/atualizar-dados")
@permissao_contratos("visualizar")
def atualizar_dados():
    try:
        executar_etl_contratos()
    except ETLJaEmExecucao:
        return jsonify({"erro": "Uma atualização já está em andamento. Aguarde."}), 409
    except Exception:
        current_app.logger.exception("Falha na atualização dos contratos")
        return jsonify({"erro": "Não foi possível atualizar os dados. Consulte os logs do servidor."}), 500
    return jsonify({"sucesso": True, "mensagem": "Dados atualizados com sucesso."})
