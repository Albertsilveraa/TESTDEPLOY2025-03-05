import logging
import datetime
import openai
import json
import re

class SQLGenerationAgent:
    def __init__(self, limit=15, openai_api_key=None):
        self.limit = limit
        self.logger = logging.getLogger(self.__class__.__name__)
        if openai_api_key:
            openai.api_key = openai_api_key

    def _parse_date_reference(self, date_reference):
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Handle various date reference formats
        if date_reference.lower() in ["today", "hoy"]:
            target_date = today
        elif date_reference.lower() in ["yesterday", "ayer"]:
            target_date = today - datetime.timedelta(days=1)
        elif re.search(r'(last|pasado|pasada)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)', date_reference.lower()):
            day_names_en = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
            day_names_es = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
            
            day_match = re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday|lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)', date_reference.lower())
            if day_match:
                day_name = day_match.group(1)
                target_day = day_names_en.get(day_name) or day_names_es.get(day_name)
                days_diff = (today.weekday() - target_day) % 7
                if days_diff == 0:
                    days_diff = 7  # Retrocede una semana si hoy es el mismo día
                target_date = today - datetime.timedelta(days=days_diff)
            else:
                self.logger.warning(f"Could not parse week day from '{date_reference}', using today")
                target_date = today
        else:
            try:
                # Intentar varios formatos de fecha
                for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                    try:
                        target_date = datetime.datetime.strptime(date_reference, fmt).replace(hour=0, minute=0, second=0, microsecond=0)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Could not parse date: {date_reference}")
            except Exception as e:
                self.logger.error(f"Error parsing date '{date_reference}': {e}")
                target_date = today
        
        # Definir inicio y fin del día
        start_of_day = target_date
        end_of_day = target_date + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
        
        start_timestamp = int(start_of_day.timestamp() * 1000)
        end_timestamp = int(end_of_day.timestamp() * 1000)
        
        return start_timestamp, end_timestamp

    def _extract_date_references(self, query_text):
        # Buscar rangos de fecha (ej., "from 10-02-2024 to 28-02-2024")
        range_match = re.search(r'(?:from|del|desde)\s+(\S+)\s+(?:to|al|hasta)\s+(\S+)', query_text, re.IGNORECASE)
        if range_match:
            start_ref = range_match.group(1)
            end_ref = range_match.group(2)
            return (start_ref, end_ref)
        
        # Buscar referencias de fechas individuales
        today_pattern = re.search(r'(?:from|de|en|el|detectados?)\s+(today|hoy)', query_text, re.IGNORECASE)
        if today_pattern:
            return "today"
        yesterday_pattern = re.search(r'(?:from|de|en|el|detectados?)\s+(yesterday|ayer)', query_text, re.IGNORECASE)
        if yesterday_pattern:
            return "yesterday"
        date_pattern = re.search(r'(?:from|de|en|el|detectados?)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})', query_text, re.IGNORECASE)
        if date_pattern:
            return date_pattern.group(1)
        
        return None

    def generar_sql(self, estructura_consulta, schema, query_text=None):
        if isinstance(estructura_consulta, dict):
            estructura_consulta = [estructura_consulta]

        sql_queries = []

        for estructura in estructura_consulta:
            table = estructura.get("tabla", "")
            if not table:
                self.logger.error("Tabla no especificada en la estructura.")
                continue

            if table not in schema:
                self.logger.error(f"La tabla '{table}' no existe en el esquema.")
                continue

            processed_filters = {}
            filters = estructura.get("filtros", {})

            # Manejar columnas con múltiples valores
            multiple_value_columns = {}
            for col, val in list(filters.items()):
                if isinstance(val, list):
                    multiple_value_columns[col] = val
                    del filters[col]

            date_ref = None
            timestamp_column = None
            
            if query_text:
                date_ref = self._extract_date_references(query_text)
                # Identificar la columna de marca de tiempo (por ejemplo, init_time)
                for col, col_info in schema[table]["columns"].items():
                    col_type = col_info["type"].lower()
                    if "timestamp" in col_type or "datetime" in col_type or "date" in col_type:
                        timestamp_column = col
                        break
            
            if date_ref and timestamp_column:
                if isinstance(date_ref, tuple):
                    start_timestamp, _ = self._parse_date_reference(date_ref[0])
                    _, end_timestamp = self._parse_date_reference(date_ref[1])
                else:
                    start_timestamp, end_timestamp = self._parse_date_reference(date_ref)
                    
                processed_filters[timestamp_column] = {
                    ">=": start_timestamp,
                    "<=": end_timestamp
                }
                
                self.logger.info(f"Filtro de tiempo agregado para {timestamp_column}: {start_timestamp} a {end_timestamp}")

            # Procesar otros filtros
            for col, val in filters.items():
                if col not in schema[table]["columns"]:
                    self.logger.warning(f"La columna '{col}' no existe en la tabla '{table}'. Se omite este filtro.")
                    continue

                column_type = schema[table]["columns"][col]["type"].lower()
                is_date_field = "timestamp" in column_type or "datetime" in column_type

                if isinstance(val, dict):
                    new_val = {}
                    for op, date_str in val.items():
                        try:
                            if is_date_field and isinstance(date_str, str):
                                date_obj = datetime.datetime.strptime(date_str, "%d-%m-%Y")
                                new_val[op] = int(date_obj.timestamp() * 1000)
                            else:
                                new_val[op] = date_str
                        except Exception as e:
                            self.logger.error(f"Error procesando el filtro en la columna {col}: {e}")
                            new_val[op] = date_str
                    processed_filters[col] = new_val
                else:
                    processed_filters[col] = val

            estructura["filtros"] = processed_filters

            # Determinar si es una consulta sobre colores
            is_color_query = False
            action = estructura.get("accion", "").lower()
            if "attribute_id" in processed_filters and processed_filters["attribute_id"] == 2:
                is_color_query = True
            elif query_text and "color" in query_text.lower():
                is_color_query = True
                # Si se detecta que es sobre colores pero no tiene el attribute_id correcto, lo agregamos
                if "attribute_id" not in processed_filters:
                    processed_filters["attribute_id"] = 2
                    estructura["filtros"] = processed_filters
            
            # Preparar el prompt para la generación de SQL
            prompt = f"""
    You are an expert SQL assistant for MySQL. Convert the following query structure into a valid SQL statement.

    Query Structure:
    Table: {table}
    Filters: {json.dumps(estructura.get('filtros', {}), ensure_ascii=False)}
    Action: {estructura.get('accion', '').lower()}

    """
            # Manejar columnas con múltiples valores
            if multiple_value_columns:
                for col, values in multiple_value_columns.items():
                    prompt += f"Multiple values for column '{col}': {values}\n"

            # Agregar instrucciones específicas para acciones como 'promedio'
            column = estructura.get("columna", "")
            if action == "promedio" and column:
                prompt += f"Column for average: {column}\n"

            # Instrucciones y ejemplos para la generación de SQL
            prompt += f"""
    Rules:
    -Si la acción es "count", usar: SELECT ... COUNT(*)
    -Si existen múltiples valores para una columna, usar la cláusula IN
    -Si se necesitan agregaciones con múltiples valores, usar GROUP BY
    -Aplicar filtros en la cláusula WHERE
    -Para filtros de rango con operadores como ">=" y "<=", usar la sintaxis correcta
    -Usar valores de marca de tiempo en milisegundos
    -Limitar los resultados a {self.limit} registros
    -Para consultas complejas con varias columnas de valores, hacer agregaciones y agrupar según sea necesario
    """

            # Añadir ejemplos específicos según el tipo de consulta
            if is_color_query:
                prompt += """
    Examples for color queries:
    1. For querying colors available in the database:
    SELECT DISTINCT description
    FROM detections 
    WHERE attribute_id = 2
    AND init_time BETWEEN UNIX_TIMESTAMP('2025-03-05 00:00:00') * 1000 
                    AND UNIX_TIMESTAMP('2025-03-05 23:59:59') * 1000
    LIMIT 25;

    2. For counting detections by color:
    SELECT description, COUNT(*) AS cantidad_detecciones
    FROM detections
    WHERE attribute_id = 2
    AND init_time BETWEEN UNIX_TIMESTAMP('2025-03-05 00:00:00') * 1000 
                    AND UNIX_TIMESTAMP('2025-03-05 23:59:59') * 1000
    GROUP BY description
    LIMIT 25;

    3. For querying specific color:
    SELECT *
    FROM detections
    WHERE attribute_id = 2
    AND description = 'Rojo'
    AND init_time BETWEEN UNIX_TIMESTAMP('2025-03-05 00:00:00') * 1000 
                    AND UNIX_TIMESTAMP('2025-03-05 23:59:59') * 1000
    LIMIT 25;
    """
            else:
                prompt += """
    Examples:
    -> Cantidad de detecciones por cámara:
    SELECT lEFT(object_id, LENGTH(object_id) - 27) AS Camara_Id,
        attribute_id,
        count(attribute_id) 
    FROM   detections
    WHERE  init_time BETWEEN UNIX_TIMESTAMP('2025-02-27 00:00:00') * 1000 
                        AND UNIX_TIMESTAMP('2025-02-27 23:59:59') * 1000
    group by 1,2
    LIMIT 25;

    -> Cantidad de detecciones por cámara en un período de tiempo:
    SELECT LEFT(object_id, LENGTH(object_id) - 27) AS Camara_Id, 
        attribute_id,
        count(attribute_id) 
    FROM detections
    WHERE init_time BETWEEN UNIX_TIMESTAMP('2025-02-27 00:00:00') * 1000 
                    AND UNIX_TIMESTAMP('2025-02-27 23:59:59') * 1000
    GROUP BY 1, 2
    LIMIT 25;
    """

            prompt += """
    Con estos datos, puedes crear las consultas SQL de acuerdo a lo que se te pida.

    Respond only with the generated SQL query.
    """
            try:
                # Llamada a OpenAI para generar la consulta SQL
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                sql_query = response["choices"][0]["message"]["content"].strip()
                sql_queries.append(sql_query)
            except Exception as e:
                self.logger.error(f"Error generating SQL with OpenAI: {e}")
                sql_queries.append(None)

        return sql_queries if len(sql_queries) > 1 else (sql_queries[0] if sql_queries else None)