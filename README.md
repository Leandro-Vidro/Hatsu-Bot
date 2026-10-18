# 🀄 Hatsu Bot — Tenhou Mahjong Tournament Manager

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.3%2B-blueviolet.svg)](https://discordpy.readthedocs.io/)
[![Google Sheets API](https://img.shields.io/badge/Google%20Sheets-API%20v4-green.svg)](https://developers.google.com/sheets/api)
[![Database](https://img.shields.io/badge/SQLite-aiosqlite-lightgrey.svg)](https://sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

O **Hatsu Bot** é um bot de Discord desenvolvido para automatizar e gerenciar torneios de **Riichi Mahjong** na plataforma [Tenhou](https://tenhou.net/), integrando sincronização de resultados com planilhas Google Sheets e automação de comandos diretamente no lobby do campeonato.

---

## 🚀 Funcionalidades

* ⏱️ **Automação de Lobby do Tenhou:** Contagem regressiva sincronizada com o lobby do Tenhou e com o canal do Discord (avisos em 5m, 3m, 1m, 10s e contagem 3-2-1), iniciando todas as mesas em paralelo.
* 📊 **Sincronização com Google Sheets:** Leitura automática de logs de partida do Tenhou (`tenhou.net/0/?log=...`), cálculo de colocações e pontuações, formatação dos dados e preenchimento na planilha com hiperlinks para os replays.
* 👥 **Suporte Multi-Servidor (*Multi-Guild*):** Cada servidor do Discord possui suas próprias configurações isoladas salvas em banco SQLite local (`hatsu_bot.db`), permitindo gerenciar torneios distintos simultaneamente.
* 🔒 **Segurança e Controle de Acesso:** Comandos administrativos protegidos pela permissão de Administrador do Discord (`@commands.has_permissions(administrator=True)`).

---

## ⚠️ Limitações Conhecidas & Modelo da Planilha

### 1. Casos de Empate
* **Cálculo e formatação de empates:** O bot não consegue formatar, calcular *uma* e inserir valores precisos em casos de empates. Em partidas onde dois ou mais jogadores terminam com a mesma pontuação final, a conferência e o ajuste de colocações e pontuações devem ser realizados manualmente na planilha.

### 2. Modelo Específico de Planilha & Importância da Aba `Partidas`
O Hatsu Bot foi desenvolvido para operar em conjunto com um **modelo específico de planilha do Google Sheets**. Ele espera encontrar abas com nomenclaturas e intervalos estruturados:
* **`Classificatória`**: Contém a lista geral de participantes e as colunas de pontuação e colocação de cada rodada classificatória.
* **`Semifinais`**: Layout dedicado às mesas de semifinal (Mesas A, B, C e D).
* **`Final`**: Layout específico para a grande final do torneio.
* **`Partidas` (Aba Central de Controle)**:
  * **Chaveamento e leitura de mesas (Lado Esquerdo):** O bot utiliza a célula `G1` para alternar dinamicamente a rodada e lê os jogadores alocados em cada mesa para iniciar partidas automaticamente via `h!StartBySheet`.
  * **Anexo de replays via hiperlink (Lado Direito):** Contém os textos pré-definidos de cada partida (`"Rodada 1 - Mesa 1"`, `"Mesa A"`, `"Final"`). Ao processar um log, o bot localiza a mesa exata correspondente aos 4 jogadores e transforma esse texto em uma fórmula clicável (`=HIPERLINK(...)`) com o replay no Tenhou.
  * **Importância:** Se a aba `Partidas` for renomeada, removida ou tiver sua estrutura modificada, o bot não conseguirá identificar o chaveamento dos jogadores nem registrar os hiperlinks dos logs.

> [!IMPORTANT]
> Um **modelo oficial em branco** da planilha (com todas as abas, células e fórmulas pré-formatadas) será disponibilizado em breve neste repositório como link para cópia. Caso utilize uma planilha com estrutura ou nomes de abas diferentes, o bot não conseguirá ler nem preencher os dados corretamente.

---

## 📋 Lista de Comandos

O prefixo padrão do bot é `h!`.

| Comando | Descrição | Permissão |
| :--- | :--- | :---: |
| `h!SetGetLog [#canal \| id]` | Configura o canal de texto onde o bot escutará e coletará os logs de partida do Tenhou. Se nenhum canal for informado, define o canal atual. | 🛡️ Admin |
| `h!GetLog <on \| off>` | Ativa ou desativa o monitoramento automático de logs no servidor. | 🛡️ Admin |
| `h!SetTorneio <planilha_id>` | Define o ID da planilha do Google Sheets que receberá os dados das partidas. | 🛡️ Admin |
| `h!SetRodada <fase> <rodada>` | Define a fase atual (`Classificatória`, `Semifinais` ou `Final`) e o número da rodada. | 🛡️ Admin |
| `h!Seted` | Exibe o status e as configurações ativas do servidor (GetLog, canal, planilha e rodada). | 🛡️ Admin |
| `h!StartBySheet <id_torneio> <tempo> [random]` | Lê as mesas diretamente da planilha Google Sheets configurada e inicia o cronômetro no Tenhou e Discord. | 🛡️ Admin |
| `h!StartMatch <jogadores> <id_torneio> <tempo> [random]` | Inicia partidas no Tenhou passando a lista de jogadores manualmente (`p1,p2,p3,p4/p5,p6,p7,p8`). | 🛡️ Admin |

---

## 🛠️ Instalação e Configuração

### Pré-requisitos
* **Python 3.10** ou superior instalado.
* Uma aplicação e bot criados no [Discord Developer Portal](https://discord.com/developers/applications).
* Um projeto configurado no [Google Cloud Console](https://console.cloud.google.com/) com a **Google Sheets API** ativada e credenciais OAuth 2.0 (Desktop).

### 1. Clonar o repositório
```bash
git clone https://github.com/Leandro-Vidro/Hatsu-Bot.git
cd Hatsu-Bot
```

### 2. Criar e ativar o ambiente virtual (Recomendado)
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar as dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar as credenciais (`tokens.json`)
Copie o arquivo de exemplo `tokens.example.json` para `tokens.json`:
```bash
cp tokens.example.json tokens.json
```
Abra o `tokens.json` e preencha com:
1. `discord_token`: O token do seu bot do Discord.
2. `google_credentials`: O JSON de credenciais baixado do Google Cloud Console (OAuth 2.0 Desktop).

```json
{
  "discord_token": "SEU_DISCORD_BOT_TOKEN_AQUI",
  "google_credentials": {
    "installed": {
      "client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
      "project_id": "SEU_PROJECT_ID",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_secret": "SEU_CLIENT_SECRET",
      "redirect_uris": [
        "http://localhost"
      ]
    }
  },
  "google_token": null
}
```

> [!NOTE]
> Na primeira vez que uma operação do Google Sheets for executada, uma tela de autorização do Google abrirá no navegador para conceder acesso às planilhas. O token de sessão será gerado e salvo automaticamente no `tokens.json`.

---

## 🏃 Como Rodar

Com o ambiente ativado e o `tokens.json` configurado:
```bash
python bot.py
```

---

## 📁 Estrutura do Projeto

```text
├── bot.py             # Comandos do Discord e listeners de eventos
├── database.py        # Gerenciamento de banco de dados SQLite (aiosqlite)
├── torneio.py         # Integração com a Google Sheets API e formatação de resultados
├── StartTenhou.py     # Automação de contagem e início de partidas no Tenhou
├── TenhouLog.py       # Integração com APIs do Tenhou e Nodocchi
├── requirements.txt   # Dependências Python
├── tokens.example.json# Modelo de configuração de tokens
├── LICENSE            # Licença MIT
└── README.md          # Documentação do projeto
```

---

## 📄 Licença

Este projeto está sob a licença [MIT](LICENSE).
