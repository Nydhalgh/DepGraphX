from neo4j import GraphDatabase, Transaction  # Import Transaction
import logging

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Delete all existing nodes and relationships."""
        try:
            with self.driver.session() as session:
                # Use execute_write and a transaction function
                session.execute_write(self._clear_db_transaction)
                self.logger.info("Database cleared successfully.")
        except Exception as e:
            self.logger.error(f"Error clearing database: {e}")

    def _clear_db_transaction(self, tx: Transaction):
        """Transaction function to clear the database."""
        tx.run("MATCH (n) DETACH DELETE n")

    def create_project_node(self, project_path):
        """Create a root node for the project."""
        try:
            with self.driver.session() as session:
                session.execute_write(self._create_project_node_transaction, project_path)
                self.logger.info(f"Created project node: {project_path}")
        except Exception as e:
            self.logger.error(f"Error creating project node: {e}")

    def _create_project_node_transaction(self, tx: Transaction, project_path):
        tx.run("MERGE (p:Project {path: $path})", path=project_path)

    def create_class_node(self, class_name, file_path):
        """Create a Class node."""
        try:
            with self.driver.session() as session:
                session.execute_write(self._create_class_node_transaction, class_name, file_path)
                self.logger.info(f"Created class node: {class_name}")
        except Exception as e:
            self.logger.error(f"Error creating class node: {e}")

    def _create_class_node_transaction(self, tx: Transaction, class_name, file_path):
        tx.run("MERGE (c:Class {name: $name, file: $file})", name=class_name, file=file_path)

    def create_method_node(self, method_name, class_name, file_path):
        """Create a Method node linked to its Class."""
        try:
            with self.driver.session() as session:
                session.execute_write(self._create_method_node_transaction, method_name, class_name, file_path)
                self.logger.info(f"Created method node: {method_name} in class {class_name}")
        except Exception as e:
            self.logger.error(f"Error creating method node: {e}")

    def _create_method_node_transaction(self, tx: Transaction, method_name, class_name, file_path):
         tx.run(
            """
            MERGE (m:Method {name: $method_name, class: $class_name, file: $file})
            MERGE (c:Class {name: $class_name, file: $file})
            MERGE (c)-[:HAS_METHOD]->(m)
            """,
            method_name=method_name,
            class_name=class_name,
            file=file_path
        )

    def create_dependency(self, dependency_data):
        """Create relationships for method calls, imports, etc."""
        try:
            with self.driver.session() as session:
              session.execute_write(self._create_dependency_transaction, dependency_data)

        except Exception as e:
            self.logger.error(f"Error creating dependency: {e}")
    
    def _create_dependency_transaction(self, tx: Transaction, dependency_data: dict):
        if dependency_data['type'] == 'method_call':
            # Split callee into object and method
            try:
                callee_object, callee_method = dependency_data['callee'].split('.', 1)
            except ValueError:
                self.logger.warning(f"Invalid callee format: {dependency_data['callee']}")
                return

            tx.run(
                """
                MATCH (caller_class:Class {name: $caller_class})
                MATCH (caller_method:Method {name: $caller_method})-[:BELONGS_TO]->(caller_class)
                MERGE (callee_method:Method {name: $callee})
                MERGE (caller_method)-[:CALLS]->(callee_method)
                """,
                    caller_class=dependency_data['caller_class'],
                    caller_method=dependency_data['caller_method'],
                    callee=dependency_data['callee'] # Pass the full callee name
            )
            self.logger.info(f"Created method call: {dependency_data.get('caller_method')} -> {dependency_data.get('callee')}")

        elif dependency_data['type'] == 'import':
            tx.run(
                """
                MATCH (c:Class {file: $file})
                MERGE (i:Import {path: $import_path})
                MERGE (c)-[:IMPORTS]->(i)
                """,
                file=dependency_data['file'],
                import_path=dependency_data['import_path']
            )
            self.logger.info(f"Created import: {dependency_data['import_path']}")

        elif dependency_data['type'] == 'inheritance':
            if 'interfaces' in dependency_data: # Handle interfaces
                for interface in dependency_data['interfaces']:
                    tx.run(
                        """
                        MATCH (c:Class {name: $class_name, file: $file})
                        MERGE (i:Interface {name: $interface_name})
                        MERGE (c)-[:IMPLEMENTS]->(i)
                        """,
                        class_name=dependency_data['class'],
                        interface_name=interface,
                        file=dependency_data['file']
                    )
                self.logger.info(f"Created implements relationship: {dependency_data['class']} implements {dependency_data['interfaces']}")
            elif 'parent' in dependency_data:  # Handle class extension
                tx.run(
                    """
                    MATCH (c:Class {name: $class_name, file: $file})
                    MERGE (p:Class {name: $parent_name})
                    MERGE (c)-[:EXTENDS]->(p)
                    """,
                    class_name=dependency_data['class'],
                    parent_name=dependency_data['parent'],
                    file=dependency_data['file']
                )
                self.logger.info(f"Created extends relationship: {dependency_data['class']} extends {dependency_data['parent']}")