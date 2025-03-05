# app.py

import mysql.connector
import pandas as pd
import datetime
import re

from db_schema import DBSchemaAgent
from semantic_mapping import SemanticMappingAgent
from query_interpreter import UserQueryAgent
from sql_generator import SQLGenerationAgent
from query_executor import QueryExecutor
from response_formatter import ResponseFormatter
from data_analyzer import DataAnalysisAgent


def infer_table_from_query(query, semantic_map):
    """
    Intenta inferir la tabla a consultar a partir de la consulta en lenguaje natural
    y del mapa semántico.
    """
    query_lower = query.lower()
    # Buscar coincidencia completa en el nombre humanizado
    for table, info in semantic_map.items():
        human_table = info.get("human_name", table).lower()
        if human_table in query_lower:
            return table

    # Buscar coincidencias parciales (por palabra)
    for table, info in semantic_map.items():
        human_table = info.get("human_name", table).lower()
        for word in human_table.split():
            if word in query_lower:
                return table

    # Fallback: retornar la primera tabla si existe
    if semantic_map:
        return list(semantic_map.keys())[0]
    return None


def es_consulta_asistente(prompt):
    
    prompt_lower = prompt.lower()
    palabras_clave = [
        "que haces", "qué haces", "qué puedes hacer", "que puedes hacer", 
        "funcionalidades", "ayuda", "ayudame", "ayúdame", "como funciona", 
        "cómo funciona", "para que sirves", "para qué sirves", "instrucciones",
        "como te uso", "cómo te uso", "ejemplos", "guía", "guia", "tutorial",
        "dime que haces", "explícame", "explicame", "capacidades", "hola",
        "eres un asistente", "asistente", "puedes ayudarme"
    ]
    
    for palabra in palabras_clave:
        if palabra in prompt_lower:
            return True
    
    palabras = prompt_lower.split()
    if len(palabras) < 5 and any(palabra in ["cómo", "como", "qué"] for palabra in palabras):
        return True
        
    return False


def obtener_mensaje_asistente():
    """
    Genera un mensaje detallado del asistente explicando sus capacidades.
    """
    mensaje = """
# 🤖 Asistente Virtual para Base de Datos de Detección de Vehículos

Soy un asistente especializado en ayudarte a extraer y analizar información de la base de datos de detección de vehículos. Puedo entender tus consultas en lenguaje natural y transformarlas en búsquedas precisas.

## ¿Qué puedo hacer por ti?

### 📊 Consultas Básicas
- **Contar vehículos**: "¿Cuántos vehículos rojos se detectaron ayer?"
- **Listar registros**: "Muestra todas las detecciones de placas que empiecen con ABC"
- **Buscar específicos**: "Encuentra el vehículo con placa XYZ-123"

### 📈 Análisis de Datos
- **Comparativas**: "Compara la cantidad de vehículos azules vs. rojos en la última semana"
- **Tendencias temporales**: "Muestra la evolución de detecciones por día del mes pasado"
- **Estadísticas**: "¿Cuál es el color de vehículo más común en las detecciones?"

### 🔍 Filtros Avanzados
- **Por fechas**: "Detecciones entre el 10 de enero y el 15 de febrero"
- **Por precisión**: "Vehículos detectados con más del 90% de precisión"
- **Combinados**: "Carros rojos detectados después de las 18:00 con placas que contengan '5'"

## 📝 Ejemplos de consultas que puedes hacer:

1. "¿Cuántos vehículos se detectaron hoy?"
2. "Muestra los 10 últimos vehículos de color negro"
3. "¿Cuántas detecciones tuvieron una precisión mayor al 85%?"
4. "Compara la cantidad de detecciones entre la semana pasada y la anterior"
5. "¿Qué placas se detectaron más de 3 veces este mes?"

¿En qué te puedo ayudar hoy?
"""
    return mensaje

