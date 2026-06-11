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


def get_db_connection():
    """環境変数から PostgreSQL 接続を返す。"""
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
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


# DB 接続情報が揃っている場合のみ初期化を試みる
if os.environ.get("POSTGRES_HOST"):
    init_db()


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
        conn = get_db_connection()
        try:
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
        except Exception:
            conn.rollback()
            app.logger.exception("DB error in /hello")
            raise
        finally:
            conn.close()
        return render_template('hello.html', name=name, records=records)
    else:
        print('Request for hello page received with no name or blank name -- redirecting')
        return redirect(url_for('index'))


@app.route('/delete/<int:record_id>', methods=['POST'])
def delete(record_id):
    """指定した ID のレコードを削除して hello 画面を再表示する。"""
    name = request.form.get('name', '')
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM greetings WHERE id = %s", (record_id,))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, created_at FROM greetings ORDER BY created_at DESC"
            )
            records = cur.fetchall()
    except Exception:
        conn.rollback()
        app.logger.exception("DB error in /delete")
        raise
    finally:
        conn.close()
    return render_template('hello.html', name=name, records=records)


if __name__ == '__main__':
    app.run()
