import json
import logging

class UserQueryAgent:
    """
    Agente encargado de interpretar consultas en lenguaje natural y convertirlas en una estructura
    de consulta estructurada (por ejemplo, un diccionario en formato JSON). La estructura resultante
    incluirá:
      - 'accion': La acción que se desea realizar (ej. contar, listar, promedio, etc.).
      - 'tabla': La tabla de la base de datos implicada.
      - 'filtros': Un objeto (diccionario) que representa las condiciones de la consulta en pares columna-valor.
    
    Este agente utiliza un modelo de lenguaje (LLM) para analizar la consulta en el contexto del esquema
    de la base de datos y del mapa semántico.
    """
    
    def __init__(self, llm_api_key=None, model="gpt-3.5-turbo", temperature=0.0):
        """
        :param llm_api_key: Clave API para el modelo de lenguaje (por ejemplo, OpenAI).
        :param model: Modelo de lenguaje a utilizar.
        :param temperature: Controla la aleatoriedad en la respuesta del modelo.
        """
        if llm_api_key:
            try:
                import openai
                openai.api_key = llm_api_key
            except ImportError:
                raise ImportError("El paquete openai no está instalado. Instálalo para usar el LLM.")
        self.model = model
        self.temperature = temperature
        self.logger = logging.getLogger(self.__class__.__name__)

    def interpretar_consulta(self, consulta, schema, semantic_map):
        """
        Interpreta una consulta en lenguaje natural y retorna una estructura de consulta (diccionario)
        con los campos 'accion', 'tabla' y 'filtros'.
        
        :param consulta: Consulta en lenguaje natural.
        :param schema: Esquema de la base de datos (diccionario obtenido, por ejemplo, con DBSchemaAgent).
        :param semantic_map: Mapa semántico para traducir nombres técnicos a nombres legibles.
        :return: Diccionario o lista de diccionarios con la estructura de consulta.
        """
        prompt = self._crear_prompt(consulta, schema, semantic_map)
        respuesta_llm = self._obtener_respuesta_llm(prompt)
        
        try:
            estructura_consulta = json.loads(respuesta_llm)
        except json.JSONDecodeError as e:
            self.logger.error("Error al decodificar la respuesta del LLM: %s", e)
            estructura_consulta = {}
        
        return estructura_consulta

    def _crear_prompt(self, consulta, schema, semantic_map):
        """
        Crea el prompt para enviar al LLM, incluyendo el esquema de la base de datos, el mapa semántico,
        el contexto general de uso de las tablas y la consulta en lenguaje natural del usuario.
        
        :param consulta: Consulta en lenguaje natural.
        :param schema: Esquema de la base de datos en formato diccionario.
        :param semantic_map: Mapa semántico en formato diccionario.
        :return: Prompt completo en forma de cadena de texto.
        """
        prompt = (
        "Eres un asistente experto en bases de datos de detección de objetos (vehículos). "
        "La base de datos que analizas registra detecciones de vehículos y sus atributos. "
        "Es fundamental que, al referirte a colores, estos se entreguen en inglés.\n\n"
        "Ten en cuenta el siguiente contexto específico de las tablas:\n"
        "- La tabla 'detections' registra las detecciones de vehículos. En ella, 'atribute_id' indica el tipo de atributo: "
        "1 para la placa del vehículo y 2 para el color del vehículo.\n"
        "- El campo 'object_id' se utiliza dos veces: una para la placa (cuando 'atribute_id' es 1) y otra para el color (cuando 'atribute_id' es 2).\n"
        "- El campo 'description' contiene el color y la placa del vehículo ya que son strings.\n"
        "- El campo 'acurrancy' representa el porcentaje de éxito con respecto a la similitud de las placas y colores.\n"
        "- La tabla 'object' puede utilizarse para consultas de análisis del sistema basados en rangos.\n"
        "- Si la consulta involucra fechas, asegúrate de incluirlas en el JSON en formato 'dd-mm-yyyy'. Las fechas también pueden estar en lenguaje natural (hoy, ayer) "
        "y si es un rango, utiliza '$gte' y '$lte'.\n\n"
        "A continuación, se proporcionan las reglas y ejemplos para la generación de consultas SQL:\n\n"
        "Reglas:\n"
        "- Si la acción es \"count\", usar: SELECT ... COUNT(*)\n"
        "- Si existen múltiples valores para una columna, usar la cláusula IN\n"
        "- Si se necesitan agregaciones con múltiples valores, usar GROUP BY\n"
        "- Aplicar filtros en la cláusula WHERE\n"
        "- Para filtros de rango con operadores como \">=\" y \"<=\" usar la sintaxis correcta\n"
        "- Usar valores de marca de tiempo en milisegundos\n"
        "- Limitar los resultados a {self.limit} registros\n"
        "- Para consultas complejas con varias columnas de valores, hacer agregaciones y agrupar según sea necesario\n\n"
        "Ejemplos:\n"
        "-> Cantidad de detecciones por cámara:\n"
        "SELECT LEFT(object_id, LENGTH(object_id) - 27) AS Camara_Id, \n"
        "       attribute_id,\n"
        "       count(attribute_id) \n"
        "FROM detections\n"
        "GROUP BY 1, 2;\n\n"
        "-> Cantidad de detecciones por cámara en un determinado período de tiempo:\n"
        "SELECT LEFT(object_id, LENGTH(object_id) - 27) AS Camara_Id, \n"
        "       attribute_id,\n"
        "       count(attribute_id) \n"
        "FROM detections\n"
        "WHERE init_time BETWEEN UNIX_TIMESTAMP('2025-02-27 00:00:00') * 1000 \n"
        "                   AND UNIX_TIMESTAMP('2025-02-27 23:59:59') * 1000\n"
        "GROUP BY 1, 2;\n\n"
        "-> Colores disponibles en la base de datos:\n"
        "SELECT DISTINCT description\n"
        "FROM tabla\n"
        "WHERE attribute_id = 2\n"
        "  AND init_time BETWEEN UNIX_TIMESTAMP('2025-03-05 00:00:00') * 1000 \n"
        "                   AND UNIX_TIMESTAMP('2025-03-05 23:59:59') * 1000;\n\n"
        "-> Cantidad total por colores detectados:\n"
        "SELECT description, COUNT(*) AS cantidad_detecciones\n"
        "FROM detections\n"
        "WHERE attribute_id = 2\n"
        "  AND init_time BETWEEN UNIX_TIMESTAMP('2025-03-05 00:00:00') * 1000 \n"
        "                   AND UNIX_TIMESTAMP('2025-03-05 23:59:59') * 1000\n"
        "GROUP BY description;\n\n"
        "Con estos datos, puedes crear las consultas SQL de acuerdo a lo que se te pida.\n\n"
        "A continuación, se te proporciona el esquema de la base de datos y un mapa semántico que traduce nombres técnicos a nombres legibles:\n\n"
        "Esquema de la base de datos (en formato JSON):\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Mapa semántico (en formato JSON):\n"
        f"{json.dumps(semantic_map, indent=2)}\n\n"
        "Interpreta la siguiente consulta en lenguaje natural y genera una estructura de consulta en formato JSON. "
        "La estructura debe incluir los siguientes campos:\n"
        "- 'accion': La acción a realizar (por ejemplo, 'contar', 'listar', 'promedio').\n"
        "- 'tabla': El nombre de la tabla a consultar.\n"
        "- 'filtros': Un objeto con pares columna-valor que representen las condiciones de la consulta.\n"
        "- Si hay fechas, inclúyelas correctamente en formato 'dd-mm-yyyy' dentro del campo 'filtros'.\n\n"
        "Además, si la consulta en lenguaje natural implica comparar datos (por ejemplo, comparar ventas o métricas entre dos períodos), "
        "devuelve un arreglo JSON en el que cada elemento siga la estructura mostrada anteriormente.\n\n"
        f"Consulta: {consulta}\n\n"
        "Estructura JSON:"
    )
        return prompt

    def _obtener_respuesta_llm(self, prompt):
        """
        Utiliza el modelo de lenguaje (por ejemplo, OpenAI GPT) para obtener una respuesta a partir del prompt.
        
        :param prompt: El prompt a enviar al modelo.
        :return: La respuesta generada por el LLM en formato de texto.
        """
        import openai
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=150
            )
            respuesta = response['choices'][0]['message']['content'].strip()
        except Exception as e:
            self.logger.error("Error al obtener respuesta del LLM: %s", e)
            respuesta = "{}"  # Retornamos un JSON vacío en caso de error.
        
        return respuesta