def get_chart_type_name(chart_type):
    """
    Retorna el nombre legible del tipo de gráfico.
    """
    chart_names = {
        "bar": "gráfico de barras",
        "line": "gráfico de líneas",
        "area": "gráfico de área"
    }
    return chart_names.get(chart_type, chart_type)


def check_if_chart_request(query):
    """
    Detecta si la consulta del usuario está solicitando un gráfico.
    
    :param query: Consulta del usuario
    :return: (bool, str) - Indica si es una solicitud de gráfico y el tipo
    """
    query_lower = query.lower()
    
    chart_keywords = {
        "gráfico de barras": "bar",
        "grafico de barras": "bar", 
        "gráfica de barras": "bar",
        "grafica de barras": "bar",
        "muestra en barras": "bar",
        "graficar en barras": "bar",
        "visualizar en barras": "bar",
        
        "gráfico de líneas": "line",
        "grafico de lineas": "line",
        "gráfica de líneas": "line",
        "grafica de lineas": "line",
        "muestra en líneas": "line",
        "muestra en lineas": "line",
        "graficar en líneas": "line",
        "graficar en lineas": "line",
        "visualizar en líneas": "line",
        "visualizar en lineas": "line",
        
        "gráfico de área": "area",
        "grafico de area": "area",
        "gráfica de área": "area",
        "grafica de area": "area",
        "muestra en área": "area",
        "muestra en area": "area",
        "graficar en área": "area",
        "graficar en area": "area",
        "visualizar en área": "area",
        "visualizar en area": "area"
    }
    
    for keyword, chart_type in chart_keywords.items():
        if keyword in query_lower:
            return True, chart_type
    return False, None


