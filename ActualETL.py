import subprocess
import os
import shutil
from datetime import datetime
import sqlite3
import mysql.connector

config_path = "/home/actual-project/scripts/Config.txt"
src_path = "/home/actual-project/data/Budget-6eb48eb"
archive_path = "/home/actual-project/data/archives"
dest_file = "/home/actual-project/data/db.sqlite"

def read_config(file_path):

    config = {}

    with open(file_path, "r") as file:
        for line in file:
            key, value = line.strip().split("=", 1)
            config[key] = value

    return config

def update_budget_data():

    if not os.path.exists(config_path):
        print(f"Configuration file {config_path} not found.")
        return None, None
    
    config = read_config(config_path)
    env = os.environ.copy()

    env["ACTUAL_URL"] = config.get("actual_url")
    env["BUDGET_ID"] = config.get("budget_id")
    env["ACTUAL_PASSWORD"] = config.get("actual_password")
    env["BUDGET_PASSWORD"] = config.get("budget_password")
    env["MYSQL_HOST"] = config.get("mysql_host")
    env["MYSQL_USER"] = config.get("mysql_user")
    env["MYSQL_PASSWORD"] = config.get("mysql_password")
    env["MYSQL_DB"] = config.get("mysql_db")

    result = subprocess.run(
        ["node", "/home/actual-project/scripts/BudgetFetch.js"],
        env = env,
        capture_output = True,
        text = True,
    )

    if result.returncode == 0:

        files_to_move = ["db.sqlite", "cache.sqlite", "metadata.json"]
        os.makedirs(archive_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamped_archive_dir = os.path.join(archive_path, timestamp)
        os.makedirs(timestamped_archive_dir)

        print(f"Actual-Budget ETL process starting: {timestamp}")

        for file_name in files_to_move:

            src_file_path = os.path.join(src_path, file_name)

            if os.path.exists(src_file_path):
                if file_name == "db.sqlite":
                    shutil.copy(src_file_path, dest_file)
                    print(f"Updated SQLite database at {dest_file}")

                dest_archive_path = os.path.join(timestamped_archive_dir, file_name)

                shutil.move(src_file_path, dest_archive_path)

                print(f"Moved {file_name} to {dest_archive_path}")
            else:
                print(f"Warning: {file_name} not found in {src_path}")

        print("SQLite data updated and archived successfully.")

        return dest_file, env
    
    else:
        print(f"Error running Node.js script: {result.stderr}")
        return None

def map_sqlite_to_mysql_type(sqlite_type):

    sqlite_type = sqlite_type.lower()

    if 'int' in sqlite_type:
        return 'BIGINT'
    elif 'char' in sqlite_type or 'text' in sqlite_type:
        return 'TEXT'
    elif 'real' in sqlite_type or 'double' in sqlite_type or 'float' in sqlite_type:
        return 'FLOAT'
    elif 'blob' in sqlite_type:
        return 'BLOB'
    else:
        return 'TEXT'
    
def get_unique_columns(table_name, sqlite_cursor):

    sqlite_cursor.execute(f"PRAGMA table_info({table_name});")
    columns = sqlite_cursor.fetchall()
    unique_key_mapping = {
        "schedules_json_paths": "schedule_id"
    }

    if columns:
        first_column = columns[0][1].lower()

        if first_column == 'id':
            return "id"
        
    return unique_key_mapping.get(table_name, None)

def migrate_sqlite_to_mysql(sqlite_file, env):

    try:
        sqlite_conn = sqlite3.connect(sqlite_file)
        sqlite_cursor = sqlite_conn.cursor()
        mysql_conn = mysql.connector.connect(
            host=env.get("MYSQL_HOST"),
            user=env.get("MYSQL_USER"),
            password=env.get("MYSQL_PASSWORD"),
            database=env.get("MYSQL_DB")
        )
        mysql_cursor = mysql_conn.cursor()

        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = sqlite_cursor.fetchall()

        for table in tables:

            table_name = table[0]
            unique_columns = get_unique_columns(table_name, sqlite_cursor)

            print(f"Migrating table: {table_name}")

            if not unique_columns:
                print(f"Skipping table {table_name} (no unique key found).")
                continue

            print(f"Using unique column for {table_name}: {unique_columns}")

            sqlite_cursor.execute(f"PRAGMA table_info({table_name});")

            columns = sqlite_cursor.fetchall()
            column_names = [col[1] for col in columns]

            column_definitions = ', '.join([f"`{col[1]}` {map_sqlite_to_mysql_type(col[2])}" for col in columns])
            create_table_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({column_definitions}, UNIQUE({unique_columns}));"

            mysql_cursor.execute(create_table_query)
            sqlite_cursor.execute(f"SELECT * FROM {table_name};")

            rows = sqlite_cursor.fetchall()
            rows_inserted = 0
            rows_updated = 0

            for row in rows:

                column_placeholders = ', '.join(['%s'] * len(row))
                column_names_str = ', '.join([f"`{col}`" for col in column_names])
                update_clause = ', '.join([f"`{col}`=VALUES(`{col}`)" for col in column_names])
                insert_query = f"""

                INSERT INTO `{table_name}` ({column_names_str})
                VALUES ({column_placeholders})
                ON DUPLICATE KEY UPDATE {update_clause};
                """
                mysql_cursor.execute(insert_query, row)

                if mysql_cursor.rowcount == 1:
                    rows_inserted += 1
                    
                elif mysql_cursor.rowcount == 2:
                    rows_updated += 1

            mysql_conn.commit()

            print(f"Table {table_name} migration completed: {rows_inserted} rows inserted, {rows_updated} rows updated.")

        sqlite_conn.close()
        mysql_conn.close()

        print("Migration complete!")

    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    sqlite_file, env = update_budget_data()
    
    if sqlite_file and env:
        migrate_sqlite_to_mysql(sqlite_file, env)
        