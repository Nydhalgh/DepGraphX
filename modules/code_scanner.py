import os
from pathlib import Path
from tree_sitter import Language, Parser
from .graph_db import Neo4jGraph  # Import from the same package


# --- Setup (Tree-sitter) --- (Moved here for clarity and to avoid repetition)
MODULE_DIR = os.path.dirname(__file__)
GRAMMARS_DIR = os.path.join(MODULE_DIR, "../vendor")
BUILD_DIR = os.path.join(MODULE_DIR, "../build")
LIBRARY_PATH = os.path.join(BUILD_DIR, "my-languages.so")
os.makedirs(BUILD_DIR, exist_ok=True)

# Build the Tree-sitter languages (only needs to happen once)
Language.build_library(
    LIBRARY_PATH,
    [
        os.path.join(GRAMMARS_DIR, "tree-sitter-java"),
        os.path.join(GRAMMARS_DIR, "tree-sitter-typescript", "typescript"),
    ],
)

JAVA_LANGUAGE = Language(LIBRARY_PATH, "java")
TS_LANGUAGE = Language(LIBRARY_PATH, "typescript")



class CodeScanner:
    def __init__(self):
        self.parser = Parser()
        self.supported_extensions = {
            '.java': JAVA_LANGUAGE,
            '.ts': TS_LANGUAGE,
            '.tsx': TS_LANGUAGE
        }
        # Define language-specific queries for dependencies
        self.QUERIES = {
            'java': {
                'method_calls': """
                    (method_invocation
                        object: (identifier) @object
                        name: (identifier) @method
                    ) @call
                """,
                'imports': "(import_declaration (scoped_identifier) @import_path)",
                'inheritance': """
                    (class_declaration
                        name: (identifier) @class_name
                        (super_interfaces (type_list (type_identifier) @interface))
                    )
                """
            },
            'typescript': {
                'method_calls': """
                    (call_expression
                        function: (member_expression object: (identifier) @object property: (property_identifier) @method)
                    ) @call
                """,
                'imports': """
                    (import_statement
                        (import_clause
                            (identifier)? @import_default
                            (named_imports)? @named_imports
                            ("*")? @wildcard)
                        source: (string) @module_path
                    )
                    """,
                'inheritance': "(class_declaration (extends_clause (identifier) @parent))"
            }
        }
        self.graph = Neo4jGraph("bolt://localhost:7687", "neo4j", "codegraph")


    def _get_node_text(self, node, source_code):
        """Extract text from a node."""
        return source_code[node.start_byte:node.end_byte].decode('utf-8')

    def _get_files(self, project_path):
        """Get all files in the project with supported extensions."""
        file_paths = []
        for root, _, files in os.walk(project_path):
            for file in files:
                ext = Path(file).suffix
                if ext in self.supported_extensions:
                    file_paths.append(os.path.join(root, file))
        return file_paths

    def _parse_file(self, file_path, language):
        """Parse a file and return its AST."""
        self.parser.set_language(language)
        with open(file_path, 'rb') as f:
            source_code = f.read()
        return self.parser.parse(source_code)
        

    def _extract_entities(self, node, source_code, entities, file_path):
        """Extract classes/methods and track their byte ranges."""
        if node.type == 'class_declaration':
            class_name = self._get_node_text(node.child_by_field_name('name'), source_code)
            entities['classes'].append({
                'name': class_name,
                'file': file_path,
                'start_byte': node.start_byte,
                'end_byte': node.end_byte
            })
            self.graph.create_class_node(class_name, file_path) # Add to Neo4j

        elif node.type == 'method_declaration':
            method_name = self._get_node_text(node.child_by_field_name('name'), source_code)
            current_class = next(
                (cls for cls in entities['classes']
                 if cls['start_byte'] <= node.start_byte < cls['end_byte']),
                None
            )
            if current_class:
                entities['methods'].append({
                    'name': method_name,
                    'class': current_class['name'],
                    'file': file_path,
                    'start_byte': node.start_byte,
                    'end_byte': node.end_byte
                })
                self.graph.create_method_node(method_name, current_class['name'], file_path) # Add to Neo4j

        for child in node.children:
            self._extract_entities(child, source_code, entities, file_path)


    def _find_enclosing_entity(self, node_byte, entities, file_path, entity_type):
        """Find the class/method enclosing a node."""
        candidates = [e for e in entities[entity_type] if e['file'] == file_path]
        for entity in candidates:
            if entity['start_byte'] <= node_byte < entity['end_byte']:
                return entity
        return None
    
    def _process_dependency(self, captures, lang, source_code, entities, file_path):
        """Processes captures from tree-sitter queries."""
        for node, tag in captures:
            if lang == "java":
                if tag == "call":
                    # Method call processing (Java)
                    method_name = None
                    object_name = None
                    for child_node, child_tag in captures:  # Iterate through all captures
                        if child_tag == 'method':
                            method_name = self._get_node_text(child_node, source_code)
                        elif child_tag == 'object':
                            object_name = self._get_node_text(child_node, source_code)

                    if method_name and object_name:
                        callee = f"{object_name}.{method_name}"
                        enclosing_class = self._find_enclosing_entity(node.start_byte, entities, file_path, 'classes')
                        enclosing_method = self._find_enclosing_entity(node.start_byte, entities, file_path, 'methods')

                        if enclosing_class and enclosing_method:
                            dependency = {
                                'type': 'method_call',
                                'caller_class': enclosing_class['name'] if enclosing_class else None,
                                'caller_method': enclosing_method['name'] if enclosing_method else None,  # Use just method name
                                'callee': callee,  # Keep this as a single string
                                'file': file_path,
                            }
                            entities['dependencies'].append(dependency)


                elif tag == "import_path":
                    # Import processing (Java)
                    import_path = self._get_node_text(node, source_code)
                    dependency = {
                        'type': 'import',
                        'file': file_path,
                        'import_path': import_path
                    }
                    entities['dependencies'].append(dependency)

                elif tag == "class_name":
                    # Inheritance processing (Java)
                    class_name = self._get_node_text(node, source_code)
                    interfaces = []
                    for child_node, child_tag in captures:
                        if child_tag == 'interface':
                            interfaces.append(self._get_node_text(child_node, source_code))
                    dependency = {
                            'type': 'inheritance',
                            'class': class_name,
                            'file': file_path,
                            'interfaces': interfaces
                        }
                    entities['dependencies'].append(dependency)

            elif lang == "typescript":
                if tag == "call":
                    # Method call processing (TypeScript)
                     method_name = None
                     object_name = None

                     for child_node, child_tag in captures:
                        if child_tag == 'method':
                            method_name = self._get_node_text(child_node, source_code)
                        elif child_tag == 'object':
                            object_name = self._get_node_text(child_node, source_code)
                     if method_name and object_name:
                        callee = f"{object_name}.{method_name}"
                        enclosing_class = self._find_enclosing_entity(node.start_byte, entities, file_path, 'classes')
                        enclosing_method = self._find_enclosing_entity(node.start_byte, entities, file_path, 'methods')
                        if enclosing_class and enclosing_method:
                            dependency = {
                                'type': 'method_call',
                                'caller_class': enclosing_class['name'] if enclosing_class else None,
                                'caller_method': enclosing_method['name'] if enclosing_method else None,
                                'callee': callee,
                                'file': file_path
                            }
                            entities['dependencies'].append(dependency)

                elif tag.startswith("import"):
                    # Import processing (TypeScript)
                    module_path = None
                    for n, t in captures:
                        if t == 'module_path':
                            module_path_str = self._get_node_text(n, source_code)
                            module_path = module_path_str.strip('\'"')
                            break
                    if module_path:
                        dependency = {
                            'type': 'import',
                            'file': file_path,
                            'import_path': module_path,
                        }
                        entities['dependencies'].append(dependency)


                elif tag == "parent":
                    # Inheritance processing (TypeScript)
                    parent_class = self._get_node_text(node, source_code)
                    enclosing_class = self._find_enclosing_entity(node.start_byte, entities, file_path, 'classes')
                    if enclosing_class:
                        dependency = {
                            'type': 'inheritance',
                            'class': enclosing_class['name'],
                            'file': file_path,
                            'parent': parent_class
                        }
                        entities['dependencies'].append(dependency)

    def scan_project(self, project_path):
        entities = {'classes': [], 'methods': [], 'dependencies': []}
        files = self._get_files(project_path)

        for file_path in files:
            ext = Path(file_path).suffix
            language = self.supported_extensions.get(ext)
            if not language:
                continue

            tree = self._parse_file(file_path, language)
            source_code = open(file_path, 'rb').read()
            self._extract_entities(tree.root_node, source_code, entities, file_path)

            lang = 'java' if ext == '.java' else 'typescript'
            queries = self.QUERIES.get(lang, {})
            for query_type, query_str in queries.items():
                query = language.query(query_str)
                captures = query.captures(tree.root_node)  # Get ALL captures
                self._process_dependency(captures, lang, source_code, entities, file_path)
        # Create dependencies in Neo4j *after* processing all files and all dependencies
        for dependency in entities['dependencies']:
            self.graph.create_dependency(dependency)

        return entities
    def get_method_source(self, method_name, file_path):
        """Retrieves the source code of a method given its name and file path."""
        try:
            language = self.supported_extensions.get(Path(file_path).suffix)
            if not language:
                return None  # Or raise an exception

            tree = self._parse_file(file_path, language)
            source_code_bytes = open(file_path, 'rb').read()
            source_code = source_code_bytes.decode('utf-8')

            # Use Tree-sitter to find the method node
            query_str = """
                (method_declaration
                    name: (identifier) @method_name
                ) @method
            """
            query = language.query(query_str)
            captures = query.captures(tree.root_node)

            for node, tag in captures:
                if tag == 'method_name':
                    current_method_name = self._get_node_text(node, source_code)
                    if current_method_name == method_name:
                        # Found the method, get its source
                        start_byte = node.parent.start_byte  # Get the method declaration's start
                        end_byte = node.parent.end_byte # and end byte
                        return source_code_bytes[start_byte:end_byte].decode('utf-8')

            return None # Method not found
        except Exception as e:
            self.graph.logger.error(f"Error in get_method_source: {e}") #Use the same logger
            return None
