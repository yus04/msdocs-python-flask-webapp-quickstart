# Deploy a Python (Flask) web app to Azure App Service - Sample Application

> **注意:** このリポジトリは [Azure-Samples/msdocs-python-flask-webapp-quickstart](https://github.com/Azure-Samples/msdocs-python-flask-webapp-quickstart) をフォークしたプロジェクトです。オリジナルに加えて、Azure Application Insights による OpenTelemetry 自動計装（マネージド ID 認証）を追加しています。

This is the sample Flask application for the Azure Quickstart [Deploy a Python (Django or Flask) web app to Azure App Service](https://docs.microsoft.com/en-us/azure/app-service/quickstart-python). For instructions on how to create the Azure resources and deploy the application to Azure, refer to the Quickstart article.

Sample applications are available for the other frameworks here:

* Django [https://github.com/Azure-Samples/msdocs-python-django-webapp-quickstart](https://github.com/Azure-Samples/msdocs-python-django-webapp-quickstart)
* FastAPI [https://github.com/Azure-Samples/msdocs-python-fastapi-webapp-quickstart](https://github.com/Azure-Samples/msdocs-python-fastapi-webapp-quickstart)

If you need an Azure account, you can [create one for free](https://azure.microsoft.com/en-us/free/).

---

## Azure Application Insights による OpenTelemetry 自動計装

このフォークでは `app.py` に OpenTelemetry の自動計装コードを追加しています。テレメトリの送信先に Azure Application Insights を使用し、認証にはマネージド ID を使います。

### 必要な作業手順

以下の手順はすべて App Service へのデプロイ後に実施してください。

#### 1. App Service のシステム割り当てマネージド ID を有効化する

Azure Portal または Azure CLI で有効化します。

```bash
az webapp identity assign \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP>
```

出力された `principalId` を次の手順で使用します。

#### 2. Application Insights リソースへのロールを付与する

マネージド ID（サービスプリンシパル）に **Monitoring Metrics Publisher** ロールを付与します。

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

#### 3. アプリ設定に接続文字列を追加する

App Service のアプリ設定に `APPLICATIONINSIGHTS_CONNECTION_STRING` を追加します。

```bash
az webapp config appsettings set \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="<CONNECTION_STRING>"
```

接続文字列は Azure Portal の Application Insights リソース → **概要** → **接続文字列** から取得できます。

#### 4. アプリを再起動する

設定変更を反映するためにアプリを再起動します。

```bash
az webapp restart \
  --name <APP_SERVICE_NAME> \
  --resource-group <RESOURCE_GROUP>
```

### ローカル開発時の注意

`APPLICATIONINSIGHTS_CONNECTION_STRING` 環境変数が未設定の場合、計装コードはスキップされます。ローカルでは通常どおり Flask アプリとして起動できます。

ローカルでも Application Insights に送信したい場合は、`.env` ファイルなどに接続文字列を設定してください（その場合は `ManagedIdentityCredential` の代わりに `DefaultAzureCredential` の使用を検討してください）。
