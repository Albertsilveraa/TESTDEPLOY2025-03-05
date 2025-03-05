import openai

class ResponseFormatter:
    """
    Agente encargado de formatear los resultados obtenidos de la consulta SQL en una respuesta
    legible en lenguaje natural, utilizando GPT-3.5 para mejorar la legibilidad.
    """

    def __init__(self, api_key):
        """
        Inicializa el formateador con la clave API de OpenAI.
        
        :param api_key: Clave de API para usar OpenAI.
        """
        openai.api_key = api_key
        # Almacenar resultados de consultas para combinar comparativas
        self.cache_resultados = []
        self.cache_estructura = []
        self.cache_sql = []

    def _generar_respuesta_con_gpt(self, prompt):
        """
        Envía un prompt a OpenAI para obtener una respuesta en lenguaje natural.

        :param prompt: Texto a enviar como prompt.
        :return: Respuesta generada por GPT.
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente amigable y útil que explica información de bases de datos en términos sencillos para personas sin conocimientos técnicos. Para consultas comparativas, ofrece análisis detallado de las diferencias, proporciones y tendencias."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )
            return response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error al generar respuesta con GPT: {str(e)}"

    def detectar_consulta_comparativa(self, estructura_consulta, consulta_sql):
        """
        Detecta si una consulta es parte de una serie comparativa.
        
        :return: Boolean indicando si es potencialmente comparativa
        """
        if isinstance(estructura_consulta, dict) and estructura_consulta.get("accion") == "contar":
            # Buscar patrones en la consulta SQL que sugieran comparación
            if consulta_sql and "WHERE" in consulta_sql.upper() and "=" in consulta_sql:
                # Extraer la columna y valor de comparación
                partes = consulta_sql.upper().split("WHERE")
                if len(partes) > 1:
                    condicion = partes[1].strip()
                    # Si la condición parece ser un filtro de categoría
                    if "=" in condicion and ("description" in condicion.lower() or "color" in condicion.lower()):
                        return True
        return False

    def formatear_respuesta(self, resultados, estructura_consulta=None, consulta_sql=None):
        """
        Recibe los resultados obtenidos y genera una respuesta legible en lenguaje natural usando GPT.
        Detecta consultas comparativas y las combina apropiadamente.
        """
        # Manejar el caso de resultados múltiples (lista)
        if isinstance(resultados, list):
            # Combinamos los resultados y generamos una única respuesta
            return self._formatear_resultados_multiples(resultados, estructura_consulta, consulta_sql)

        # Si la consulta es potencialmente parte de una serie comparativa
        es_comparativa = self.detectar_consulta_comparativa(estructura_consulta, consulta_sql)
        
        if es_comparativa:
            # Almacenar esta consulta para potencial combinación
            self.cache_resultados.append(resultados)
            self.cache_estructura.append(estructura_consulta)
            self.cache_sql.append(consulta_sql)
            
            # Si tenemos varias consultas comparativas acumuladas
            if len(self.cache_resultados) >= 2:
                # Combinar los resultados para análisis comparativo
                return self._formatear_resultados_comparativos()
        else:
            # Si no es comparativa, limpiar caché
            self.cache_resultados = []
            self.cache_estructura = []
            self.cache_sql = []

        # Si la consulta SQL ya está optimizada para comparación (GROUP BY)
        if "description" in resultados.get("columns", []) and "count" in resultados.get("columns", []):
            return self._formatear_resultados_agrupados(resultados)

        # Procesamiento normal para consultas individuales
        return self._formatear_resultado_individual(resultados, estructura_consulta, consulta_sql)

    def _formatear_resultado_individual(self, resultados, estructura_consulta=None, consulta_sql=None):
        """
        Formatea un único resultado a lenguaje natural.
        """
        # Si los resultados son inválidos
        if not resultados or "columns" not in resultados or "data" not in resultados:
            return "No se encontraron resultados o hubo un problema con la consulta."

        # Si es una consulta de conteo
        accion = estructura_consulta.get("accion", "").lower() if isinstance(estructura_consulta, dict) else ""

        if accion == "contar":
            valor = resultados["data"][0][0]
            mensaje = f"La consulta SQL usada fue: '{consulta_sql}'.\n"
            mensaje += f"En resumen, tenemos un total de {valor} registros que coinciden con tu búsqueda."
            mensaje += "\n\n¿Hay algo más en lo que pueda ayudarte? 😊"
            return self._generar_respuesta_con_gpt(mensaje)

        # Generar tabla si es una consulta de lista
        columnas = resultados["columns"]
        datos = resultados["data"]
        
        # Limitar a 15 filas si hay muchas
        if len(datos) > 15:
            datos_mostrados = datos[:15]
            nota_adicional = f"\n(Mostrando 15 de {len(datos)} resultados)"
        else:
            datos_mostrados = datos
            nota_adicional = ""
            
        # Formatear tabla
        tabla = " | ".join(columnas) + "\n"
        tabla += "-" * (sum(len(col) for col in columnas) + 3 * (len(columnas) - 1)) + "\n"
        tabla += "\n".join([" | ".join(map(str, fila)) for fila in datos_mostrados])
        tabla += nota_adicional
        
        prompt = (
            f"La consulta SQL usada fue: '{consulta_sql}'.\n"
            f"Aquí están los datos obtenidos:\n\n{tabla}\n\n"
            f"Por favor, reformula esta información de manera clara y sencilla para alguien que no tiene conocimientos técnicos, "
            f"como si estuvieras explicándolo a un amigo. Hazlo en un tono accesible y amigable."
        )

        return self._generar_respuesta_con_gpt(prompt)

    def _formatear_resultados_agrupados(self, resultados):
        """
        Formatea resultados de una consulta agrupada (ej: GROUP BY color).
        """
        idx_desc = resultados["columns"].index("description")
        idx_count = resultados["columns"].index("count")
        
        conteos = {row[idx_desc]: row[idx_count] for row in resultados["data"]}
        total = sum(conteos.values())

        # Construir una comparación en lenguaje natural
        mensaje = "Aquí tienes la comparación de elementos por categoría:\n\n"
        
        # Ordenar de mayor a menor
        conteos_ordenados = sorted(conteos.items(), key=lambda x: x[1], reverse=True)
        
        for categoria, count in conteos_ordenados:
            porcentaje = round((count/total)*100, 2)
            emoji = "🚗" if "car" in str(resultados).lower() or "vehic" in str(resultados).lower() else "📊"
            mensaje += f"{emoji} {categoria.capitalize()}: {count} ({porcentaje}%)\n"
        
        mensaje += f"\nEn total se contabilizaron {total} elementos en la base de datos."
        mensaje += "\n\nPor favor, analiza estos datos comparativamente, destacando patrones, proporciones y posibles conclusiones."

        return self._generar_respuesta_con_gpt(mensaje)

    def _formatear_resultados_comparativos(self):
        """
        Combina varias consultas de conteo en un análisis comparativo.
        """
        datos_comparativos = []
        
        # Procesar cada consulta en caché
        for i, (resultados, estructura, sql) in enumerate(zip(self.cache_resultados, self.cache_estructura, self.cache_sql)):
            if "data" in resultados and resultados["data"]:
                valor = resultados["data"][0][0]
                
                # Extraer etiqueta de categoría de la consulta SQL
                categoria = "Desconocido"
                if "WHERE" in sql.upper() and "=" in sql:
                    partes = sql.split("WHERE")[1].split("=")
                    if len(partes) >= 2:
                        # Limpiar comillas y espacios
                        categoria = partes[1].strip().strip('"').strip("'").strip()
                
                datos_comparativos.append((categoria, valor))
        
        # Limpiar caché después de procesar
        self.cache_resultados = []
        self.cache_estructura = []
        self.cache_sql = []
        
        # Si tenemos datos comparativos
        if datos_comparativos:
            total = sum(valor for _, valor in datos_comparativos)
            
            # Ordenar de mayor a menor
            datos_comparativos.sort(key=lambda x: x[1], reverse=True)
            
            mensaje = "Análisis comparativo de categorías:\n\n"
            
            for categoria, valor in datos_comparativos:
                porcentaje = round((valor/total)*100, 2)
                emoji = "🚗" if any("car" in cat.lower() or "vehic" in cat.lower() for cat, _ in datos_comparativos) else "📊"
                mensaje += f"{emoji} {categoria.capitalize()}: {valor} ({porcentaje}%)\n"
            
            mensaje += f"\nEn total se contabilizaron {total} elementos en la base de datos."
            mensaje += "\n\nPor favor, analiza estos datos comparativamente, destacando patrones, proporciones y posibles conclusiones entre las diferentes categorías."
            
            return self._generar_respuesta_con_gpt(mensaje)
        
        return "No se pudieron procesar los datos comparativos."

    def _formatear_resultados_multiples(self, resultados_lista, estructura_consulta, consulta_sql):
        """
        Maneja el caso de recibir múltiples resultados como lista.
        """
        # Si es una lista de resultados pero no tenemos estructuras o consultas como lista
        if not isinstance(estructura_consulta, list) or not isinstance(consulta_sql, list):
            respuestas = []
            for res in resultados_lista:
                respuesta = self._formatear_resultado_individual(res, estructura_consulta, consulta_sql)
                respuestas.append(respuesta)
            return "\n\n".join(respuestas)
        
        # Tenemos listas completas de resultados, estructuras y consultas
        datos_comparativos = []
        
        for i, (res, est, sql) in enumerate(zip(resultados_lista, estructura_consulta, consulta_sql)):
            # Si es consulta de conteo
            if est.get("accion") == "contar" and "data" in res and res["data"]:
                valor = res["data"][0][0]
                
                # Extraer etiqueta de categoría de la consulta SQL o estructura
                categoria = "Grupo " + str(i+1)
                
                # Intentar extraer de SQL
                if "WHERE" in sql.upper() and "=" in sql:
                    partes = sql.split("WHERE")[1].split("=")
                    if len(partes) >= 2:
                        categoria = partes[1].strip().strip('"').strip("'").strip()
                
                # Intentar extraer de estructura
                if est.get("filtros"):
                    for filtro in est["filtros"]:
                        if isinstance(filtro, dict) and "valor" in filtro:
                            categoria = filtro["valor"]
                
                datos_comparativos.append((categoria, valor))
        
        # Si tenemos datos comparativos
        if datos_comparativos and len(datos_comparativos) > 1:
            total = sum(valor for _, valor in datos_comparativos)
            
            # Ordenar de mayor a menor
            datos_comparativos.sort(key=lambda x: x[1], reverse=True)
            
            mensaje = "Análisis comparativo de categorías:\n\n"
            
            for categoria, valor in datos_comparativos:
                porcentaje = round((valor/total)*100, 2)
                emoji = "🚗" if "car" in str(estructura_consulta).lower() or "vehic" in str(estructura_consulta).lower() else "📊"
                mensaje += f"{emoji} {categoria.capitalize()}: {valor} ({porcentaje}%)\n"
            
            mensaje += f"\nEn total se contabilizaron {total} elementos en la base de datos."
            mensaje += "\n\nPor favor, analiza estos datos comparativamente, destacando patrones, proporciones y posibles conclusiones entre las diferentes categorías."
            
            return self._generar_respuesta_con_gpt(mensaje)
        
        # Si no podemos hacer análisis comparativo, procesamos cada resultado individualmente
        respuestas = []
        for i, res in enumerate(resultados_lista):
            est = estructura_consulta[i] if i < len(estructura_consulta) else None
            sql = consulta_sql[i] if i < len(consulta_sql) else None
            respuesta = self._formatear_resultado_individual(res, est, sql)
            respuestas.append(respuesta)
        
        return "\n\n".join(respuestas)