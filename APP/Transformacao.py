from sqlalchemy import TEXT
from extracao import OracleConnector
from Carregamento import SupabaseConnector
from query import Automatizacao, Gestantes
import pandas as pd
import re
import os


#Conectar no banco Oracle
con = OracleConnector()
con.conectar()
df =con.executar_query(Automatizacao,chunksize=1000)
dfg = con.executar_query(Gestantes,chunksize=1000)
print(dfg.head())
print(df.head())
con.fechar_conexao()

#Transformar os dados

# Transformar os dados


def extrair_informacoes(descricao):
    resultado = {
        "REQ": None,
        "Substituído": None,
        "Crachá Substituído": None,
        "Tipo Contrato": None,
        "Dias Contrato": None,
        "Motivo": None
    }

    if pd.isna(descricao):
        return pd.Series(resultado)

    texto = str(descricao).strip().upper()
    texto = re.sub(r"\s+", " ", texto)

    # 1. Número da requisição
    req = re.search(r"\bREQ\.?\s*(\d+)", texto)
    if req:
        resultado["REQ"] = req.group(1)

    # 2. Nome do colaborador substituído
    nome = re.search(
        r"\bSUBST(?:C|ITUI(?:CAO|ÇÃO)?)?\s*A\s*"
        r"(.+?)\s*COD\.?\s*\d+",
        texto
    )
    if nome:
        resultado["Substituído"] = nome.group(1).strip(" .-")

    # 3. Crachá do colaborador substituído
    cracha = re.search(r"\bCOD\.?\s*(\d+)", texto)
    if cracha:
        resultado["Crachá Substituído"] = cracha.group(1)

    # 4. Tipo de contrato
    contrato = re.search(
        r"\b(CONTRATO DETERMINADO|CONT DETERMINADO|"
        r"CONTRATO INDETERMINADO|CONT INDETERMINADO)\b",
        texto
    )
    if contrato:
        tipo = contrato.group(1)
        resultado["Tipo Contrato"] = (
            tipo.replace("CONT DETERMINADO", "CONTRATO DETERMINADO")
                .replace("CONT INDETERMINADO", "CONTRATO INDETERMINADO")
        )

    # 5. Quantidade de dias
    dias = re.search(r"\b(\d+)\s*DIAS?\b", texto)
    if dias:
        resultado["Dias Contrato"] = int(dias.group(1))

    # 6. Motivo
    motivo = re.search(
        r"\bDIAS?\s*[-: ]*\s*(?:MOTIVO\s*[-:]?\s*)?(.+)$",
        texto
    )
    if motivo:
        resultado["Motivo"] = motivo.group(1).strip(" .-:")

    return pd.Series(resultado)


# Criar as novas colunas
novas_colunas = df["Descrição Completa"].apply(extrair_informacoes)

# Adicionar ao DataFrame original
df = pd.concat([df, novas_colunas], axis=1)

# Conferir o resultado
print("\nDados transformados:")
print(df[[
    "REQ",
    "Substituído",
    "Crachá Substituído",
    "Tipo Contrato",
    "Dias Contrato",
    "Motivo"
]].head(10).to_string(index=False))



# 1. Converter a admissão para data
df["Admissão"] = pd.to_datetime(
    df["Admissão"],
    errors="coerce"
)

# 2. Converter os dias de contrato para número
df["Dias Contrato"] = pd.to_numeric(
    df["Dias Contrato"],
    errors="coerce"
)

# 3. Calcular a data de vencimento
df["Data Vencimento"] = (
    df["Admissão"] +
    pd.to_timedelta(df["Dias Contrato"], unit="D")
)

# 4. Calcular quantos dias faltam para vencer
hoje = pd.Timestamp.today().normalize()

df["Dias Restantes"] = (
    df["Data Vencimento"] - hoje
).dt.days

# 5. Classificar o status do vencimento
def classificar_vencimento(dias):

    if pd.isna(dias):
        return "SEM DATA DE VENCIMENTO"

    if dias < 0:
        return "VENCIDO"

    elif dias < 10:
        return "ENCAMINHAR E-MAIL COM URGÊNCIA"

    elif dias <= 20:
        return "ENCAMINHAR E-MAIL"

    else:
        return "EM TEMPO DE CARÊNCIA"


df["Status Vencimento"] = df["Dias Restantes"].apply(
    classificar_vencimento
)

# 6. Conferir o resultado
print("\nControle de vencimento dos contratos:")

print(df[[
    "Colaborador",
    "Admissão",
    "Dias Contrato",
    "Data Vencimento",
    "Dias Restantes",
    "Status Vencimento"
]].to_string(index=False))

def salva_df_local(df: pd.DataFrame, nome_arquivo: str, caminho: str = r'C:\Users\WEMBLEY.MACEDO\Desktop\tabelas\\'):
    """
    Salva o DataFrame localmente, suportando Parquet, CSV e Excel dinamicamente.
    """
    caminho_completo = os.path.join(caminho, nome_arquivo)
    try:
        if nome_arquivo.endswith('.parquet'):
            df.to_parquet(caminho_completo, index=False)
        elif nome_arquivo.endswith('.csv'):
            df.to_csv(caminho_completo, index=False, sep=';', encoding='utf-8-sig')
        elif nome_arquivo.endswith('.xlsx'):
            df.to_excel(caminho_completo, index=False)
        else:
            print(f"❌ Formato de arquivo não suportado: {nome_arquivo}")
            return

        print(f"✅ DataFrame salvo localmente como {nome_arquivo}")

    except Exception as e:
        print(f"❌ Erro ao salvar DataFrame {nome_arquivo}: {e}")

salva_df_local(df, "Automatizacao_Lidi.csv", caminho=r"C:\Users\braian.lourenco\Desktop")

# Carregar os dados no banco PostgreSQL
con_postgres = SupabaseConnector()
con_postgres._create_engine()
con_postgres.load_dataframe(df, "Automatizacao_Lidi")
con_postgres.fechar_conexao()

#Carregar os dados da tabela Gestantes no banco PostgreSQL
con_postgres.load_dataframe(dfg, "Gestantes")
