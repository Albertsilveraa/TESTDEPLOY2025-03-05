# modules/db_schema.py

import logging

class DBSchemaAgent:
    """
    Agente encargado de conectarse a la base de datos, extraer el esquema completo y cachearlo para optimizar múltiples lecturas.
    El esquema incluye:
      - Tablas disponibles (con opción de filtrar tablas principales)
      - Columnas de cada tabla (nombre, tipo y si es clave primaria)
      - Relaciones entre tablas (llaves foráneas)
      - Datos de muestra (opcional)
    """

    def __init__(self, get_connection, db_name, main_tables=None, include_sample_data=True):
        """
        :param get_connection: Función que retorna una conexión a la base de datos.
        :param db_name: Nombre del esquema (base de datos) a utilizar.
        :param main_tables: Lista de nombres de tablas principales a procesar. Si se especifica, solo estas tablas se incluirán.
        :param include_sample_data: Si es True, extrae las 2 primeras filas de cada tabla.
        """
        self.get_connection = get_connection
        self.db_name = db_name
        self.main_tables = main_tables  # tabla_1 , tabla_2 correspondiente a la base de datos
        self.include_sample_data = include_sample_data
        self.cached_schema = None  # Cache para evitar múltiples lecturas
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_schema_dict(self):
        """
        Extrae el esquema de la base de datos y lo retorna en forma de diccionario.
        Se utiliza una caché interna para evitar lecturas repetitivas.
        """
        if self.cached_schema:
            return self.cached_schema

        conn = self.get_connection()
        cursor = conn.cursor()
        schema_dict = {}

        try:
            # Intentamos desactivar ONLY_FULL_GROUP_BY para la sesión actual (opcional según la configuración del servidor)
            try:
                cursor.execute(
                    "SET SESSION sql_mode=(SELECT REPLACE(@@sql_mode, 'ONLY_FULL_GROUP_BY', ''));"
                )
            except Exception as e:
                self.logger.warning("No se pudo modificar el modo de sesión: %s", e)

            # Obtener la lista de tablas, filtrando si se ha especificado main_tables.
            if self.main_tables:
                placeholders = ','.join(['%s'] * len(self.main_tables))
                query = f"""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s 
                      AND table_name IN ({placeholders});
                """
                params = [self.db_name] + self.main_tables
            else:
                query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s;
                """
                params = (self.db_name,)

            cursor.execute(query, params)
            tables = cursor.fetchall()

            for (table_name,) in tables:
                # Consultar las columnas de la tabla, ordenadas por posición.
                cursor.execute("""
                    SELECT column_name, data_type, column_key
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (self.db_name, table_name))
                columns_data = cursor.fetchall()

                # Consultar las relaciones (llaves foráneas) de la tabla.
                cursor.execute("""
                    SELECT column_name, referenced_table_name, referenced_column_name
                    FROM information_schema.key_column_usage
                    WHERE table_schema = %s 
                      AND table_name = %s
                      AND referenced_table_name IS NOT NULL;
                """, (self.db_name, table_name))
                relations = cursor.fetchall()

                # Extraer las dos primeras filas de la tabla, si se ha habilitado esta opción.
                sample_data = []
                if self.include_sample_data:
                    try:
                        sample_query = f"SELECT * FROM `{table_name}` LIMIT 2;"
                        cursor.execute(sample_query)
                        sample_rows = cursor.fetchall()
                        columns_names = [desc[0] for desc in cursor.description] if cursor.description else []
                        sample_data = [dict(zip(columns_names, row)) for row in sample_rows]
                    except Exception as e:
                        self.logger.error("Error al obtener datos de muestra para la tabla %s: %s", table_name, e)
                        sample_data = []

                # Construir el diccionario para la tabla.
                schema_dict[table_name] = {
                    "columns": {
                        col[0]: {
                            "type": col[1],
                            "key": col[2]
                        } for col in columns_data
                    },
                    "relations": [
                        {
                            "column": rel[0],
                            "referenced_table": rel[1],
                            "referenced_column": rel[2]
                        } for rel in relations
                    ],
                    "sample_data": sample_data
                }

            # Cacheamos el esquema obtenido
            self.cached_schema = schema_dict
            return schema_dict

        finally:
            cursor.close()
            conn.close()

    def get_schema_text(self):
        """
        Retorna el esquema en un formato legible por humanos.
        """
        schema_dict = self.get_schema_dict()
        lines = []
        for table, details in schema_dict.items():
            lines.append(f"Tabla: {table}")
            # Descripción de columnas.
            col_descriptions = []
            for col, info in details["columns"].items():
                pk_label = " [PK]" if info["key"] == "PRI" else ""
                col_descriptions.append(f"{col} ({info['type']}{pk_label})")
            lines.append("Columnas: " + ", ".join(col_descriptions))
            
            # Mostrar filas de muestra (si se habilita).
            if self.include_sample_data:
                if details["sample_data"]:
                    lines.append("Filas de muestra:")
                    for row in details["sample_data"]:
                        row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                        lines.append(row_str)
                else:
                    lines.append("Filas de muestra: No hay datos")
            
            # Mostrar relaciones (llaves foráneas).
            for rel in details["relations"]:
                lines.append(f"FK en {table}.{rel['column']} -> {rel['referenced_table']}.{rel['referenced_column']}")
            lines.append("-" * 50)
        return "\n".join(lines)
