# modules/semantic_mapping.py

class SemanticMappingAgent:
    """
    Agente encargado de generar un mapa semántico a partir del esquema técnico de la base de datos.
    
    Funciones principales:
      - Convertir nombres técnicos (snake_case) a una versión legible para humanos.
      - Generar un diccionario que mapea cada tabla y cada columna a su versión humanizada.
      - Permitir reglas personalizadas para contextos o columnas específicas.
    
    Ejemplo:
      Dado un esquema con una tabla "carros_venta" y una columna "descripcion",
      se generará un mapeo como:
        {
          "carros_venta": {
              "human_name": "Carros Venta",
              "columns": {
                  "descripcion": "Descripcion"
              }
          }
        }
    """
    
    def __init__(self, custom_rules=None):
        """
        :param custom_rules: (Opcional) Diccionario con reglas personalizadas de mapeo.
                             La llave es una tupla (nombre_columna, nombre_tabla) y el valor
                             es el nombre humanizado que se desea asignar.
                             Ejemplo: { ("descripcion", "carros_venta"): "Color" }
        """
        # Cache interna para el mapa semántico
        self.map_cache = {}
        # Reglas personalizadas para columnas específicas (si se requieren)
        self.custom_rules = custom_rules if custom_rules is not None else {}

    def humanize_name(self, name):
        """
        Convierte un nombre técnico en un nombre legible para humanos.
        Ejemplo:
            "carros_venta" -> "Carros Venta"
            "fecha_creacion" -> "Fecha Creacion"
        :param name: Nombre técnico a transformar.
        :return: Nombre humanizado.
        """
        # Separa la cadena por guiones bajos y capitaliza cada palabra.
        words = name.split('_')
        humanized = " ".join(word.capitalize() for word in words)
        return humanized

    def generate_map(self, schema):
        """
        Genera un diccionario mapeando los nombres técnicos de las tablas y columnas
        a sus equivalentes humanizados.
        
        :param schema: Diccionario del esquema obtenido (por ejemplo, a partir de DBSchemaAgent).
        :return: Diccionario de mapeo semántico.
        """
        # Si ya se generó el mapa, se devuelve la versión cachada.
        if self.map_cache:
            return self.map_cache

        mapping = {}
        
        # Iterar sobre las tablas en el esquema.
        for table, details in schema.items():
            human_table_name = self.humanize_name(table)
            mapping[table] = {
                'human_name': human_table_name,
                'columns': {}
            }
            
            # Procesar cada columna de la tabla.
            for col in details.get('columns', {}):
                # Verificar si existe una regla personalizada para esta columna en esta tabla.
                custom_key = (col, table)
                if custom_key in self.custom_rules:
                    human_col_name = self.custom_rules[custom_key]
                else:
                    human_col_name = self.humanize_name(col)
                mapping[table]['columns'][col] = human_col_name
        
        self.map_cache = mapping
        return mapping

    def get_human_table_name(self, table, mapping=None):
        """
        Retorna el nombre humanizado de una tabla.
        
        :param table: Nombre técnico de la tabla.
        :param mapping: (Opcional) Diccionario de mapeo semántico a utilizar. Si no se provee,
                        se utiliza el cache interno.
        :return: Nombre humanizado de la tabla.
        """
        mapping = mapping or self.map_cache
        if table in mapping:
            return mapping[table].get('human_name', self.humanize_name(table))
        return self.humanize_name(table)

    def get_human_column_name(self, table, column, mapping=None):
        """
        Retorna el nombre humanizado de una columna, dada la tabla en la que se encuentra.
        
        :param table: Nombre técnico de la tabla.
        :param column: Nombre técnico de la columna.
        :param mapping: (Opcional) Diccionario de mapeo semántico a utilizar.
        :return: Nombre humanizado de la columna.
        """
        mapping = mapping or self.map_cache
        if table in mapping and 'columns' in mapping[table]:
            return mapping[table]['columns'].get(column, self.humanize_name(column))
        return self.humanize_name(column)
