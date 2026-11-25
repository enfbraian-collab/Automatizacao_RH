# Portal de Extração de Contratos

Aplicação Flask que consulta uma tabela PostgreSQL existente e permite filtrar por período de admissão e status de vencimento, visualizar até 100 registros e baixar Excel ou CSV.

## Instalação (Windows)

1. Instale Python 3.11 ou superior.
2. Abra o terminal nesta pasta.
3. Execute `python -m venv .venv` e `.venv\Scripts\activate`.
4. Execute `pip install -r requirements.txt`.
5. Copie `.env.example` para `.env` e preencha os valores reais (não compartilhe esse arquivo).
6. Execute `python app.py`.
7. Abra `http://127.0.0.1:5000` no navegador.

**Atenção:** o protótipo usa login simples por variável de ambiente, adequado apenas a teste local. Antes de disponibilizar para outras pessoas, implemente autenticação corporativa/SSO, HTTPS, controles de autorização por usuário, logs de auditoria, limites de consulta, CSRF, rate limiting e hospedagem com servidor WSGI de produção. Não publique o servidor de desenvolvimento Flask na rede/internet.

A coluna usada no filtro de período é configurada por `DATE_COLUMN` (padrão `Admissão`). A tabela é configurada por `TABLE_NAME` (padrão `Automatizacao_Lidi`). Confirme que a tabela e as colunas existem exatamente com esses nomes no PostgreSQL, incluindo letras maiúsculas e acentos. A consulta presume que a coluna de data é do tipo DATE/TIMESTAMP. Se o banco estiver em outro schema, adapte a consulta e a inspeção de colunas.

O sistema **não** executa o ETL Oracle: consulta a última carga disponível no PostgreSQL. A atualização dos dados deve ser agendada separadamente.
