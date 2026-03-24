# Stark Bank Webhook Integration

Sistema de integração com a API do Stark Bank para emissão automatizada de invoices e processamento de webhooks para transferências.

## Sumario

- [Sobre o Projeto](#sobre-o-projeto)
- [Arquitetura](#arquitetura)
- [Stack Tecnologica](#stack-tecnologica)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Pre-requisitos](#pre-requisitos)
- [Configuracao](#configuracao)
- [Como Subir o Ambiente](#como-subir-o-ambiente)
- [Deploy em Producao (VPS)](#deploy-em-producao-vps)
- [Endpoints da API](#endpoints-da-api)
- [Celery e Tasks](#celery-e-tasks)
- [Testes](#testes)
- [Observabilidade](#observabilidade)
- [Seguranca](#seguranca)

---

## Sobre o Projeto

Este projeto implementa uma integracao com o Stark Bank que:

1. **Emite 8-12 invoices a cada 3 horas** para pessoas aleatorias durante 24 horas (8 execucoes)
2. **Recebe webhooks** quando invoices sao pagas (credited)
3. **Cria transferencias automaticas** do valor recebido (menos taxas) para a conta destino configurada

### Fluxo de Funcionamento

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Celery Beat    │────▶│  Issue Invoices │────▶│   Stark Bank    │
│  (3h interval)  │     │     Task        │     │      API        │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Create         │◀────│  Process Credit │◀────│    Webhook      │
│  Transfer       │     │     Task        │     │   Callback      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Arquitetura

O sistema utiliza uma arquitetura baseada em microservicos containerizados:

```
┌──────────────────────────────────────────────────────────────────┐
│                           NGINX                                   │
│                    (Reverse Proxy :80)                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                      DJANGO + GUNICORN                            │
│                    (Web Application :8000)                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │
│  │   Views    │  │  Services  │  │   Models   │                  │
│  └────────────┘  └────────────┘  └────────────┘                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │     Redis     │  │    Celery     │
│   (Database)  │  │    (Broker)   │  │   (Workers)   │
└───────────────┘  └───────────────┘  └───────┬───────┘
                                              │
                                              ▼
                                    ┌───────────────┐
                                    │  Celery Beat  │
                                    │  (Scheduler)  │
                                    └───────────────┘
```

### Componentes

| Componente | Descricao |
|------------|-----------|
| **Nginx** | Reverse proxy, serve arquivos estaticos, SSL termination |
| **Django + Gunicorn** | Aplicacao web com 3 workers |
| **PostgreSQL 16** | Banco de dados relacional |
| **Redis 7** | Message broker para Celery |
| **Celery Worker** | Processamento assincrono de tasks |
| **Celery Beat** | Agendamento de tasks periodicas |

---

## Stack Tecnologica

### Backend
| Tecnologia | Versao | Descricao |
|------------|--------|-----------|
| Python | 3.12 | Linguagem de programacao |
| Django | 6.0.3 | Framework web |
| Django REST Framework | 3.17.0 | API REST |
| Celery | 5.6.2 | Task queue assincrona |
| Gunicorn | 25.1.0 | WSGI HTTP Server |

### Banco de Dados e Cache
| Tecnologia | Versao | Descricao |
|------------|--------|-----------|
| PostgreSQL | 16 (Alpine) | Banco de dados |
| Redis | 7 (Alpine) | Message broker |

### Integracao
| Tecnologia | Versao | Descricao |
|------------|--------|-----------|
| starkbank-sdk | 2.32.1 | SDK oficial do Stark Bank |
| Faker | 40.11.1 | Geracao de dados aleatorios |

### Documentacao e Observabilidade
| Tecnologia | Versao | Descricao |
|------------|--------|-----------|
| drf-spectacular | 0.29.0 | OpenAPI/Swagger |
| Sentry SDK | 2.55.0 | Monitoramento de erros |

### Infraestrutura
| Tecnologia | Descricao |
|------------|-----------|
| Docker | Containerizacao |
| Docker Compose | Orquestracao local |
| Nginx | Reverse proxy |

---

## Estrutura do Projeto

```
starkbank_webhook/
├── core/                       # Configuracoes do projeto Django
│   ├── __init__.py
│   ├── celery.py              # Configuracao do Celery
│   ├── settings.py            # Configuracoes do Django
│   ├── urls.py                # URLs principais
│   └── wsgi.py                # WSGI config
│
├── invoices/                   # App principal
│   ├── management/
│   │   └── commands/
│   │       └── start_campaign.py  # Comando para iniciar campanha
│   ├── migrations/            # Migracoes do banco
│   ├── tests/                 # Testes unitarios
│   │   ├── test_models.py
│   │   ├── test_services.py
│   │   ├── test_tasks.py
│   │   └── test_views.py
│   ├── admin.py               # Django Admin
│   ├── apps.py
│   ├── exceptions.py          # Excecoes customizadas
│   ├── models.py              # Modelos do banco
│   ├── serializers.py         # Serializers DRF
│   ├── services.py            # Servicos do Stark Bank
│   ├── tasks.py               # Tasks do Celery
│   ├── urls.py                # URLs do app
│   └── views.py               # Views/Endpoints
│
├── keys/                       # Chaves privadas (gitignore)
│   └── private-key.pem
│
├── nginx/
│   └── nginx.conf             # Configuracao do Nginx
│
├── staticfiles/               # Arquivos estaticos coletados
│
├── .env                       # Variaveis de ambiente
├── .env-example               # Exemplo de variaveis
├── docker-compose.yml         # Orquestracao Docker
├── Dockerfile                 # Build da aplicacao
├── manage.py
└── requirements.txt           # Dependencias Python
```

---

## Pre-requisitos

- Docker e Docker Compose
- Conta no Stark Bank Sandbox
- Chave privada do projeto Stark Bank

### Gerando Chaves do Stark Bank

O Stark Bank utiliza chaves ECDSA com a curva secp256k1 para autenticacao. Siga os passos abaixo para gerar seu par de chaves:

```bash
# 1. Gerar chave privada ECDSA (curva secp256k1)
openssl ecparam -name secp256k1 -genkey -out privateKey.pem

# 2. Extrair chave publica da chave privada
openssl ec -in privateKey.pem -pubout -out publicKey.pem

# 3. Visualizar a chave publica para cadastrar no Stark Bank
cat publicKey.pem
```

**Importante:**
- A chave **privada** (`privateKey.pem`) deve ser mantida em segredo e usada na sua aplicacao
- A chave **publica** (`publicKey.pem`) deve ser cadastrada no painel do Stark Bank ao criar o Project
- Copie o arquivo `privateKey.pem` para a pasta `keys/` do projeto e configure o path no `.env`

---

## Configuracao

### 1. Clone o repositorio

```bash
git clone <repository-url>
cd starkbank_webhook
```

### 2. Configure as variaveis de ambiente

```bash
cp .env-example .env
```

### 3. Edite o arquivo `.env`

```env
# Django Settings
DEBUG=True
SECRET_KEY=sua-chave-secreta-aqui
ALLOWED_HOSTS=localhost,127.0.0.1,seu-dominio.com
CSRF_TRUSTED_ORIGINS=https://seu-dominio.com

# Database
DB_NAME=starkbank_db
DB_USER=starkbank_user
DB_PASSWORD=starkbank_pass
DB_HOST=db
DB_PORT=5432

# Redis/Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Celery Retry Settings
CELERY_RETRY_BACKOFF=60
CELERY_RETRY_BACKOFF_MAX=600
CELERY_RETRY_MAX=5

# Stark Bank
STARKBANK_ENVIRONMENT=sandbox
STARKBANK_PROJECT_ID=seu-project-id
STARKBANK_PRIVATE_KEY_PATH=/app/keys/private-key.pem
STARKBANK_INVOICE_EXPIRATION_HOURS=12

# Transfer Destination Account
TRANSFER_BANK_CODE=20018183
TRANSFER_BRANCH_CODE=0001
TRANSFER_ACCOUNT_NUMBER=6341320293482496
TRANSFER_ACCOUNT_NAME=Stark Bank S.A.
TRANSFER_TAX_ID=20.018.183/0001-80
TRANSFER_ACCOUNT_TYPE=payment

# API Authentication
API_KEY=sua-api-key-segura

# Rate Limiting
THROTTLE_RATE_ANON=100/hour
THROTTLE_RATE_USER=1000/hour
THROTTLE_RATE_WEBHOOK=60/minute

# Webhook IP Whitelist (comma-separated, empty = disabled)
WEBHOOK_IP_WHITELIST=

# Sentry (optional)
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
```

### 4. Adicione sua chave privada

```bash
mkdir -p keys
cp /path/to/your/private-key.pem keys/private-key.pem
```

---

## Como Subir o Ambiente

### Desenvolvimento Local com Docker

```bash
# Build e iniciar todos os servicos
docker compose up --build

# Ou em background
docker compose up -d --build

# Ver logs
docker compose logs -f

# Ver logs de um servico especifico
docker compose logs -f web
docker compose logs -f celery
docker compose logs -f celery-beat
```

### Executar Migracoes

```bash
# Aplicar migracoes
docker compose exec web python manage.py migrate

# Criar superusuario (opcional)
docker compose exec web python manage.py createsuperuser
```

### Iniciar uma Campanha de Invoices

```bash
# Iniciar campanha padrao (8 execucoes = 24 horas)
docker compose exec web python manage.py start_campaign

# Com numero customizado de execucoes
docker compose exec web python manage.py start_campaign --max-executions 4

# Desativar campanhas anteriores e iniciar nova
docker compose exec web python manage.py start_campaign --deactivate-previous
```

### Parar os Servicos

```bash
docker compose down

# Remover volumes (dados do banco)
docker compose down -v
```

---

## Deploy em Producao (VPS)

### Arquitetura de Deploy

O deploy utiliza o Nginx da VPS como reverse proxy, fazendo proxy para os containers Docker:

```
Internet → Nginx (VPS:80/443) → Django Container (8000)
```

### 1. Configurar DNS

Aponte seu dominio para o IP da VPS no painel do seu provedor de DNS.

### 2. Instalar Nginx e Certbot na VPS

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

### 3. Criar arquivo de configuracao do Nginx

```bash
sudo nano /etc/nginx/sites-available/seu-dominio.com
```

Cole o conteudo (substitua `seu-dominio.com` pelo seu dominio):

```nginx
server {
    listen 80;
    server_name seu-dominio.com www.seu-dominio.com;
    client_max_body_size 50M;

    location /static/ {
        alias /caminho/do/projeto/staticfiles/;
    }

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. Ativar o site e gerar certificado SSL

```bash
# Criar link simbolico
sudo ln -s /etc/nginx/sites-available/seu-dominio.com /etc/nginx/sites-enabled/

# Testar configuracao
sudo nginx -t

# Recarregar Nginx
sudo systemctl reload nginx

# Gerar certificado SSL com Let's Encrypt
sudo certbot --nginx -d seu-dominio.com
```

### 5. Subir a aplicacao

```bash
# Clonar o repositorio
git clone <repository-url>
cd starkbank-webhook

# Configurar variaveis de ambiente
cp .env-example .env
nano .env  # Editar com suas configuracoes

# Subir containers
docker compose up -d --build

# Rodar migrations
docker compose exec web python manage.py migrate

# Coletar arquivos estaticos
docker compose exec web python manage.py collectstatic --noinput

# Copiar estaticos para o host (para o Nginx servir)
docker compose cp web:/app/staticfiles/. ./staticfiles/

# Criar superusuario
docker compose exec web python manage.py createsuperuser

# Iniciar campanha
docker compose exec web python manage.py start_campaign
```

### 6. Configurar webhook no Stark Bank

No painel do Stark Bank, configure a URL do webhook:

```
https://seu-dominio.com/api/webhook/
```

### Permissoes dos Arquivos Estaticos

Se os estaticos nao carregarem, verifique as permissoes:

```bash
# Dar permissao de leitura para o Nginx
chmod -R 755 /caminho/do/projeto/staticfiles/
```

---

## Endpoints da API

### URL Base
- **Local**: `http://localhost/api/`
- **Documentacao Swagger**: `http://localhost/api/docs/`
- **Documentacao ReDoc**: `http://localhost/`
- **OpenAPI Schema**: `http://localhost/api/schema/`

### Autenticacao

Todos os endpoints (exceto webhook) requerem header `X-API-Key`:

```bash
curl -H "X-API-Key: sua-api-key" http://localhost/api/invoices/
```

### Endpoints Disponiveis

#### Invoices

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/invoices/` | Listar todas as invoices |
| GET | `/api/invoices/{id}/` | Detalhes de uma invoice |

**Exemplo de Response:**
```json
{
    "id": 1,
    "starkbank_id": "5678901234567890",
    "amount": 15000,
    "name": "Joao Silva",
    "tax_id": "123.456.789-00",
    "status": "paid",
    "fee": 150,
    "created_at": "2024-01-15T10:30:00-03:00",
    "updated_at": "2024-01-15T11:00:00-03:00"
}
```

#### Transfers

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/transfers/` | Listar todas as transferencias |
| GET | `/api/transfers/{id}/` | Detalhes de uma transferencia |

**Exemplo de Response:**
```json
{
    "id": 1,
    "starkbank_id": "9876543210987654",
    "invoice": 1,
    "amount": 14850,
    "status": "processing",
    "created_at": "2024-01-15T11:00:00-03:00",
    "updated_at": "2024-01-15T11:00:00-03:00"
}
```

#### Webhook (Stark Bank)

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/webhook/` | Receber callbacks do Stark Bank |

**Headers Requeridos:**
- `Digital-Signature`: Assinatura digital do Stark Bank

**Eventos Processados:**
- `invoice.credited`: Dispara criacao de transferencia

---

## Celery e Tasks

### Configuracao do Celery

O Celery esta configurado em `core/celery.py` e utiliza Redis como broker.

### Tasks Disponiveis

#### `issue_invoices`
- **Descricao**: Emite 8-12 invoices aleatorias
- **Agendamento**: A cada 3 horas (via Celery Beat)
- **Controle**: Executa apenas se houver campanha ativa

#### `process_invoice_credit`
- **Descricao**: Processa invoice paga e cria transferencia
- **Trigger**: Chamada pelo webhook quando invoice e creditada
- **Retry**: Automatico com exponential backoff

### Configuracao do Beat Schedule

```python
# core/settings.py
CELERY_BEAT_SCHEDULE = {
    'issue-invoices-every-3-hours': {
        'task': 'invoices.tasks.issue_invoices',
        'schedule': 3 * 60 * 60,  # 3 horas em segundos
    },
}
```

### Monitorando Tasks

```bash
# Ver logs do worker
docker compose logs -f celery

# Ver logs do beat
docker compose logs -f celery-beat

# Acessar shell do Django
docker compose exec web python manage.py shell

# Disparar task manualmente
>>> from invoices.tasks import issue_invoices
>>> issue_invoices.delay()
```

### Retry com Exponential Backoff

As tasks estao configuradas com retry automatico:

```python
@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=60,           # Backoff inicial: 60s
    retry_backoff_max=600,      # Backoff maximo: 10min
    retry_kwargs={'max_retries': 5},
    retry_jitter=True,          # Adiciona variacao aleatoria
)
```

---

## Testes

### Executar Todos os Testes

```bash
# Via Docker
docker compose exec web python manage.py test

# Com coverage
docker compose exec web coverage run manage.py test
docker compose exec web coverage report
```

### Executar Testes Especificos

```bash
# Testes de um arquivo
docker compose exec web python manage.py test invoices.tests.test_views

# Testes de uma classe
docker compose exec web python manage.py test invoices.tests.test_tasks.IssueInvoicesTaskTest

# Um teste especifico
docker compose exec web python manage.py test invoices.tests.test_views.WebhookCallbackTest.test_webhook_invoice_credited_triggers_transfer
```

### Estrutura de Testes

| Arquivo | Cobertura |
|---------|-----------|
| `test_models.py` | Modelos e suas regras |
| `test_services.py` | Servicos do Stark Bank |
| `test_tasks.py` | Tasks do Celery |
| `test_views.py` | Endpoints da API |
| `test_business_rules.py` | Regras de negocio |

### Testes Incluidos

- Autenticacao via API Key
- Validacao de assinatura do webhook
- Processamento de eventos de invoice
- Calculo correto de valores de transferencia
- Dedupplicacao de eventos
- IP Whitelist
- Ciclo completo de campanha

---

## Observabilidade

### Sentry (Monitoramento de Erros)

Configure as variaveis de ambiente:

```env
SENTRY_DSN=https://xxx@sentry.io/xxx
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

### Logging

O sistema utiliza logging estruturado do Python:

```python
import logging
logger = logging.getLogger(__name__)

# Logs sao enviados para stdout (visivel via docker compose logs)
```

### Health Checks

O Docker Compose inclui health checks para:
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`

---

## Seguranca

### Autenticacao da API

- Endpoints protegidos por `X-API-Key` header
- API Key configurada via variavel de ambiente

### Validacao de Webhook

1. **Assinatura Digital**: Verifica `Digital-Signature` header usando SDK do Stark Bank
2. **IP Whitelist**: Opcional, restringe IPs que podem enviar webhooks
3. **Dedupplicacao**: Eventos ja processados sao ignorados

### Boas Praticas Implementadas

- Variaveis sensiveis via environment
- Chaves privadas no `.gitignore`
- Rate limiting em todos os endpoints
- Validacao de entrada via serializers
- Erros nao expõem detalhes internos

### Configurando IP Whitelist

```env
# IPs do Stark Bank (exemplo)
WEBHOOK_IP_WHITELIST=35.198.37.164,35.199.80.240
```

---

## Comandos Uteis

```bash
# Shell do Django
docker compose exec web python manage.py shell

# Shell do banco
docker compose exec db psql -U starkbank_user -d starkbank_db

# Criar novas migracoes
docker compose exec web python manage.py makemigrations

# Ver tasks agendadas
docker compose exec celery-beat celery -A starkbank_webhook inspect scheduled

# Limpar fila do Celery
docker compose exec celery celery -A starkbank_webhook purge
```

---

## Troubleshooting

### Webhook nao esta sendo recebido

1. Verifique se o endpoint esta acessivel externamente
2. Use ngrok para desenvolvimento local: `ngrok http 80`
3. Configure a URL no Stark Bank: `https://seu-ngrok.io/api/webhook/`

### Tasks nao estao executando

1. Verifique se o worker esta rodando: `docker compose logs celery`
2. Verifique se o beat esta rodando: `docker compose logs celery-beat`
3. Verifique se ha campanha ativa: `python manage.py shell` -> `InvoiceCampaign.objects.filter(is_active=True)`

### Erros de conexao com Stark Bank

1. Verifique o `STARKBANK_PROJECT_ID`
2. Verifique se a chave privada esta correta
3. Verifique o ambiente (`sandbox` vs `production`)

---

## Licenca

Este projeto foi desenvolvido como parte de um desafio tecnico para o Stark Bank.

---

## Autor

Desenvolvido por João Oliveira