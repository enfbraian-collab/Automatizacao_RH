import io
import os
import re
from datetime import date, datetime
from functools import wraps
from hmac import compare_digest

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, Response, abort, render_template, request, send_file, session, redirect, url_for
from sqlalchemy import create_engine, inspect, text

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    dotenv_path=BASE_DIR / ".env",
    override=True
)
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Automatizacao_Lidi')
DATE_COLUMN = os.environ.get('DATE_COLUMN', 'Admissão')
STATUS_COLUMN = 'Status Vencimento'
ALLOWED_STATUSES = {'VENCIDO', 'ENCAMINHAR E-MAIL COM URGÊNCIA', 'ENCAMINHAR E-MAIL', 'EM TEMPO DE CARÊNCIA', 'SEM DATA DE VENCIMENTO'}

if not app.secret_key or not DATABASE_URL or not os.environ.get('PORTAL_PASSWORD') or not os.environ.get('PORTAL_USER'):
    raise RuntimeError('Configure FLASK_SECRET_KEY, DATABASE_URL, PORTAL_USER e PORTAL_PASSWORD no .env')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        valid_user = compare_digest(request.form.get('username', ''), os.environ['PORTAL_USER'])
        valid_password = compare_digest(request.form.get('password', ''), os.environ['PORTAL_PASSWORD'])
        if valid_user and valid_password:
            session.clear()
            session['authenticated'] = True
            return redirect(url_for('index'))
        error = 'Credenciais inválidas.'
    return render_template('login.html', error=error)


@app.post('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def get_columns():
    cols = [c['name'] for c in inspect(engine).get_columns(TABLE_NAME)]
    if DATE_COLUMN not in cols:
        raise RuntimeError(f'Coluna de período não encontrada: {DATE_COLUMN}')
    return cols


def get_filters():
    start_raw = request.args.get('inicio', '').strip()
    end_raw = request.args.get('fim', '').strip()
    if not start_raw or not end_raw:
        abort(400, 'Informe data inicial e data final.')
    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
    except ValueError:
        abort(400, 'Datas inválidas.')
    if start > end:
        abort(400, 'Data inicial deve ser anterior ou igual à data final.')
    status = request.args.get('status', '').strip()
    if status and status not in ALLOWED_STATUSES:
        abort(400, 'Status inválido.')
    return start, end, status


def query_data(start, end, status, limit=None):
    cols = get_columns()
    date_col = quote_identifier(DATE_COLUMN)
    sql = f'SELECT * FROM {quote_identifier(TABLE_NAME)} WHERE {date_col} >= :inicio AND {date_col} < (:fim + INTERVAL \'1 day\')'
    params = {'inicio': start, 'fim': end}
    if status:
        if STATUS_COLUMN not in cols:
            abort(400, 'Coluna de status não encontrada.')
        sql += f' AND {quote_identifier(STATUS_COLUMN)} = :status'
        params['status'] = status
    sql += f' ORDER BY {date_col} DESC'
    if limit is not None:
        sql += ' LIMIT :limite'
        params['limite'] = limit
    return pd.read_sql_query(text(sql), engine, params=params)


@app.get('/')
@login_required
def index():
    return render_template('index.html', statuses=sorted(ALLOWED_STATUSES), date_column=DATE_COLUMN)


@app.get('/consultar')
@login_required
def consultar():
    start, end, status = get_filters()
    data = query_data(start, end, status, limit=100)
    return {'total_exibido': len(data), 'colunas': list(data.columns), 'registros': data.astype(object).where(pd.notna(data), None).to_json(orient='records', date_format='iso')}


@app.get('/exportar')
@login_required
def exportar():
    start, end, status = get_filters()
    formato = request.args.get('formato', 'xlsx')
    if formato not in ('xlsx', 'csv'):
        abort(400, 'Formato inválido.')
    data = query_data(start, end, status)
    nome = f'contratos_{start:%Y%m%d}_{end:%Y%m%d}.{formato}'
    output = io.BytesIO()
    if formato == 'xlsx':
        if len(data) > 1_048_575:
            abort(400, 'Quantidade excede o limite de linhas do Excel. Use CSV.')
        data.to_excel(output, index=False, engine='openpyxl')
        mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        output.write(data.to_csv(index=False, sep=';').encode('utf-8-sig'))
        mime = 'text/csv; charset=utf-8'
    output.seek(0)
    return send_file(output, mimetype=mime, as_attachment=True, download_name=nome)


if __name__ == '__main__':
    app.run(host='127.0.0.2', port=2000, debug=False)
