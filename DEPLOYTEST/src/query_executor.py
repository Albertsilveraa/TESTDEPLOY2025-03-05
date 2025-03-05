#query_executor.py


import logging
class QueryExecutor:
    def __init__(self, get_connection):
        self.get_connection = get_connection
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def ejecutar_sql(self, sql):
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if isinstance(sql, str):
                self.logger.info("Ejecutando SQL: %s", sql)
                cursor.execute(sql)
                
                # Solo fetch si es SELECT (tiene descripción)
                if cursor.description:
                    data = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                else:
                    data = []
                    columns = []
                    conn.commit()  # Commit para DML
                
                return {"columns": columns, "data": data}
            
            elif isinstance(sql, list):
                results_list = []
                for idx, single_query in enumerate(sql, start=1):
                    self.logger.info("Ejecutando SQL %d: %s", idx, single_query)
                    cursor.execute(single_query)
                    
                    if cursor.description:
                        data = cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                    else:
                        data = []
                        columns = []
                        conn.commit()  # Commit para DML
                    
                    results_list.append({"columns": columns, "data": data})
                return results_list
            
        except Exception as e:
            self.logger.error("Error al ejecutar la consulta SQL: %s", e)
            conn.rollback()  # Rollback en caso de error
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()