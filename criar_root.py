
import os
from pathlib import Path
from getpass import getpass

from dotenv import load_dotenv
from sqlalchemy import text
from werkzeug.security import generate_password_hash

# Carregar as variáveis de ambiente
BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# Aproveitar a conexão PostgreSQL existente
from services.database import engine, criar_tabelas_portal


def cadastrar_root():

    criar_tabelas_portal()

    print("\n=== CADASTRO DO ADMINISTRADOR ROOT ===")

    nome = input("Nome completo: ").strip()
    usuario = input("Usuário de acesso: ").strip().lower()
    senha = getpass("Senha do ROOT: ")
    confirmacao = getpass("Confirme a senha: ")

    if not nome or not usuario:
        print("Nome e usuário são obrigatórios.")
        return

    if len(senha) < 5:
        print("A senha deve ter pelo menos 5 caracteres.")
        return

    if senha != confirmacao:
        print("As senhas não coincidem.")
        return

    senha_hash = generate_password_hash(
        senha,
        method="scrypt"
    )

    with engine.begin() as conn:

        existente = conn.execute(
            text("""
                SELECT id
                FROM portal_usuarios
                WHERE username = :usuario
            """),
            {"usuario": usuario}
        ).first()

        if existente:
            print("Esse usuário já está cadastrado.")
            return

        conn.execute(
            text("""
                INSERT INTO portal_usuarios
                    (nome, username, password_hash, is_root, ativo)
                VALUES
                    (:nome, :usuario, :senha, TRUE, TRUE)
            """),
            {
                "nome": nome,
                "usuario": usuario,
                "senha": senha_hash
            }
        )

    print("\nROOT cadastrado com sucesso!")


if __name__ == "__main__":
    cadastrar_root()
