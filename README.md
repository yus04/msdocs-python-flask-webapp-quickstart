# Deploy a Python (Flask) web app to Azure App Service - Sample Application

> **注意:** このリポジトリは [Azure-Samples/msdocs-python-flask-webapp-quickstart](https://github.com/Azure-Samples/msdocs-python-flask-webapp-quickstart) をフォークしたプロジェクトです。オリジナルに加えて、Azure Application Insights による OpenTelemetry 自動計装（マネージド ID 認証）と PostgreSQL を使った挨拶履歴の保存・削除機能を追加しています。

This is the sample Flask application for the Azure Quickstart [Deploy a Python (Django or Flask) web app to Azure App Service](https://docs.microsoft.com/en-us/azure/app-service/quickstart-python). For instructions on how to create the Azure resources and deploy the application to Azure, refer to the Quickstart article.

Sample applications are available for the other frameworks here:

* Django [https://github.com/Azure-Samples/msdocs-python-django-webapp-quickstart](https://github.com/Azure-Samples/msdocs-python-django-webapp-quickstart)
* FastAPI [https://github.com/Azure-Samples/msdocs-python-fastapi-webapp-quickstart](https://github.com/Azure-Samples/msdocs-python-fastapi-webapp-quickstart)

If you need an Azure account, you can [create one for free](https://azure.microsoft.com/en-us/free/).

---

## デプロイ前の共通事前準備

以下の手順は Application Insights・PostgreSQL の両方で共通して必要です。

### 1. App Service のシステム割り当てマネージド ID を有効化する

```bash
az webapp identity assign \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP>
```

出力された `principalId` を以降の手順で使用します。

---

## Azure Application Insights による OpenTelemetry 自動計装

`app.py` に OpenTelemetry の自動計装コードを追加しています。マネージド ID で認証し、テレメトリを Application Insights に送信します。接続文字列は「どのリソースに送るか」を指定するためのもので、マネージド ID 認証時は接続文字列内のキーは認証に使用されません。

### 必要な作業手順

#### 1. Monitoring Metrics Publisher ロールを付与する

```bash
az role assignment create \
  --assignee <PRINCIPAL_ID> \
  --role "Monitoring Metrics Publisher" \
  --scope <APPLICATION_INSIGHTS_RESOURCE_ID>
```

`APPLICATION_INSIGHTS_RESOURCE_ID` は以下で確認できます。

```bash
az monitor app-insights component show \
  --app <APPLICATION_INSIGHTS_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --query id -o tsv
```

#### 2. アプリ設定に接続文字列を追加する

接続文字列は送信先リソースの識別に使用します（認証はマネージド ID で行います）。

Azure Portal の場合: App Service → **構成** → **アプリケーション設定** → **新しいアプリケーション設定** から追加します。

Azure CLI の場合:

```bash
az webapp config appsettings set \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="<CONNECTION_STRING>"
```

接続文字列は Azure Portal の Application Insights リソース → **概要** → **接続文字列** から取得できます。

#### 3. アプリを再起動する

```bash
az webapp restart \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP>
```

### ローカル開発時の注意

`APPLICATIONINSIGHTS_CONNECTION_STRING` 環境変数が未設定の場合、計装コードはスキップされます。ローカルでは通常どおり Flask アプリとして起動できます。

---

## PostgreSQL による挨拶履歴の保存・削除

マネージド ID のアクセストークンをパスワードとして使用するパスワードレス接続で PostgreSQL に接続します。`POSTGRES_PASSWORD` の設定は不要です。

### 機能概要

| 機能 | 説明 |
|---|---|
| 履歴保存 | 名前を送信すると `greetings` テーブルに名前と入力日時 (UTC) を INSERT |
| 履歴一覧 | `/hello` 画面に DB から取得したデータであることが分かる形で全件表示 |
| 個別削除 | 各行の削除ボタンで指定レコードを DELETE し画面を再描画 |
| テーブル自動作成 | 起動時に `CREATE TABLE IF NOT EXISTS` でテーブルを自動作成 |

### 必要な環境変数

| 変数名 | 説明 | デフォルト |
|---|---|---|
| `POSTGRES_HOST` | PostgreSQL サーバーのホスト名 | （必須） |
| `POSTGRES_DB` | データベース名 | （必須） |
| `POSTGRES_USER` | PostgreSQL に Entra 管理者として登録した際の値 | （必須） |
| `POSTGRES_PORT` | ポート番号 | `5432` |
| `POSTGRES_SSLMODE` | SSL モード | `require` |

`POSTGRES_HOST` が未設定の場合はテーブル初期化をスキップするため、DB なしでも起動できます（名前送信時はエラーになります）。

### PostgreSQL マネージド ID 接続の事前設定

#### 1. PostgreSQL Flexible Server で Microsoft Entra 認証を有効化する

Azure Portal: PostgreSQL リソース → **認証** → **Microsoft Entra 認証のみ** または **PostgreSQL と Microsoft Entra の両方** を選択して保存します。

#### 2. マネージド ID を PostgreSQL の Entra 管理者ユーザーとして追加する

```bash
az postgres flexible-server ad-admin create \
  --server-name <POSTGRES_SERVER_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --display-name <APP_SERVICE_NAME> \
  --object-id <PRINCIPAL_ID>
```

#### 3. App Service のアプリ設定に接続情報を追加する

```bash
az webapp config appsettings set \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings \
    POSTGRES_HOST="<SERVER>.postgres.database.azure.com" \
    POSTGRES_DB="<DATABASE_NAME>" \
    POSTGRES_USER="<APP_SERVICE_NAME>"
```

---

## Azure Blob Storage による PDF 表示

マネージド ID を使って Azure Blob Storage のコンテナーから PDF ファイルの一覧を取得し、`/hello` 画面にインライン表示します。コンテナー内に PDF 以外のファイルが含まれている場合はエラーを返します。

### 機能概要

| 機能 | 説明 |
|---|---|
| PDF 一覧取得 | コンテナー内の全 Blob を列挙し、PDF ファイル名を取得 |
| PDF インライン表示 | `/hello` 画面の挨拶履歴テーブルの下に PDF を埋め込み表示 |
| 非 PDF 検出 | PDF 以外のファイルが含まれている場合は画面にエラーを表示 |
| 未設定検出 | 必要な環境変数が未設定の場合は `RuntimeError` を返し画面にエラーを表示 |

### 必要な環境変数

| 変数名 | 説明 |
|---|---|
| `AZURE_STORAGE_ACCOUNT_NAME` | Blob Storage アカウント名 |
| `AZURE_STORAGE_CONTAINER_NAME` | PDF が格納されているコンテナー名 |

いずれかが未設定の場合は Storage セクションにエラーメッセージを表示します（DB セクションは引き続き動作します）。

### Blob Storage マネージド ID 接続の事前設定

#### 1. Storage Blob データ閲覧者ロールを付与する

```bash
STORAGE_RESOURCE_ID=$(az storage account show \
  --name <STORAGE_ACCOUNT_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --query id -o tsv)

az role assignment create \
  --assignee <PRINCIPAL_ID> \
  --role "Storage Blob Data Reader" \
  --scope "$STORAGE_RESOURCE_ID"
```

コンテナー単位でスコープを絞る場合は `--scope` に以下を指定します。

```
/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Storage/storageAccounts/<STORAGE_ACCOUNT_NAME>/blobServices/default/containers/<CONTAINER_NAME>
```

#### 2. App Service のアプリ設定に接続情報を追加する

```bash
az webapp config appsettings set \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings \
    AZURE_STORAGE_ACCOUNT_NAME="<STORAGE_ACCOUNT_NAME>" \
    AZURE_STORAGE_CONTAINER_NAME="<CONTAINER_NAME>"
```

#### 3. アプリを再起動する

```bash
az webapp restart \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP>
```

### ローカル開発時の注意

`AZURE_STORAGE_ACCOUNT_NAME` または `AZURE_STORAGE_CONTAINER_NAME` が未設定の場合、Storage セクションはエラー表示になります。ローカルでテストする場合は `DefaultAzureCredential` による認証（`az login` 後）を使うか、環境変数を設定した上で Storage エミュレーター（Azurite）を利用してください。

