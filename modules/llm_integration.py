import google.generativeai as genai
import os
from pathlib import Path
from .code_scanner import CodeScanner

class GeminiLLMIntegration:
    def __init__(self, api_key):
        genai.configure(api_key="AIzaSyCsBa_hCihv8UVGL8i7irmWO4ZwHNwY0fg")
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = "Write a short poem about nature."

        response = model.generate_text(prompt=prompt)
        print(response.result)
        self.code_scanner = CodeScanner()

    def summarize_method(self, method_name, file_path):
        """Summarizes a method using the Gemini API."""
        source_code = self.code_scanner.get_method_source(method_name, file_path)
        if source_code is None:
            return "Error: Method not found or source code could not be retrieved."

        file_extension = Path(file_path).suffix
        language_tag = "java" if file_extension == ".java" else "typescript"

        prompt = f"""
    You are a helpful code assistant.  Summarize the following method in one sentence:

    {language_tag}
    {source_code}
    
    Summary:
    """

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error calling Gemini API: {e}"
        
    def summarize_all_methods_in_class(self, class_name):
        """Summarizes all methods in a given class."""
        try:
            with self.code_scanner.graph.driver.session() as session:
                result = session.run(
                    "MATCH (m:Method {class: $class_name}) RETURN m.name AS methodName, m.file AS filePath",
                    class_name=class_name
                )

            summaries = {}
            for record in result:
                method_name = record["methodName"]
                file_path = record["filePath"]
                summary = self.summarize_method(method_name, file_path)
                summaries[method_name] = summary
            return summaries

        except Exception as e:
            return f"Error retrieving methods from Neo4j or summarizing: {e}"


    def generate_javadoc(self, method_name, file_path):
        """Generates Javadoc-style documentation for a method."""
        source_code = self.code_scanner.get_method_source(method_name, file_path)
        if source_code is None:
            return "Error: Method not found or source code could not be retrieved."

        file_extension = Path(file_path).suffix
        language_tag = "java" if file_extension == ".java" else "typescript"

        prompt = f"""
    You are a helpful code assistant. Generate Javadoc-style documentation (or TSDoc if Typescript) for the following method:
    {source_code}
    Documentation:
    """

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error calling Gemini API: {e}"


    def explain_code(self, code_snippet, language_tag):
        """Explains a given code snippet in plain English."""
        prompt = f"""
    You are a helpful code assistant. Explain the following code snippet in plain English:

    {code_snippet}
    Explanation:
    """

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error calling Gemini API: {e}"
        
    
    def suggest_refactoring(self, method_name, file_path):
        """Suggests refactoring improvements for a method."""
        source_code = self.code_scanner.get_method_source(method_name, file_path)
        if source_code is None:
            return "Error: Method not found or source code could not be retrieved."

        file_extension = Path(file_path).suffix
        language_tag = "java" if file_extension == ".java" else "typescript"

        prompt = f"""
        You are a helpful code assistant. Suggest refactoring improvements for the following method, focusing on best practices, readability, and maintainability. If no significant improvements are needed, respond with 'No significant refactoring needed.'.

        Refactoring Suggestions:
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error calling Gemini API: {e}"
        return f"Error calling Gemini API: {e}"