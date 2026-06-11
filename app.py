import logging
import os

import psycopg2
from azure.identity import ManagedIdentityCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)

# APPLICATIONINSIGHTS_CONNECTION_STRING 環境変数が設定されている場合に
# Azure Application Insights への OpenTelemetry 自動計装を有効化する。
# Azure リソース上での認証にはマネージド ID を使用する。
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor(
        credential=ManagedIdentityCredential(),
    )

app = Flask(__name__)

# PostgreSQL へのパスワードレス接続に使用するマネージド ID 資格情報
_mi_credential = ManagedIdentityCredential()
_POSTGRES_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

# DB 設定に必要な環境変数がすべて揃っているか確認する
_REQUIRED_DB_VARS = ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER")
_missing_db_vars = [v for v in _REQUIRED_DB_VARS if not os.environ.get(v)]
_db_configured = len(_missing_db_vars) == 0


def get_db_connection():
    """マネージド ID のアクセストークンを取得して PostgreSQL に接続する。"""
    if not _db_configured:
        raise RuntimeError(
            "DB 接続に必要な環境変数が設定されていません: {}".format(", ".join(_missing_db_vars))
        )
    token = _mi_credential.get_token(_POSTGRES_TOKEN_SCOPE)
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=token.token,
        sslmode=os.environ.get("POSTGRES_SSLMODE", "require"),
    )


def init_db():
    """起動時にテーブルが存在しなければ作成する。"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS greetings (
                    id        SERIAL PRIMARY KEY,
                    name      TEXT        NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


# DB 設定が揃っている場合のみ初期化を試みる
if _db_configured:
    try:
        init_db()
    except Exception as e:
        logging.warning("init_db failed: %s", e)


@app.route('/')
def index():
    print('Request for index page received')
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/hello', methods=['POST'])
def hello():
    name = request.form.get('name')

    if name:
        print('Request for hello page received with name=%s' % name)
        conn = None
        try:
            conn = get_db_connection()
            # 名前と時刻を INSERT
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO greetings (name) VALUES (%s)",
                    (name,),
                )
            conn.commit()
            # 全件 SELECT
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, created_at FROM greetings ORDER BY created_at DESC"
                )
                records = cur.fetchall()
            return render_template('hello.html', name=name, records=records)
        except Exception as e:
            app.logger.exception("DB error in /hello")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return render_template(
                'index.html',
                db_error="DB にアクセスできません。({}: {})".format(type(e).__name__, e)
            )
        finally:
            if conn:
                conn.close()
    else:
        print('Request for hello page received with no name or blank name -- redirecting')
        return redirect(url_for('index'))


@app.route('/delete/<int:record_id>', methods=['POST'])
def delete(record_id):
    """指定した ID のレコードを削除して hello 画面を再表示する。"""
    name = request.form.get('name', '')
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM greetings WHERE id = %s", (record_id,))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, created_at FROM greetings ORDER BY created_at DESC"
            )
            records = cur.fetchall()
        return render_template('hello.html', name=name, records=records)
    except Exception as e:
        app.logger.exception("DB error in /delete")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return render_template(
            'index.html',
            db_error="DB にアクセスできません。({}: {})".format(type(e).__name__, e)
        )
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    app.run()
