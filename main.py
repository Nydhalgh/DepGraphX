from modules.code_scanner import CodeScanner
from modules.llm_integration import GeminiLLMIntegration
import os

def main():
    project_path = input("Enter the path to your project: ").strip()

    # Initialize the code scanner
    scanner = CodeScanner()

    # Ask if the user wants to clear the Neo4j database
    clear_db = input("Clear the Neo4j database before scanning? (y/n): ").strip().lower()
    if clear_db == 'y':
        scanner.graph.clear_database()

    # Scan the project and close the Neo4j connection
    scanner.scan_project(project_path)
    scanner.graph.close()

    # Initialize the LLM integration (API key should be handled internally)
    llm = GeminiLLMIntegration()

    while True:
        print("\nChoose an action:")
        print("1. Summarize a single method")
        print("2. Summarize all methods in a class")
        print("3. Generate Javadoc/TSDoc for a method")
        print("4. Explain a code snippet")
        print("5. Suggest refactoring for a method")
        print("6. Exit")

        choice = input("Enter your choice: ").strip()

        if choice == '1':
            method_to_summarize = input("Enter the name of a method to summarize: ").strip()
            file_of_method = input("Enter the file path of the method: ").strip()
            if not os.path.exists(file_of_method):
                print("Error: File does not exist.")
                continue
            summary = llm.summarize_method(method_to_summarize, file_of_method)
            print(f"\nSummary: {summary}")

        elif choice == '2':
            class_to_summarize = input("Enter the name of a class: ").strip()
            summaries = llm.summarize_all_methods_in_class(class_to_summarize)
            if isinstance(summaries, dict):
                for method_name, summary in summaries.items():
                    print(f"\nMethod: {method_name}\nSummary: {summary}")
            else:
                print(summaries)

        elif choice == '3':
            method_to_document = input("Enter the name of a method to document: ").strip()
            file_of_method = input("Enter the file path of the method: ").strip()
            if not os.path.exists(file_of_method):
                print("Error: File does not exist.")
                continue
            javadoc = llm.generate_javadoc(method_to_document, file_of_method)
            print(f"\nJavadoc/TSDoc:\n{javadoc}")

        elif choice == '4':
            code_snippet = input("Enter the code snippet to explain:\n").strip()
            language_tag = input("Enter the language (java or typescript): ").strip()
            if language_tag.lower() not in ['java', 'typescript']:
                print("Error: Unsupported language. Use 'java' or 'typescript'.")
                continue
            explanation = llm.explain_code(code_snippet, language_tag)
            print(f"\nExplanation:\n{explanation}")

        elif choice == '5':
            method_name = input("Enter the name of the method to refactor: ").strip()
            file_path = input("Enter the file path of the method: ").strip()
            if not os.path.exists(file_path):
                print("Error: File does not exist.")
                continue
            suggestions = llm.suggest_refactoring(method_name, file_path)
            print(f"\nRefactoring Suggestions:\n{suggestions}")

        elif choice == '6':
            print("Exiting the program. Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()