def process_query(prompt, db_config, openai_api_key):
    """
    Procesa la consulta del usuario:
      - Verifica si es para el asistente.
      - Detecta si se solicita un gráfico.
      - Extrae el esquema y genera el mapa semántico.
      - Interpreta la consulta en lenguaje natural.
      - Infiera la tabla si no se indica.
      - Genera y ejecuta la consulta SQL.
      - Formatea la respuesta (incluyendo análisis de datos si corresponde).
    """
    # Verificar si es una consulta para el asistente
    if es_consulta_asistente(prompt):
        return {
            "estructura_consulta": {},
            "sql": "",
            "resultados": {},
            "formatted_response": obtener_mensaje_asistente(),
            "analysis_result": None
        }
    
    # Verificar si es una solicitud de gráfico
    is_chart_request, chart_type = check_if_chart_request(prompt)

    def get_connection():
        return mysql.connector.connect(
            host=db_config.get("host", "localhost"),
            user=db_config.get("user", ""),
            password=db_config.get("password", ""),
            database=db_config.get("database", ""),
            port=db_config.get("port", 3306)
        )

    db_name = db_config.get("database", "")

    # Extraer el esquema
    db_agent = DBSchemaAgent(get_connection, db_name, main_tables=None, include_sample_data=False)
    schema = db_agent.get_schema_dict()

    # Generar el mapa semántico
    semantic_agent = SemanticMappingAgent(custom_rules=None)
    semantic_map = semantic_agent.generate_map(schema)

    # Interpretar la consulta en lenguaje natural (usando OpenAI)
    user_query_agent = UserQueryAgent(llm_api_key=openai_api_key, model="gpt-3.5-turbo", temperature=0.0)
    estructura_consulta = user_query_agent.interpretar_consulta(prompt, schema, semantic_map)
    
    # Verificar si tenemos múltiples consultas
    is_multiple_queries = isinstance(estructura_consulta, list) and len(estructura_consulta) > 0
    
    if is_multiple_queries:
        estructura_principal = estructura_consulta[0]  # Tomamos la primera consulta
    else:
        estructura_principal = estructura_consulta

    # Si no hay tabla en la estructura, intentamos inferirla
    if not estructura_principal.get("tabla"):
        inferred_table = infer_table_from_query(prompt, semantic_map)
        estructura_principal["tabla"] = inferred_table
        
    # Si hay múltiples consultas, asegurarse de que todas tengan una tabla asignada
    if is_multiple_queries:
        for i in range(len(estructura_consulta)):
            if not estructura_consulta[i].get("tabla"):
                estructura_consulta[i]["tabla"] = inferred_table

    # Generar la consulta SQL
    sql_generator = SQLGenerationAgent(limit=25)
    sql = sql_generator.generar_sql(estructura_consulta, schema)

    # Ejecutar la consulta SQL
    query_executor = QueryExecutor(get_connection)
    if isinstance(sql, list):  # Si hay varias consultas
        resultados = [query_executor.ejecutar_sql(q) for q in sql]
    else:  # Si es solo una consulta
        resultados = query_executor.ejecutar_sql(sql)

    # Formatear la respuesta en lenguaje natural usando GPT, pasando la consulta SQL
    response_formatter = ResponseFormatter(openai_api_key)
    if isinstance(resultados, list):
        formatted_responses = [
            response_formatter.formatear_respuesta(res, estructura_consulta[i], consulta_sql=q)
            for i, (res, q) in enumerate(zip(resultados, sql))
        ]
        # Si es una solicitud de gráfico, agregar un mensaje adicional
        if is_chart_request:
            formatted_responses.append(f"Generando {get_chart_type_name(chart_type)} con los datos solicitados.")
        formatted_response = "\n\n".join(formatted_responses)
    else:
        formatted_response = response_formatter.formatear_respuesta(resultados, estructura_consulta, consulta_sql=sql)
        if is_chart_request:
            formatted_response += f"\n\nGenerando {get_chart_type_name(chart_type)} con los datos solicitados."

    # (Opcional) Análisis estadístico si la consulta incluye columnas de fechas
    analysis_result = None
    if is_multiple_queries and isinstance(resultados, list):
        analysis_results = []
        for idx, result in enumerate(resultados):
            if result and "columns" in result and "data" in result and "timestamp" in result["columns"]:
                df = pd.DataFrame(result["data"], columns=result["columns"])
                numeric_cols = [col for col in result["columns"] if col != "timestamp"]
                if numeric_cols:
                    analysis_column = numeric_cols[0]
                    analysis_agent = DataAnalysisAgent(time_unit='ms')
                    df_converted = analysis_agent.convert_epoch_to_datetime(df.copy(), "timestamp")
                    agg_df = analysis_agent.aggregate_by_time(df_converted, "timestamp", analysis_column, freq='D')
                    analysis_results.append({"agg_data": agg_df.to_dict(orient="list")})
            else:
                analysis_results.append(None)
        
        if any(analysis_results):
            analysis_result = next((res for res in analysis_results if res is not None), None)
    else:
        if resultados and isinstance(resultados, dict) and "columns" in resultados and "data" in resultados:
            if "timestamp" in resultados["columns"]:
                df = pd.DataFrame(resultados["data"], columns=resultados["columns"])
                numeric_cols = [col for col in resultados["columns"] if col != "timestamp"]
                if numeric_cols:
                    analysis_column = numeric_cols[0]
                    analysis_agent = DataAnalysisAgent(time_unit='ms')
                    df_converted = analysis_agent.convert_epoch_to_datetime(df.copy(), "timestamp")
                    agg_df = analysis_agent.aggregate_by_time(df_converted, "timestamp", analysis_column, freq='D')
                    analysis_result = {"agg_data": agg_df.to_dict(orient="list")}

    result = {
        "estructura_consulta": estructura_consulta,
        "sql": sql,
        "resultados": resultados,
        "formatted_response": formatted_response,
        "analysis_result": analysis_result
    }
    
    # Si es una solicitud de gráfico, se incluye esa información en el resultado final
    if is_chart_request:
        result["chart_request"] = {
            "type": chart_type,
            "request": prompt
        }
    
    return result
